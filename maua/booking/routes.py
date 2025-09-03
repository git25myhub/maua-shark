from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from maua.extensions import db
from .models import Booking
from maua.catalog.models import Trip
from datetime import datetime

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/')
@login_required
def index():
    # List all bookings for the current user
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('booking/index.html', bookings=bookings)

@booking_bp.route('/book/<int:trip_id>', methods=['GET', 'POST'])
@login_required
def book(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    # Disallow booking for completed or cancelled trips
    if trip.status in ['completed', 'cancelled']:
        flash('This trip is not open for booking.', 'warning')
        return redirect(url_for('catalog.trip_detail', trip_id=trip_id))
    
    if request.method == 'POST':
        # Process booking with validation
        seat_number = request.form.get('seat_number')
        if not seat_number:
            flash('Please select a seat.', 'warning')
            return redirect(url_for('booking.book', trip_id=trip_id))

        # Validate seat availability
        booked_seats = {b.seat_number for b in trip.bookings if b.status in ['confirmed','reserved','checked_in','completed']}
        if seat_number in booked_seats:
            flash('Seat already taken. Choose another.', 'danger')
            return redirect(url_for('catalog.trip_detail', trip_id=trip_id))

        # Determine fare from trip base_fare
        fare = trip.base_fare

        booking = Booking(
            trip_id=trip_id,
            user_id=current_user.id,
            seat_number=seat_number,
            status='confirmed',
            fare=fare,
            reference=f"BK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )

        try:
            db.session.add(booking)
            db.session.commit()
            flash('Booking successful!', 'success')
            return redirect(url_for('booking.index'))
        except Exception:
            db.session.rollback()
            flash('Error creating booking. Please try again.', 'danger')

    # For GET request, show seat picker
    # Build seat layout and taken seats to render picker
    seat_layout = trip.vehicle.seat_layout or []
    taken = {b.seat_number for b in trip.bookings if b.status in ['confirmed','reserved','checked_in','completed']}
    return render_template('booking/select_seat.html', trip=trip, seat_layout=seat_layout, taken=taken)

@booking_bp.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Ensure the current user owns this booking
    if booking.user_id != current_user.id:
        flash('You are not authorized to cancel this booking.', 'danger')
        return redirect(url_for('booking.index'))
    
    try:
        booking.status = 'cancelled'
        db.session.commit()
        flash('Booking has been cancelled.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error cancelling booking. Please try again.', 'danger')
    
    return redirect(url_for('booking.index'))