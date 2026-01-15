from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, Response, stream_with_context, send_file
from flask_login import login_required, current_user
from maua.extensions import db
from maua.notifications.sms import send_sms
from maua.payment.cache import PaymentStatusCache
from .models import Booking, BookingSeat, Ticket
from .services import broker
from .forms import PassengerDetailsForm
from maua.catalog.models import Trip
from datetime import datetime, timedelta
import uuid

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/')
def index():
    # Redirect to catalog - customers no longer need to login to view bookings
    # They can track by reference instead
    return redirect(url_for('catalog.routes'))

@booking_bp.route('/book/<int:trip_id>', methods=['GET', 'POST'])
def book(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Disallow booking for completed, cancelled, or full trips
    if trip.status in ['completed', 'cancelled']:
        flash('This trip is not open for booking.', 'warning')
        return redirect(url_for('catalog.trip_detail', trip_id=trip_id))
    
    if trip.is_full:
        flash('This trip is full. Please select another trip.', 'warning')
        return redirect(url_for('catalog.routes'))
    
    if request.method == 'POST':
        # Process seat selection - support multiple seats
        seat_numbers = request.form.getlist('seat_number')  # Get list of selected seats
        if not seat_numbers:
            flash('Please select at least one seat.', 'warning')
            return redirect(url_for('booking.book', trip_id=trip_id))
        
        # Remove duplicates and validate
        seat_numbers = list(set(seat_numbers))
        
        # Check if all seats are available
        now = datetime.utcnow()
        # Get booked seats from both old format (seat_number) and new format (BookingSeat)
        booked_seats = set()
        for b in trip.bookings:
            if b.status in ['pending_payment', 'confirmed', 'checked_in']:
                # Check old format
                if b.seat_number:
                    booked_seats.add(b.seat_number)
                # Check new format (BookingSeat)
                for bs in b.booking_seats:
                    booked_seats.add(bs.seat_number)
        
        # Also check BookingSeat directly (in case of orphaned records)
        for bs in BookingSeat.query.filter_by(trip_id=trip_id).all():
            booking = Booking.query.get(bs.booking_id)
            if booking and booking.status in ['pending_payment', 'confirmed', 'checked_in']:
                booked_seats.add(bs.seat_number)
        
        unavailable = [seat for seat in seat_numbers if seat in booked_seats]
        if unavailable:
            flash(f'Seat(s) {", ".join(unavailable)} are already taken. Please select other seats.', 'danger')
            return redirect(url_for('booking.book', trip_id=trip_id))
        
        # Redirect to passenger details with seat numbers (comma-separated)
        seat_numbers_str = ','.join(seat_numbers)
        return redirect(url_for('booking.passenger_details', 
                             trip_id=trip_id, 
                             seat_numbers=seat_numbers_str))
    
    # For GET request, show seat selection
    now = datetime.utcnow()
    # Get booked seats from both old format (seat_number) and new format (BookingSeat)
    booked_seats = set()
    for b in trip.bookings:
        if b.status in ['pending_payment', 'confirmed', 'checked_in']:
            # Check old format
            if b.seat_number:
                booked_seats.add(b.seat_number)
            # Check new format (BookingSeat)
            for bs in b.booking_seats:
                booked_seats.add(bs.seat_number)
    
    # Also check BookingSeat directly
    for bs in BookingSeat.query.filter_by(trip_id=trip_id).all():
        booking = Booking.query.get(bs.booking_id)
        if booking and booking.status in ['pending_payment', 'confirmed', 'checked_in']:
            booked_seats.add(bs.seat_number)
    
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
def passenger_details(trip_id):
    seat_numbers_str = request.args.get('seat_numbers') or request.args.get('seat_number')  # Support both formats
    if not seat_numbers_str:
        flash('Please select at least one seat first.', 'warning')
        return redirect(url_for('booking.book', trip_id=trip_id))
    
    # Parse seat numbers (comma-separated or single)
    seat_numbers = [s.strip() for s in seat_numbers_str.split(',') if s.strip()]
    if not seat_numbers:
        flash('Please select at least one seat first.', 'warning')
        return redirect(url_for('booking.book', trip_id=trip_id))
    
    trip = Trip.query.get_or_404(trip_id)
    form = PassengerDetailsForm()
    
    # Check if all seats are still available
    now = datetime.utcnow()
    booked_seats = set()
    for b in trip.bookings:
        if b.status in ['pending_payment', 'confirmed', 'checked_in']:
            if b.seat_number:
                booked_seats.add(b.seat_number)
            for bs in b.booking_seats:
                booked_seats.add(bs.seat_number)
    
    for bs in BookingSeat.query.filter_by(trip_id=trip_id).all():
        booking = Booking.query.get(bs.booking_id)
        if booking and booking.status in ['pending_payment', 'confirmed', 'checked_in']:
            booked_seats.add(bs.seat_number)
    
    unavailable = [seat for seat in seat_numbers if seat in booked_seats]
    if unavailable:
        flash(f'Seat(s) {", ".join(unavailable)} are no longer available. Please select other seats.', 'danger')
        return redirect(url_for('booking.book', trip_id=trip_id))

    if form.validate_on_submit():
        # Clean up expired pending_payment bookings (older than 10 minutes)
        expired_cutoff = datetime.utcnow() - timedelta(minutes=10)
        expired_bookings = Booking.query.filter(
            Booking.status == 'pending_payment',
            Booking.created_at < expired_cutoff
        ).all()
        for booking in expired_bookings:
            # Also delete associated BookingSeat records
            BookingSeat.query.filter_by(booking_id=booking.id).delete()
            db.session.delete(booking)
        db.session.commit()
        
        # Final seat availability check just before confirmation
        booked_seats_final = set()
        for b in trip.bookings:
            if b.status in ['pending_payment', 'confirmed', 'checked_in']:
                if b.seat_number:
                    booked_seats_final.add(b.seat_number)
                for bs in b.booking_seats:
                    booked_seats_final.add(bs.seat_number)
        
        for bs in BookingSeat.query.filter_by(trip_id=trip_id).all():
            booking = Booking.query.get(bs.booking_id)
            if booking and booking.status in ['pending_payment', 'confirmed', 'checked_in']:
                booked_seats_final.add(bs.seat_number)
        
        unavailable_final = [seat for seat in seat_numbers if seat in booked_seats_final]
        if unavailable_final:
            flash(f'Seat(s) {", ".join(unavailable_final)} have just been taken. Please select other seats.', 'danger')
            return redirect(url_for('booking.book', trip_id=trip_id))

        # Calculate total fare
        total_fare = trip.base_fare * len(seat_numbers)

        # Create booking with pending status (requires payment)
        # No login required - user_id is optional
        booking = Booking(
            trip_id=trip_id,
            user_id=None,  # No login required for customers
            seat_number=None,  # No longer used for multi-seat bookings
            status='pending_payment',
            fare=total_fare,  # Total fare for all seats
            reference=f"BK-{uuid.uuid4().hex[:8].upper()}",
            hold_expires_at=None,
            passenger_name=form.name.data,
            passenger_sex=form.sex.data,
            passenger_age=form.age.data,
            passenger_phone=form.phone.data,
            passenger_email=form.email.data,  # Store email for notifications
            passenger_id_number=form.id_number.data,
            pickup_location=form.pickup_location.data or None
        )
        try:
            db.session.add(booking)
            db.session.flush()  # Get booking.id
            
            # Create BookingSeat records for each selected seat
            for seat_num in seat_numbers:
                booking_seat = BookingSeat(
                    booking_id=booking.id,
                    trip_id=trip_id,
                    seat_number=seat_num
                )
                db.session.add(booking_seat)
            
            db.session.commit()
            
            # Create payment record
            from maua.payment.models import Payment
            payment = Payment(
                amount=total_fare,
                payment_method='pending',
                status='pending',
                user_id=None,  # No login required - user_id is optional
                booking_id=booking.id
            )
            db.session.add(payment)
            db.session.commit()
            
            # Publish seat events for each seat
            for seat_num in seat_numbers:
                broker.publish(trip_id, {"type": "seat_confirmed", "seat": seat_num, "status": "booked"})
            
            # Redirect to payment page
            return redirect(url_for('booking.payment', booking_id=booking.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating booking: {str(e)}")
            flash('An error occurred while processing your booking. Please try again.', 'danger')
    
    return render_template('booking/passenger_details.html',
                         form=form,
                         trip=trip,
                         seat_numbers=seat_numbers,
                         seat_number=', '.join(seat_numbers))  # For backward compatibility in template

@booking_bp.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    """Handle payment for booking - no login required"""
    booking = Booking.query.get_or_404(booking_id)
    
    # No authentication check - anyone with booking_id can access payment
    
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
def payment_status(booking_id):
    """Check payment status - no login required"""
    booking = Booking.query.get_or_404(booking_id)
    
    # No authentication check - anyone with booking_id can check status
    
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
def booking_confirmation(booking_id):
    """View booking confirmation - no login required"""
    booking = Booking.query.get_or_404(booking_id)
    
    # No authentication check - anyone with booking_id can view confirmation
    
    return render_template('booking/booking_confirmation.html', booking=booking)


@booking_bp.route('/receipt/<int:booking_id>.pdf')
def download_receipt(booking_id: int):
    """Download booking receipt - no login required"""
    booking = Booking.query.get_or_404(booking_id)
    # No authentication check - anyone with booking_id can download receipt

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
    c.drawString(20*mm, height-28, 'MAUA SHARK EXPRESS - E-Ticket Receipt')

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
    seats_str = ', '.join(booking.seats) if booking.seats else (booking.seat_number or 'N/A')
    c.drawString(22*mm, y, f"Vehicle: {getattr(booking.trip.vehicle, 'plate_no', 'N/A')}  Seat{'s' if booking.seat_count > 1 else ''}: {seats_str}")
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
    c.drawString(20*mm, 10*mm, 'Thank you for choosing Maua Shark Express.')

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"receipt_{booking.reference}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@booking_bp.route('/cancel/<int:booking_id>', methods=['POST'])
def cancel(booking_id):
    """Cancel booking - no login required"""
    booking = Booking.query.get_or_404(booking_id)
    
    # No authentication check - anyone with booking_id can cancel (if status allows)
    
    try:
        booking.status = 'cancelled'
        db.session.commit()
        # Publish cancellation events for all seats
        for seat_num in booking.seats:
            broker.publish(booking.trip_id, {"type": "seat_cancelled", "seat": seat_num, "status": "available"})
        
        # Send cancellation notification
        try:
            from maua.notifications.notification_service import NotificationService
            NotificationService.notify_booking_cancelled(booking)
        except Exception:
            pass  # Don't fail if notification fails
        
        flash('Booking has been cancelled.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error cancelling booking. Please try again.', 'danger')
    
    return redirect(url_for('booking.index'))