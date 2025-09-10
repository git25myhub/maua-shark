from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, Response, stream_with_context, send_file
from flask_login import login_required, current_user
from maua.extensions import db
from maua.notifications.sms import send_sms
from maua.payment.cache import PaymentStatusCache
from .models import Booking, Ticket
from .services import broker
from .forms import PassengerDetailsForm
from maua.catalog.models import Trip
from datetime import datetime, timedelta
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
        
        # Check if seat is available (any active booking blocks selection)
        now = datetime.utcnow()
        booked_seats = {b.seat_number for b in trip.bookings 
                       if b.status in ['pending_payment', 'confirmed', 'checked_in']}
        
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
                   if b.status in ['pending_payment', 'confirmed', 'checked_in']}
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
                   if b.status in ['pending_payment', 'confirmed', 'checked_in']}
    
    if seat_number in booked_seats:
        flash('This seat is no longer available. Please select another seat.', 'danger')
        return redirect(url_for('booking.book', trip_id=trip_id))
    
    # No hold logic: just render form on GET; on POST, attempt to create confirmed booking

    if form.validate_on_submit():
        # Clean up expired pending_payment bookings (older than 10 minutes)
        expired_cutoff = datetime.utcnow() - timedelta(minutes=10)
        expired_bookings = Booking.query.filter(
            Booking.status == 'pending_payment',
            Booking.created_at < expired_cutoff
        ).all()
        for booking in expired_bookings:
            db.session.delete(booking)
        db.session.commit()
        
        # Final seat availability check just before confirmation
        exists = Booking.query.filter(
            Booking.trip_id == trip_id,
            Booking.seat_number == seat_number,
            Booking.status.in_(['pending_payment', 'confirmed', 'checked_in'])
        ).first()
        if exists:
            flash('This seat has just been taken. Please select another.', 'danger')
            return redirect(url_for('booking.book', trip_id=trip_id))

        # Create booking with pending status (requires payment)
        booking = Booking(
            trip_id=trip_id,
            user_id=current_user.id,
            seat_number=seat_number,
            status='pending_payment',  # Changed from 'confirmed' to 'pending_payment'
            fare=trip.base_fare,
            reference=f"BK-{uuid.uuid4().hex[:8].upper()}",
            hold_expires_at=None,
            passenger_name=form.name.data,
            passenger_sex=form.sex.data,
            passenger_age=form.age.data,
            passenger_phone=form.phone.data,
            passenger_id_number=form.id_number.data,
            pickup_location=form.pickup_location.data or None
        )
        try:
            db.session.add(booking)
            db.session.commit()
            
            # Create payment record
            from maua.payment.models import Payment
            payment = Payment(
                amount=trip.base_fare,
                payment_method='pending',
                status='pending',
                user_id=current_user.id,
                booking_id=booking.id
            )
            db.session.add(payment)
            db.session.commit()
            
            # Redirect to payment page
            return redirect(url_for('booking.payment', booking_id=booking.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating booking: {str(e)}")
            flash('An error occurred while processing your booking. Please try again.', 'danger')
    
    return render_template('booking/passenger_details.html',
                         form=form,
                         trip=trip,
                         seat_number=seat_number)

@booking_bp.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def payment(booking_id):
    """Handle payment for booking"""
    booking = Booking.query.get_or_404(booking_id)
    
    # Ensure user owns this booking
    if booking.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('booking.index'))
    
    # Check if booking is in pending payment status
    if booking.status != 'pending_payment':
        flash('This booking is not pending payment.', 'warning')
        return redirect(url_for('booking.booking_confirmation', booking_id=booking_id))
    
    # Get the payment record
    payment = booking.payment
    if not payment:
        flash('Payment record not found.', 'danger')
        return redirect(url_for('booking.index'))
    
    if request.method == 'POST':
        # Handle payment form submission
        phone = request.form.get('phone')
        if not phone:
            flash('Phone number is required.', 'danger')
            return redirect(url_for('booking.payment', booking_id=booking_id))
        
        # Process M-Pesa STK push directly
        try:
            from maua.payment.mpesa_service import MpesaService
            
            # Initialize M-Pesa service
            mpesa_service = MpesaService()
            
            # Generate account reference
            account_reference = f"BOOKING-{payment.id}"
            transaction_desc = f"Booking payment for {booking.reference}"
            
            # Initiate STK push
            stk_response = mpesa_service.initiate_stk_push(
                phone_number=phone,
                amount=float(payment.amount),
                account_reference=account_reference,
                transaction_desc=transaction_desc
            )
            
            if stk_response['success']:
                # Update payment with checkout request ID
                payment.payment_method = 'mpesa_stk'
                payment.transaction_id = stk_response.get('checkout_request_id')
                payment.status = 'pending'
                db.session.commit()
                
                flash('Payment request sent to your phone. Please check your M-Pesa app.', 'info')
                return redirect(url_for('booking.payment_status', booking_id=booking_id))
            else:
                flash(f'Payment failed: {stk_response.get("message", "Unknown error")}', 'danger')
                
        except Exception as e:
            current_app.logger.error(f"Payment request error: {str(e)}")
            flash('Payment request failed. Please try again.', 'danger')
    
    return render_template('booking/payment.html', 
                         booking=booking, 
                         payment=payment,
                         trip=booking.trip)

@booking_bp.route('/payment/status/<int:booking_id>')
@login_required
def payment_status(booking_id):
    """Check payment status"""
    booking = Booking.query.get_or_404(booking_id)
    
    # Ensure user owns this booking
    if booking.user_id != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('booking.index'))
    
    # Get the payment record
    payment = booking.payment
    if not payment:
        flash('Payment record not found.', 'danger')
        return redirect(url_for('booking.index'))
    
    # Pull a friendly failure message from cache if present
    cached = PaymentStatusCache.get_status(payment.id)
    failure_message = None
    if cached and cached.get('status') == 'failed':
        failure_message = cached.get('message')
    
    return render_template('booking/payment_status.html', 
                         booking=booking, 
                         payment=payment,
                         trip=booking.trip,
                         failure_message=failure_message)

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
    c.drawString(22*mm, y, f"National ID: {booking.passenger_id_number}")
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