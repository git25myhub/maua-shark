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
    return render_template('staff/dashboard.html', booking_count=booking_count, parcel_count=parcel_count, active_trips=active_trips)


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
        # SMS: If checked in or completed, notify passenger
        try:
            if new_status == 'checked_in':
                msg = (
                    f"Maua Shark: Thank you {booking.passenger_name} for boarding. "
                    f"Trip {booking.trip.route.origin.town}->{booking.trip.route.destination.town}. "
                    f"Seat {booking.seat_number}. We wish you a safe journey."
                )
                # Get user email from booking if available
                user_email = booking.user.email if booking.user and hasattr(booking.user, 'email') else None
                send_sms(booking.passenger_phone, msg, user_email=user_email)
            elif new_status == 'completed':
                msg = (
                    f"Maua Shark: Trip completed. Thank you for traveling with us, {booking.passenger_name}. "
                    f"We appreciate you and welcome you to ride with MAUA SHARK again."
                )
                # Get user email from booking if available
                user_email = booking.user.email if booking.user and hasattr(booking.user, 'email') else None
                send_sms(booking.passenger_phone, msg, user_email=user_email)
        except Exception:
            pass
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
        # SMS: Notify sender/receiver on parcel status changes
        try:
            # Get user email from parcel creator if available
            user_email = None
            if parcel.created_by:
                from maua.auth.models import User
                user = User.query.get(parcel.created_by)
                if user and hasattr(user, 'email'):
                    user_email = user.email
            
            if new_status == 'pending':
                msg = (
                    f"Maua Shark: Parcel {parcel.ref_code} is pending dispatch from {parcel.origin_name}."
                )
                send_sms(parcel.sender_phone, msg, user_email=user_email)
            elif new_status == 'in_transit':
                msg_sender = (
                    f"Maua Shark: Parcel {parcel.ref_code} now in transit to {parcel.destination_name}."
                )
                msg_receiver = (
                    f"Maua Shark: You will receive parcel {parcel.ref_code} from {parcel.sender_name}. "
                    f"It is now in transit to {parcel.destination_name}."
                )
                send_sms(parcel.sender_phone, msg_sender, user_email=user_email)
                send_sms(parcel.receiver_phone, msg_receiver, user_email=user_email)
            elif new_status == 'delivered':
                msg_sender = (
                    f"Maua Shark: Parcel {parcel.ref_code} delivered to {parcel.receiver_name}. Thank you!"
                )
                msg_receiver = (
                    f"Maua Shark: Parcel {parcel.ref_code} received. Thank you for choosing Maua Shark."
                )
                send_sms(parcel.sender_phone, msg_sender, user_email=user_email)
                send_sms(parcel.receiver_phone, msg_receiver, user_email=user_email)
        except Exception:
            pass
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
    driver_phone = request.form.get('driver_phone')
    if not any([tracking_number, vehicle_plate, driver_phone]):
        flash('Provide vehicle plate/driver phone (or tracking number).', 'danger')
        return redirect(url_for('staff.parcels_list'))
    try:
        if tracking_number:
            parcel.tracking_number = tracking_number
        if vehicle_plate:
            parcel.vehicle_plate = vehicle_plate
        if driver_phone:
            parcel.driver_phone = driver_phone
        db.session.commit()
        # Notify customer of vehicle assignment
        try:
            details = []
            if parcel.vehicle_plate:
                details.append(f"Vehicle {parcel.vehicle_plate}")
            if parcel.driver_phone:
                details.append(f"Driver {parcel.driver_phone}")
            if details:
                info = ", ".join(details)
                msg_sender = (
                    f"Maua Shark: Parcel {parcel.ref_code} assigned to {info}. Track with your reference code."
                )
                user_email = None
                if parcel.created_by:
                    from maua.auth.models import User
                    u = User.query.get(parcel.created_by)
                    if u and hasattr(u, 'email'):
                        user_email = u.email
                send_sms(parcel.sender_phone, msg_sender, user_email=user_email)
                # Inform receiver as well
                try:
                    send_sms(parcel.receiver_phone, msg_sender, user_email=user_email)
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
        sender_id_number = request.form.get('sender_id_number')
        receiver_name = request.form.get('receiver_name')
        receiver_phone = request.form.get('receiver_phone')
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
            sender_id_number=sender_id_number or 'N/A',
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
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
        
        # Send SMS notification to sender and receiver
        try:
            sender_msg = (
                f"Maua Shark: Your parcel {ref_code} has been registered. "
                f"From {origin_name} to {destination_name}. "
                f"Receiver: {receiver_name}. Amount: KES {price}"
            )
            send_sms(sender_phone, sender_msg, user_email=None)
            
            receiver_msg = (
                f"Maua Shark: A parcel {ref_code} is coming to you from {sender_name}. "
                f"Track at our website using ref: {ref_code}"
            )
            send_sms(receiver_phone, receiver_msg, user_email=None)
        except Exception:
            pass  # SMS errors shouldn't block parcel creation
        
        flash(f'Parcel {ref_code} created successfully!', 'success')
        
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
        ['Sender ID:', parcel.sender_id_number],
        ['', ''],
        ['Receiver:', parcel.receiver_name],
        ['Receiver Phone:', parcel.receiver_phone],
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

