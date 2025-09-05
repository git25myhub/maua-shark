from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from maua.extensions import db
from . import staff_bp
from maua.booking.models import Booking
from maua.catalog.models import Trip, Vehicle, Route
from maua.parcels.models import Parcel
from datetime import datetime
from maua.booking.models import Booking
from maua.notifications.sms import send_sms


def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_admin):
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


@staff_bp.route('/bookings')
@login_required
@staff_required
def bookings_list():
    status = request.args.get('status')
    query = Booking.query.order_by(Booking.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    bookings = query.limit(200).all()
    return render_template('staff/bookings.html', bookings=bookings)


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
        try:
            depart_dt = datetime.fromisoformat(depart_at)
            trip = Trip(route_id=route_id, vehicle_id=vehicle_id, depart_at=depart_dt, base_fare=base_fare, status='scheduled')
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
        flash('Trip status updated.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update trip.', 'danger')
    return redirect(url_for('staff.trips_list'))


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


