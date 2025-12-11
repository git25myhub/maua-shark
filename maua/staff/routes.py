from flask import render_template, redirect, url_for, flash, request, jsonify, send_file, current_app, make_response
from flask_login import login_required, current_user
from functools import wraps
from maua.extensions import db
from . import staff_bp
from maua.booking.models import Booking
from maua.catalog.models import Trip, Vehicle, Route
from maua.parcels.models import Parcel
from datetime import datetime
from maua.notifications.sms import send_sms
from maua.notifications.notification_service import NotificationService
from werkzeug.utils import secure_filename
import os
import io
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER


def staff_required(f):
    """Require staff or admin role to access this route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not (current_user.is_admin or current_user.is_staff):
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function


@staff_bp.route('/')
@login_required
@staff_required
def dashboard():
    booking_count = Booking.query.count()
    parcel_count = Parcel.query.count()
    active_trips = Trip.query.filter(Trip.status.in_(['scheduled', 'in_progress'])).count()
    today_date = datetime.now().strftime('%b %d, %Y')
    return render_template('staff/dashboard.html', 
                         booking_count=booking_count, 
                         parcel_count=parcel_count, 
                         active_trips=active_trips,
                         today_date=today_date)


@staff_bp.route('/bookings/routes')
@login_required
@staff_required
def bookings_routes():
    routes = Route.query.order_by(Route.code.asc()).all()
    return render_template('staff/bookings_routes.html', routes=routes)


@staff_bp.route('/bookings/routes/<int:route_id>/trips')
@login_required
@staff_required
def bookings_route_trips(route_id: int):
    route = Route.query.get_or_404(route_id)
    # Show recent/scheduled trips for this route
    trips = Trip.query.filter_by(route_id=route_id).order_by(Trip.depart_at.desc()).limit(200).all()
    return render_template('staff/bookings_route_trips.html', route=route, trips=trips)


@staff_bp.route('/bookings')
@login_required
@staff_required
def bookings_list():
    status = request.args.get('status')
    trip_id = request.args.get('trip_id', type=int)
    if not trip_id:
        return redirect(url_for('staff.bookings_routes'))
    query = Booking.query.filter(Booking.trip_id == trip_id).order_by(Booking.created_at.desc())
    if status:
        query = query.filter(Booking.status == status)
    bookings = query.limit(200).all()
    selected_trip = Trip.query.get_or_404(trip_id)
    return render_template('staff/bookings.html', bookings=bookings, selected_trip=selected_trip)


@staff_bp.route('/bookings/<int:booking_id>/status', methods=['POST'])
@login_required
@staff_required
def bookings_update_status(booking_id: int):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    if new_status not in ['confirmed', 'reserved', 'checked_in', 'cancelled', 'completed']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('staff.bookings_list'))
    try:
        booking.status = new_status
        db.session.commit()
        
        # Send notifications based on status change
        try:
            if new_status == 'checked_in':
                # Send check-in notification (SMS + Email)
                NotificationService.notify_booking_checked_in(booking)
                current_app.logger.info(f'Check-in notification sent for booking {booking.reference}')
            elif new_status == 'completed':
                # Send trip completion thank you (SMS + Email)
                NotificationService.notify_booking_completed(booking)
                current_app.logger.info(f'Completion notification sent for booking {booking.reference}')
            elif new_status == 'cancelled':
                # Send cancellation notification
                NotificationService.notify_booking_cancelled(booking)
                current_app.logger.info(f'Cancellation notification sent for booking {booking.reference}')
        except Exception as e:
            current_app.logger.error(f'Failed to send notification: {e}')
        
        flash('Booking status updated.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update booking.', 'danger')
    return redirect(url_for('staff.bookings_list'))


@staff_bp.route('/parcels')
@login_required
@staff_required
def parcels_list():
    status = request.args.get('status')
    query = Parcel.query.order_by(Parcel.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    parcels = query.limit(200).all()
    return render_template('staff/parcels.html', parcels=parcels)


@staff_bp.route('/parcels/<int:parcel_id>/status', methods=['POST'])
@login_required
@staff_required
def parcels_update_status(parcel_id: int):
    parcel = Parcel.query.get_or_404(parcel_id)
    new_status = request.form.get('status')
    if new_status not in ['pending', 'in_transit', 'delivered', 'cancelled']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('staff.parcels_list'))
    try:
        parcel.status = new_status
        db.session.commit()
        
        # Send notifications based on status change
        try:
            # Use parcel's stored emails (sender_email, receiver_email) for notifications
            # These are collected during parcel creation
            if new_status == 'in_transit':
                # Send in-transit notification to sender and receiver
                NotificationService.notify_parcel_in_transit(
                    parcel, 
                    vehicle=parcel.vehicle_plate,
                    driver_name=parcel.driver_name,
                    driver_phone=parcel.driver_phone
                )
                current_app.logger.info(f'In-transit notification sent for parcel {parcel.ref_code}')
            elif new_status == 'delivered':
                # Send delivery confirmation with appreciation message
                NotificationService.notify_parcel_delivered(parcel)
                current_app.logger.info(f'Delivery notification sent for parcel {parcel.ref_code}')
            elif new_status == 'pending':
                # Simple SMS for pending status
                msg = f"Maua Shark: Parcel {parcel.ref_code} is pending dispatch from {parcel.origin_name}."
                send_sms(parcel.sender_phone, msg, user_email=parcel.sender_email)
        except Exception as e:
            current_app.logger.error(f'Failed to send parcel notification: {e}')
        
        flash('Parcel status updated.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update parcel.', 'danger')
    return redirect(url_for('staff.parcels_list'))


@staff_bp.route('/parcels/<int:parcel_id>/tracking', methods=['POST', 'HEAD'])
@login_required
@staff_required
def parcels_assign_tracking(parcel_id: int):
    parcel = Parcel.query.get_or_404(parcel_id)
    
    # Handle HEAD requests (for uptime monitoring)
    if request.method == 'HEAD':
        return '', 200
    
    # Backward-compat: accept tracking_number but prefer vehicle assignments
    tracking_number = request.form.get('tracking_number')
    vehicle_plate = request.form.get('vehicle_plate')
    driver_name = request.form.get('driver_name')
    driver_phone = request.form.get('driver_phone')
    if not any([tracking_number, vehicle_plate, driver_name, driver_phone]):
        flash('Provide vehicle plate, driver name, or driver phone.', 'danger')
        return redirect(url_for('staff.parcels_list'))
    try:
        if tracking_number:
            parcel.tracking_number = tracking_number
        if vehicle_plate:
            parcel.vehicle_plate = vehicle_plate
        if driver_name:
            parcel.driver_name = driver_name
        if driver_phone:
            parcel.driver_phone = driver_phone
        db.session.commit()
        # Notify customer of vehicle assignment using parcel's stored emails
        try:
            details = []
            if parcel.vehicle_plate:
                details.append(f"Vehicle {parcel.vehicle_plate}")
            if parcel.driver_name:
                details.append(f"Driver: {parcel.driver_name}")
            if parcel.driver_phone:
                details.append(f"Phone: {parcel.driver_phone}")
            if details:
                info = ", ".join(details)
                msg_sender = (
                    f"Maua Shark: Parcel {parcel.ref_code} assigned to {info}. Track with your reference code."
                )
                # Use parcel's stored emails for notifications
                send_sms(parcel.sender_phone, msg_sender, user_email=parcel.sender_email)
                # Inform receiver as well
                try:
                    send_sms(parcel.receiver_phone, msg_sender, user_email=parcel.receiver_email)
                except Exception:
                    pass
        except Exception:
            pass
        flash('Assignment saved.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to save assignment.', 'danger')
    return redirect(url_for('staff.parcels_list'))


@staff_bp.route('/trips')
@login_required
@staff_required
def trips_list():
    status = request.args.get('status')
    query = Trip.query.order_by(Trip.depart_at.desc())
    if status:
        query = query.filter_by(status=status)
    else:
        # By default, show only active trips (exclude completed)
        query = query.filter(Trip.status.in_(['scheduled', 'in_progress']))
    trips = query.limit(200).all()
    return render_template('staff/trips.html', trips=trips)


@staff_bp.route('/trips/create', methods=['GET', 'POST'])
@login_required
@staff_required
def trips_create():
    if request.method == 'POST':
        route_id = request.form.get('route_id', type=int)
        vehicle_id = request.form.get('vehicle_id', type=int)
        depart_at = request.form.get('depart_at')
        base_fare = request.form.get('base_fare', type=float)
        driver_name = request.form.get('driver_name')
        driver_phone = request.form.get('driver_phone')
        try:
            depart_dt = datetime.fromisoformat(depart_at)
            trip = Trip(route_id=route_id, vehicle_id=vehicle_id, depart_at=depart_dt, base_fare=base_fare, status='scheduled', driver_name=driver_name, driver_phone=driver_phone)
            db.session.add(trip)
            db.session.commit()
            flash('Trip created.', 'success')
            return redirect(url_for('staff.trips_list'))
        except Exception:
            db.session.rollback()
            flash('Failed to create trip.', 'danger')
    routes = Route.query.all()
    vehicles = Vehicle.query.all()
    return render_template('staff/trips_create.html', routes=routes, vehicles=vehicles)


@staff_bp.route('/trips/<int:trip_id>/status', methods=['POST'])
@login_required
@staff_required
def trips_update_status(trip_id: int):
    trip = Trip.query.get_or_404(trip_id)
    new_status = request.form.get('status')
    if new_status not in ['scheduled', 'in_progress', 'completed', 'cancelled']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('staff.trips_list'))
    try:
        trip.status = new_status
        db.session.commit()
        
        # Send bell notifications to customers about trip status change
        try:
            NotificationService.notify_trip_status_change(trip, new_status)
        except Exception as e:
            current_app.logger.error(f'Failed to send trip status notifications: {e}')
        
        # When trip is completed, mark relevant bookings as completed
        if new_status == 'completed':
            try:
                bookings_to_complete = Booking.query.filter(
                    Booking.trip_id == trip.id,
                    Booking.status.in_(['confirmed', 'checked_in'])
                ).all()
                for b in bookings_to_complete:
                    b.status = 'completed'
                    try:
                        msg = (
                            f"Maua Shark: Trip completed. Thank you for traveling with us, {b.passenger_name}. "
                            f"We appreciate you and welcome you to ride with MAUA SHARK again."
                        )
                        user_email = b.user.email if b.user and hasattr(b.user, 'email') else None
                        send_sms(b.passenger_phone, msg, user_email=user_email)
                    except Exception:
                        pass
                db.session.commit()
            except Exception:
                db.session.rollback()
                # Swallow error but log it
                try:
                    from flask import current_app
                    current_app.logger.error('Failed to auto-complete bookings for trip %s', trip.id)
                except Exception:
                    pass
        flash('Trip status updated.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update trip.', 'danger')
    # If marked completed, take user to completed trips page
    if new_status == 'completed':
        return redirect(url_for('staff.trips_completed'))
    return redirect(url_for('staff.trips_list'))


@staff_bp.route('/trips/completed')
@login_required
@staff_required
def trips_completed():
    trips = Trip.query.filter_by(status='completed').order_by(Trip.depart_at.desc()).limit(500).all()
    return render_template('staff/trips_completed.html', trips=trips)


@staff_bp.route('/trips/completed/export_pdf', methods=['POST'])
@login_required
@staff_required
def trips_completed_export_pdf():
    # Fetch completed trips to export
    trips = Trip.query.filter_by(status='completed').order_by(Trip.depart_at.asc()).all()
    if not trips:
        flash('No completed trips to export.', 'info')
        return redirect(url_for('staff.trips_completed'))

    # Generate PDF in-memory
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_left = 40
    margin_top = height - 40
    line_height = 16

    pdf.setTitle('Completed Trips')
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(margin_left, margin_top, 'Completed Trips Export')
    pdf.setFont('Helvetica', 10)
    y = margin_top - 24

    for idx, t in enumerate(trips, start=1):
        lines = [
            f"#{idx} Trip ID: {t.id}",
            f"Route: {t.route.origin.town} -> {t.route.destination.town}",
            f"Departs: {t.depart_at.strftime('%Y-%m-%d %H:%M') if t.depart_at else ''}",
            f"Vehicle: {getattr(t.vehicle, 'plate_no', '')} ({getattr(t.vehicle, 'make', '')} {getattr(t.vehicle, 'model', '')})",
            f"Driver: {t.driver_name or ''} | Phone: {t.driver_phone or ''}",
            f"Base Fare: {t.base_fare} | Status: {t.status}",
        ]
        for line in lines:
            if y < 60:
                pdf.showPage()
                pdf.setFont('Helvetica', 10)
                y = margin_top
            pdf.drawString(margin_left, y, line)
            y -= line_height
        # spacer
        y -= 8

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    # After generating, delete the completed trips
    try:
        for t in trips:
            db.session.delete(t)
        db.session.commit()
        flash('Exported and cleared completed trips.', 'success')
    except Exception:
        db.session.rollback()
        flash('Export successful, but failed to clear completed trips.', 'warning')

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"completed_trips_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )


@staff_bp.route('/vehicles')
@login_required
@staff_required
def vehicles_list():
    vehicles = Vehicle.query.order_by(Vehicle.plate_no.asc()).all()
    return render_template('staff/vehicles.html', vehicles=vehicles)


@staff_bp.route('/vehicles/<int:vehicle_id>/seats', methods=['GET', 'POST'])
@login_required
@staff_required
def vehicle_seat_layout(vehicle_id: int):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if request.method == 'POST':
        # Expect JSON-like textarea where each line is a seat code
        seats_text = request.form.get('seats', '').strip()
        layout = []
        for token in seats_text.split():
            layout.append({'seat': token})
        vehicle.seat_layout = layout
        vehicle.seat_count = len(layout)
        try:
            db.session.commit()
            flash('Seat layout updated.', 'success')
        except Exception:
            db.session.rollback()
            flash('Failed to update seats.', 'danger')
        return redirect(url_for('staff.vehicles_list'))
    # Pre-fill seats as space-separated codes
    seats_text = ''
    if vehicle.seat_layout:
        seats_text = ' '.join([s['seat'] for s in vehicle.seat_layout])
    return render_template('staff/vehicle_seats.html', vehicle=vehicle, seats_text=seats_text)


@staff_bp.route('/customers')
@login_required
@staff_required
def customers_list():
    # Show passenger profiles derived from bookings, not login accounts
    bookings = Booking.query.order_by(Booking.created_at.desc()).limit(2000).all()
    key_to_passenger = {}
    for b in bookings:
        key = (b.passenger_name or 'Passenger', b.passenger_phone or 'N/A')
        rec = key_to_passenger.get(key)
        if not rec:
            rec = {
                'name': b.passenger_name,
                'phone': b.passenger_phone,
                'num_bookings': 0,
                'last_booking_at': b.created_at,
            }
            key_to_passenger[key] = rec
        rec['num_bookings'] += 1
        if b.created_at and (rec['last_booking_at'] is None or b.created_at > rec['last_booking_at']):
            rec['last_booking_at'] = b.created_at
    passengers = sorted(key_to_passenger.values(), key=lambda r: r['last_booking_at'] or datetime.min, reverse=True)
    return render_template('staff/customers.html', passengers=passengers)


@staff_bp.route('/trips/<int:trip_id>/seats')
@login_required
@staff_required
def trip_seat_map(trip_id: int):
    trip = Trip.query.get_or_404(trip_id)
    seat_layout = trip.vehicle.seat_layout or []
    seat_to_booking = {}
    for b in trip.bookings:
        if b.status in ['confirmed', 'reserved', 'checked_in', 'completed']:
            seat_to_booking[b.seat_number] = b
    return render_template('staff/trip_seats.html', trip=trip, seat_layout=seat_layout, seat_to_booking=seat_to_booking)


@staff_bp.route('/trips/<int:trip_id>/seats/<seat>/checkin', methods=['POST'])
@login_required
@staff_required
def trip_seat_checkin(trip_id: int, seat: str):
    trip = Trip.query.get_or_404(trip_id)
    booking = Booking.query.filter_by(trip_id=trip.id, seat_number=seat).first()
    if not booking:
        flash('No booking found for this seat.', 'warning')
        return redirect(url_for('staff.trip_seat_map', trip_id=trip.id))
    try:
        booking.status = 'checked_in'
        db.session.commit()
        flash('Passenger checked in.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to check in.', 'danger')
    return redirect(url_for('staff.trip_seat_map', trip_id=trip.id))


@staff_bp.route('/trips/<int:trip_id>/mark-full', methods=['POST'])
@login_required
@staff_required
def trip_mark_full(trip_id: int):
    """Mark a trip as full (physical check-ins). Creates bookings for empty seats."""
    import uuid
    trip = Trip.query.get_or_404(trip_id)
    
    # Toggle the is_full flag
    new_state = not trip.is_full
    
    try:
        if new_state:
            # Marking as full - create bookings for all remaining empty seats
            seat_layout = trip.vehicle.seat_layout or []
            all_seats = {s['seat'] for s in seat_layout}
            
            # Get currently booked seats
            booked_seats = {b.seat_number for b in trip.bookings 
                          if b.status in ['confirmed', 'reserved', 'checked_in', 'completed', 'pending_payment']}
            
            # Find empty seats
            empty_seats = all_seats - booked_seats
            
            # Create "walk-in" bookings for empty seats
            for seat in empty_seats:
                ref = f"WI-{uuid.uuid4().hex[:8].upper()}"
                booking = Booking(
                    trip_id=trip.id,
                    user_id=None,  # No user account (physical walk-in)
                    seat_number=seat,
                    status='checked_in',
                    fare=trip.base_fare,
                    reference=ref,
                    hold_expires_at=None,
                    passenger_name='Walk-in Passenger',
                    passenger_sex='other',
                    passenger_age=0,
                    passenger_phone='N/A',
                    passenger_id_number='N/A',
                    pickup_location=None
                )
                db.session.add(booking)
            
            trip.is_full = True
            db.session.commit()
            flash(f'Trip marked as full. {len(empty_seats)} walk-in passenger(s) added.', 'success')
        else:
            # Unmarking - just toggle the flag (keep bookings)
            trip.is_full = False
            db.session.commit()
            flash('Trip unmarked as full. Existing bookings retained.', 'info')
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to mark trip {trip_id} as full: {e}')
        flash('Failed to update trip.', 'danger')
    
    return redirect(url_for('staff.trip_seat_map', trip_id=trip.id))


# JSON endpoint to fetch booking details for a specific seat on a trip
@staff_bp.route('/trips/<int:trip_id>/seats/<seat>/booking.json')
@login_required
@staff_required
def trip_seat_booking_json(trip_id: int, seat: str):
    trip = Trip.query.get_or_404(trip_id)
    booking = Booking.query.filter_by(trip_id=trip.id, seat_number=seat).first()
    if not booking:
        return jsonify({'found': False}), 404
    b = booking.to_dict()
    # Attach trip-level details under the booking object for simpler client usage
    b['route'] = f"{trip.route.origin.town} → {trip.route.destination.town}"
    b['depart_at'] = trip.depart_at.isoformat() if trip.depart_at else None
    b['vehicle_plate'] = getattr(trip.vehicle, 'plate_no', None)
    b['vehicle_make'] = getattr(trip.vehicle, 'make', None)
    b['vehicle_model'] = getattr(trip.vehicle, 'model', None)
    b['driver_name'] = getattr(trip, 'driver_name', None)
    b['driver_phone'] = getattr(trip, 'driver_phone', None)
    return jsonify({'found': True, 'booking': b})


# ============================================================================
# STAFF BOOKING - Create bookings for walk-in customers
# ============================================================================

@staff_bp.route('/trips/<int:trip_id>/seats/<seat>/book', methods=['POST'])
@login_required
@staff_required
def trip_seat_book(trip_id: int, seat: str):
    """Staff creates a booking for a walk-in customer on a specific seat"""
    import uuid
    trip = Trip.query.get_or_404(trip_id)
    
    # Check if seat is already booked
    existing = Booking.query.filter_by(trip_id=trip.id, seat_number=seat).first()
    if existing and existing.status not in ['cancelled']:
        return jsonify({'success': False, 'message': 'Seat is already booked'}), 400
    
    # Get form data
    passenger_name = request.form.get('passenger_name', '').strip()
    passenger_phone = request.form.get('passenger_phone', '').strip()
    passenger_sex = request.form.get('passenger_sex', 'other')
    passenger_age = request.form.get('passenger_age', type=int) or 18
    passenger_id_number = request.form.get('passenger_id_number', '').strip() or 'N/A'
    pickup_location = request.form.get('pickup_location', '').strip() or None
    payment_method = request.form.get('payment_method', 'cash')
    
    if not passenger_name or not passenger_phone:
        return jsonify({'success': False, 'message': 'Name and phone are required'}), 400
    
    try:
        # Generate reference
        ref = f"ST-{uuid.uuid4().hex[:8].upper()}"
        
        # Create booking
        booking = Booking(
            trip_id=trip.id,
            user_id=None,  # No user account (staff booking)
            seat_number=seat,
            status='confirmed' if payment_method == 'cash' else 'pending_payment',
            fare=trip.base_fare,
            reference=ref,
            hold_expires_at=None,
            passenger_name=passenger_name,
            passenger_sex=passenger_sex,
            passenger_age=passenger_age,
            passenger_phone=passenger_phone,
            passenger_id_number=passenger_id_number,
            pickup_location=pickup_location
        )
        db.session.add(booking)
        db.session.commit()
        
        # Create payment record
        from maua.payment.models import Payment
        payment = Payment(
            amount=float(trip.base_fare),
            payment_method=payment_method,
            status='completed' if payment_method == 'cash' else 'pending',
            user_id=current_user.id,
            booking_id=booking.id
        )
        db.session.add(payment)
        db.session.commit()
        
        # Send SMS notification to passenger
        try:
            msg = (
                f"Maua Shark: Booking confirmed! Ref: {ref}. "
                f"Seat {seat} on {trip.route.origin.town} → {trip.route.destination.town}, "
                f"{trip.depart_at.strftime('%b %d at %H:%M')}. "
                f"Fare: KES {trip.base_fare}. Safe travels!"
            )
            send_sms(passenger_phone, msg)
        except Exception as e:
            current_app.logger.error(f'Failed to send booking SMS: {e}')
        
        return jsonify({
            'success': True, 
            'message': f'Booking created! Reference: {ref}',
            'reference': ref,
            'booking_id': booking.id
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Failed to create staff booking: {e}')
        return jsonify({'success': False, 'message': 'Failed to create booking'}), 500


@staff_bp.route('/bookings/quick')
@login_required
@staff_required
def bookings_quick():
    """Quick booking page - shows available trips for immediate booking"""
    # Get active trips with available seats
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    
    trips = Trip.query.filter(
        Trip.status.in_(['scheduled', 'in_progress']),
        Trip.depart_at >= now - timedelta(hours=1)  # Include trips departing in the last hour
    ).order_by(Trip.depart_at.asc()).limit(50).all()
    
    # Calculate available seats for each trip
    trip_data = []
    for trip in trips:
        seat_layout = trip.vehicle.seat_layout or []
        total_seats = len(seat_layout)
        booked_seats = len([b for b in trip.bookings if b.status in ['confirmed', 'reserved', 'checked_in', 'completed', 'pending_payment']])
        available = total_seats - booked_seats
        
        trip_data.append({
            'trip': trip,
            'total_seats': total_seats,
            'booked_seats': booked_seats,
            'available_seats': available
        })
    
    return render_template('staff/bookings_quick.html', trip_data=trip_data)


# ============================================================================
# PARCEL MANAGEMENT - Staff creates parcels, customers only track
# ============================================================================

@staff_bp.route('/parcels/create', methods=['GET', 'POST'])
@login_required
@staff_required
def parcels_create():
    """Staff creates parcels on behalf of customers at the depot"""
    if request.method == 'POST':
        sender_name = request.form.get('sender_name')
        sender_phone = request.form.get('sender_phone')
        sender_email = request.form.get('sender_email', '').strip() or None
        sender_id_number = request.form.get('sender_id_number')
        receiver_name = request.form.get('receiver_name')
        receiver_phone = request.form.get('receiver_phone')
        receiver_email = request.form.get('receiver_email', '').strip() or None
        receiver_id_number = request.form.get('receiver_id_number')
        origin_name = request.form.get('origin_name')
        destination_name = request.form.get('destination_name')
        weight_kg = request.form.get('weight_kg', type=float)
        price = request.form.get('price')
        payment_method = request.form.get('payment_method', 'cash')  # cash or mpesa

        # Handle photo upload
        photo_filename = None
        file = request.files.get('parcel_photo')
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'parcels')
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            photo_filename = filename

        ref_code = f"P{int(datetime.utcnow().timestamp())}"
        
        # Staff creates parcel - can mark as paid immediately for cash payments
        parcel = Parcel(
            ref_code=ref_code,
            sender_name=sender_name,
            sender_phone=sender_phone,
            sender_email=sender_email,
            sender_id_number=sender_id_number or 'N/A',
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            receiver_email=receiver_email,
            receiver_id_number=receiver_id_number or 'N/A',
            origin_name=origin_name,
            destination_name=destination_name,
            weight_kg=weight_kg,
            price=price,
            created_by=current_user.id,
            photo_filename=photo_filename,
            status="pending" if payment_method == 'cash' else "pending_payment",
            payment_status="paid" if payment_method == 'cash' else "pending"
        )
        db.session.add(parcel)
        db.session.commit()
        
        # Create payment record
        from maua.payment.models import Payment
        payment = Payment(
            amount=float(price),
            payment_method=payment_method,
            status='completed' if payment_method == 'cash' else 'pending',
            user_id=current_user.id,
            parcel_id=parcel.id
        )
        db.session.add(payment)
        db.session.commit()
        
        # Handle M-Pesa payment - send STK push to sender's phone
        if payment_method == 'mpesa':
            try:
                from maua.payment.mpesa_service import MpesaService
                from maua.notifications.sms import normalize_phone
                
                # Initialize M-Pesa service
                mpesa_service = MpesaService()
                
                # Use sender's phone number for STK push
                stk_phone = normalize_phone(sender_phone)
                
                # Generate account reference
                account_reference = f"PARCEL-{parcel.id}"
                transaction_desc = f"Parcel {ref_code} from {origin_name} to {destination_name}"
                
                # Initiate STK push to sender's phone
                stk_response = mpesa_service.initiate_stk_push(
                    phone_number=stk_phone,
                    amount=float(price),
                    account_reference=account_reference,
                    transaction_desc=transaction_desc
                )
                
                if stk_response['success']:
                    # Update payment with checkout request ID
                    payment.payment_method = 'mpesa_stk'
                    payment.transaction_id = stk_response.get('checkout_request_id')
                    db.session.commit()
                    
                    flash(f'Parcel {ref_code} created! M-Pesa payment request sent to {sender_phone}. '
                          f'Customer should check their phone to complete payment.', 'info')
                    
                    # Redirect to payment status page
                    return redirect(url_for('staff.parcels_payment_status', parcel_id=parcel.id))
                else:
                    flash(f'Parcel {ref_code} created but M-Pesa request failed: {stk_response.get("message")}. '
                          f'Customer can pay later.', 'warning')
                    
            except Exception as e:
                current_app.logger.error(f'M-Pesa STK push failed for parcel {ref_code}: {e}')
                flash(f'Parcel {ref_code} created but M-Pesa request failed. Customer can pay later.', 'warning')
        
        # Send notifications to sender and receiver (SMS + Email if available)
        try:
            NotificationService.notify_parcel_created(parcel)
            current_app.logger.info(f'Parcel creation notifications sent for {ref_code}')
        except Exception as e:
            current_app.logger.error(f'Failed to send parcel notifications: {e}')
            # SMS errors shouldn't block parcel creation
        
        if payment_method == 'cash':
            flash(f'Parcel {ref_code} created and paid successfully!', 'success')
        
        # Redirect to receipt printing
        return redirect(url_for('staff.parcels_receipt', parcel_id=parcel.id))
    
    return render_template('staff/parcels_create.html')


@staff_bp.route('/parcels/<int:parcel_id>/receipt')
@login_required
@staff_required
def parcels_receipt(parcel_id):
    """View parcel receipt - can be printed"""
    parcel = Parcel.query.get_or_404(parcel_id)
    return render_template('staff/parcels_receipt.html', parcel=parcel)


@staff_bp.route('/parcels/<int:parcel_id>/payment-status')
@login_required
@staff_required
def parcels_payment_status(parcel_id):
    """View parcel payment status - for M-Pesa payments"""
    parcel = Parcel.query.get_or_404(parcel_id)
    payment = parcel.payment
    return render_template('staff/parcels_payment_status.html', parcel=parcel, payment=payment)


@staff_bp.route('/parcels/<int:parcel_id>/receipt.pdf')
@login_required
@staff_required
def parcels_receipt_pdf(parcel_id):
    """Generate PDF receipt for parcel"""
    parcel = Parcel.query.get_or_404(parcel_id)
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0d6efd')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#0d6efd')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    story = []
    
    # Header
    story.append(Paragraph("MAUA SHARK SACCO", title_style))
    story.append(Paragraph("Parcel Delivery Receipt", normal_style))
    story.append(Spacer(1, 20))
    
    # Parcel Info
    story.append(Paragraph("PARCEL DETAILS", heading_style))
    
    parcel_data = [
        ['Reference:', parcel.ref_code],
        ['Date:', parcel.created_at.strftime('%B %d, %Y %I:%M %p')],
        ['Route:', f"{parcel.origin_name} → {parcel.destination_name}"],
        ['Weight:', f"{parcel.weight_kg:.1f} kg" if parcel.weight_kg else "N/A"],
        ['Amount:', f"KES {float(parcel.price):.2f}"],
        ['Status:', parcel.status.replace('_', ' ').title()],
    ]
    
    parcel_table = Table(parcel_data, colWidths=[1.5*inch, 4*inch])
    parcel_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(parcel_table)
    story.append(Spacer(1, 15))
    
    # Sender/Receiver
    story.append(Paragraph("SENDER & RECEIVER", heading_style))
    
    contact_data = [
        ['Sender:', parcel.sender_name],
        ['Sender Phone:', parcel.sender_phone],
        ['Sender Email:', parcel.sender_email or 'N/A'],
        ['Sender ID:', parcel.sender_id_number],
        ['', ''],
        ['Receiver:', parcel.receiver_name],
        ['Receiver Phone:', parcel.receiver_phone],
        ['Receiver Email:', parcel.receiver_email or 'N/A'],
        ['Receiver ID:', parcel.receiver_id_number],
    ]
    
    contact_table = Table(contact_data, colWidths=[1.5*inch, 4*inch])
    contact_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(contact_table)
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph("Thank you for choosing Maua Shark Sacco!", normal_style))
    story.append(Paragraph(f"Track your parcel at: mauasharksacco.co.ke/parcels/track?ref={parcel.ref_code}", normal_style))
    
    doc.build(story)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=parcel_{parcel.ref_code}.pdf'
    
    return response

