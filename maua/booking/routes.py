from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, Response, stream_with_context, send_file
from flask_login import login_required, current_user
from maua.extensions import db
from maua.notifications.sms import send_sms
from .models import Booking, Ticket
from .services import broker
from .forms import PassengerDetailsForm
from maua.catalog.models import Trip
from datetime import datetime
from datetime import timedelta
import uuid

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
        # Process seat selection
        seat_number = request.form.get('seat_number')
        if not seat_number:
            flash('Please select a seat.', 'warning')
            return redirect(url_for('booking.book', trip_id=trip_id))
        
        # Check if seat is available (only confirmed/checked_in block selection)
        now = datetime.utcnow()
        booked_seats = {b.seat_number for b in trip.bookings 
                       if b.status in ['confirmed', 'checked_in']}
        
        if seat_number in booked_seats:
            flash('This seat is already taken. Please select another seat.', 'danger')
            return redirect(url_for('booking.book', trip_id=trip_id))
        
        # Redirect to passenger details with seat number
        return redirect(url_for('booking.passenger_details', 
                             trip_id=trip_id, 
                             seat_number=seat_number))
    
    # For GET request, show seat selection
    now = datetime.utcnow()
    booked_seats = {b.seat_number for b in trip.bookings 
                   if b.status in ['confirmed', 'checked_in']}
    seat_layout = trip.vehicle.seat_layout or []
    
    form = PassengerDetailsForm()
    return render_template('booking/select_seat.html',
                         trip=trip,
                         seat_layout=seat_layout,
                         taken=booked_seats,
                         form=form)


@booking_bp.route('/stream/<int:trip_id>')
def stream_trip_seats(trip_id: int):
    q = broker.subscribe(trip_id)

    def event_stream():
        try:
            # Send a comment to keep connection open
            yield ': connected\n\n'
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            pass
        finally:
            broker.unsubscribe(trip_id, q)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return Response(stream_with_context(event_stream()), mimetype='text/event-stream', headers=headers)

@booking_bp.route('/book/<int:trip_id>/passenger', methods=['GET', 'POST'])
@login_required
def passenger_details(trip_id):
    seat_number = request.args.get('seat_number')
    if not seat_number:
        flash('Please select a seat first.', 'warning')
        return redirect(url_for('booking.book', trip_id=trip_id))
    
    trip = Trip.query.get_or_404(trip_id)
    form = PassengerDetailsForm()
    
    # Check if seat is still available (no holds logic)
    now = datetime.utcnow()
    booked_seats = {b.seat_number for b in trip.bookings 
                   if b.status in ['confirmed', 'checked_in']}
    
    if seat_number in booked_seats:
        flash('This seat is no longer available. Please select another seat.', 'danger')
        return redirect(url_for('booking.book', trip_id=trip_id))
    
    # No hold logic: just render form on GET; on POST, attempt to create confirmed booking

    if form.validate_on_submit():
        # Final seat availability check just before confirmation
        exists = Booking.query.filter(
            Booking.trip_id == trip_id,
            Booking.seat_number == seat_number,
            Booking.status.in_(['confirmed','checked_in'])
        ).first()
        if exists:
            flash('This seat has just been taken. Please select another.', 'danger')
            return redirect(url_for('booking.book', trip_id=trip_id))

        booking = Booking(
            trip_id=trip_id,
            user_id=current_user.id,
            seat_number=seat_number,
            status='confirmed',
            fare=trip.base_fare,
            reference=f"BK-{uuid.uuid4().hex[:8].upper()}",
            hold_expires_at=None,
            passenger_name=form.name.data,
            passenger_sex=form.sex.data,
            passenger_age=form.age.data,
            passenger_phone=form.phone.data
        )
        try:
            db.session.add(booking)
            db.session.commit()
            broker.publish(trip_id, {"type": "seat_confirmed", "seat": booking.seat_number, "status": "confirmed"})
            # Create ticket
            ticket = Ticket(booking_id=booking.id, status='confirmed')
            db.session.add(ticket)
            db.session.commit()
            # SMS: Booking confirmation to passenger
            try:
                msg = (
                    f"Maua Shark: Booking confirmed. Ref {booking.reference}. "
                    f"Trip {booking.trip.route.origin.town} -> {booking.trip.route.destination.town} on "
                    f"{booking.trip.depart_at.strftime('%Y-%m-%d %H:%M')}. Seat {booking.seat_number}. "
                    f"Fare KES {booking.fare:.2f}. Thank you!"
                )
                send_sms(booking.passenger_phone, msg, user_email=current_user.email)
            except Exception:
                pass
            flash('Booking confirmed!', 'success')
            return redirect(url_for('booking.booking_confirmation', booking_id=booking.id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating booking: {str(e)}")
            flash('An error occurred while processing your booking. Please try again.', 'danger')
    
    return render_template('booking/passenger_details.html',
                         form=form,
                         trip=trip,
                         seat_number=seat_number)

@booking_bp.route('/confirmation/<int:booking_id>')
@login_required
def booking_confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Ensure the current user owns this booking
    if booking.user_id != current_user.id and not current_user.is_admin:
        flash('You are not authorized to view this booking.', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('booking/booking_confirmation.html', booking=booking)


@booking_bp.route('/receipt/<int:booking_id>.pdf')
@login_required
def download_receipt(booking_id: int):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id and not current_user.is_admin:
        flash('You are not authorized to download this receipt.', 'danger')
        return redirect(url_for('booking.index'))

    # Generate PDF in-memory
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    c.setFillColor(colors.HexColor('#0d6efd'))
    c.rect(0, height-40, width, 40, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(20*mm, height-28, 'MAUA SHARK SACCO - E-Ticket Receipt')

    y = height - 60
    c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20*mm, y, 'Booking Reference:')
    c.setFont('Helvetica', 12)
    c.drawString(65*mm, y, booking.reference)
    y -= 10*mm

    # Passenger
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20*mm, y, 'Passenger')
    y -= 6*mm
    c.setFont('Helvetica', 11)
    c.drawString(22*mm, y, f"Name: {booking.passenger_name}")
    y -= 5*mm
    c.drawString(22*mm, y, f"Phone: {booking.passenger_phone}")
    y -= 5*mm
    c.drawString(22*mm, y, f"Gender: {booking.passenger_sex.title()}  Age: {booking.passenger_age}")
    y -= 8*mm

    # Trip
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20*mm, y, 'Trip')
    y -= 6*mm
    c.setFont('Helvetica', 11)
    c.drawString(22*mm, y, f"Route: {booking.trip.route.origin.town} → {booking.trip.route.destination.town}")
    y -= 5*mm
    c.drawString(22*mm, y, f"Departure: {booking.trip.depart_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 5*mm
    c.drawString(22*mm, y, f"Vehicle: {getattr(booking.trip.vehicle, 'plate_no', 'N/A')}  Seat: {booking.seat_number}")
    y -= 8*mm

    # Fare
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20*mm, y, 'Fare')
    y -= 6*mm
    c.setFont('Helvetica', 11)
    c.drawString(22*mm, y, f"Amount Paid: KES {booking.fare:0.2f}")
    y -= 5*mm
    c.drawString(22*mm, y, f"Status: {booking.status.title()}")
    y -= 12*mm

    # Footer
    c.setFont('Helvetica-Oblique', 9)
    c.setFillColor(colors.grey)
    c.drawString(20*mm, 15*mm, 'Please present this e-ticket and a valid ID during boarding.')
    c.drawString(20*mm, 10*mm, 'Thank you for choosing Maua Shark Sacco.')

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"receipt_{booking.reference}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

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
        broker.publish(booking.trip_id, {"type": "seat_cancelled", "seat": booking.seat_number, "status": "available"})
        flash('Booking has been cancelled.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error cancelling booking. Please try again.', 'danger')
    
    return redirect(url_for('booking.index'))