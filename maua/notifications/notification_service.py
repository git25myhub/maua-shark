"""
Comprehensive Notification Service for MAUA SHARK SACCO
Handles SMS and Email notifications for bookings and parcels
"""

import logging
from typing import Optional
from datetime import datetime
from flask import current_app, render_template_string

logger = logging.getLogger(__name__)


# =============================================================================
# SMS MESSAGE TEMPLATES
# =============================================================================

SMS_TEMPLATES = {
    # BOOKING MESSAGES
    'booking_confirmed': (
        "MAUA SHARK SACCO: Dear {passenger_name}, your booking {reference} is CONFIRMED! "
        "Route: {origin} to {destination}. Date: {date} at {time}. "
        "Seat: {seat_number}. Vehicle: {vehicle}. Fare: KES {fare}. "
        "Please arrive 30 mins early. Safe travels!"
    ),
    
    'booking_payment_received': (
        "MAUA SHARK: Payment of KES {amount} received for booking {reference}. "
        "Your seat {seat_number} is now confirmed on {route} departing {date} at {time}. "
        "Thank you for choosing Maua Shark Sacco!"
    ),
    
    'booking_reminder': (
        "MAUA SHARK REMINDER: Dear {passenger_name}, your trip from {origin} to {destination} "
        "is TOMORROW at {time}. Vehicle: {vehicle}, Seat: {seat_number}. "
        "Please arrive at the departure point 30 minutes early with valid ID. Safe journey!"
    ),
    
    'booking_checked_in': (
        "MAUA SHARK: Thank you {passenger_name} for checking in! "
        "Trip: {origin} to {destination}. Seat {seat_number}. "
        "We wish you a safe and comfortable journey!"
    ),
    
    'booking_completed': (
        "MAUA SHARK: Trip completed! Thank you for traveling with us, {passenger_name}. "
        "We hope you had a pleasant journey from {origin} to {destination}. "
        "We appreciate your patronage and look forward to serving you again soon!"
    ),
    
    'booking_cancelled': (
        "MAUA SHARK: Your booking {reference} has been cancelled. "
        "If you paid, a refund will be processed within 24-48 hours. "
        "Contact us for any questions. Thank you!"
    ),
    
    # PARCEL MESSAGES
    'parcel_created': (
        "MAUA SHARK: Parcel {ref_code} registered! From: {origin} to {destination}. "
        "Receiver: {receiver_name}. Amount: KES {price}. "
        "Track your parcel at our website using ref: {ref_code}"
    ),
    
    'parcel_receiver_notification': (
        "MAUA SHARK: Hello {receiver_name}! A parcel {ref_code} is being sent to you by {sender_name}. "
        "From: {origin} to {destination}. "
        "Track status at our website using ref: {ref_code}"
    ),
    
    'parcel_payment_confirmed': (
        "MAUA SHARK: Payment of KES {price} confirmed for parcel {ref_code}. "
        "Your parcel from {origin} to {destination} will be dispatched soon. "
        "Track at our website with ref: {ref_code}"
    ),
    
    'parcel_in_transit': (
        "MAUA SHARK: Parcel {ref_code} is now IN TRANSIT to {destination}. "
        "Vehicle: {vehicle}. Driver: {driver_name} ({driver_phone}). "
        "Estimated arrival will be communicated. Thank you!"
    ),
    
    'parcel_in_transit_receiver': (
        "MAUA SHARK: Hello {receiver_name}! Parcel {ref_code} from {sender_name} "
        "is now IN TRANSIT to {destination}. Driver: {driver_name} ({driver_phone}). "
        "Please be available to receive it."
    ),
    
    'parcel_delivered': (
        "MAUA SHARK: Parcel {ref_code} has been DELIVERED successfully! "
        "Thank you for choosing Maua Shark Sacco for your parcel delivery. "
        "We appreciate your business and welcome you to send again!"
    ),
    
    'parcel_delivered_receiver': (
        "MAUA SHARK: Hello {receiver_name}! Parcel {ref_code} has been delivered to you. "
        "Thank you for choosing Maua Shark Sacco!"
    ),
    
    # APPRECIATION MESSAGES
    'thank_you_first_booking': (
        "MAUA SHARK: Welcome to the Maua Shark family, {passenger_name}! "
        "Thank you for your first booking with us. "
        "We're committed to providing you safe and comfortable travels. "
        "Save this number for easy booking!"
    ),
    
    'loyalty_appreciation': (
        "MAUA SHARK: Dear {passenger_name}, thank you for being a loyal customer! "
        "This is your {booking_count}th trip with us. "
        "We truly appreciate your continued trust in Maua Shark Sacco!"
    ),
}


# =============================================================================
# EMAIL TEMPLATES (HTML)
# =============================================================================

EMAIL_TEMPLATES = {
    'booking_confirmation': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 10px 0 0; opacity: 0.9; }
        .content { padding: 30px; }
        .ticket-box { background: #f8fafc; border: 2px dashed #1e40af; border-radius: 10px; padding: 20px; margin: 20px 0; }
        .ticket-header { text-align: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 15px; margin-bottom: 15px; }
        .ref-code { font-size: 28px; font-weight: bold; color: #1e40af; letter-spacing: 2px; }
        .detail-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e2e8f0; }
        .detail-label { color: #64748b; font-size: 14px; }
        .detail-value { font-weight: 600; color: #1e293b; }
        .route-box { background: #1e40af; color: white; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }
        .route-arrow { font-size: 24px; margin: 0 15px; }
        .route-city { font-size: 20px; font-weight: bold; }
        .cta-button { display: inline-block; background: #1e40af; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: bold; margin: 20px 0; }
        .footer { background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }
        .footer a { color: #60a5fa; }
        .highlight { background: #fef3c7; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b; margin: 20px 0; }
        .highlight-title { font-weight: bold; color: #92400e; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚌 MAUA SHARK SACCO</h1>
            <p>Your Booking is Confirmed!</p>
        </div>
        <div class="content">
            <p>Dear <strong>{{ passenger_name }}</strong>,</p>
            <p>Thank you for booking with Maua Shark Sacco! Your trip has been confirmed.</p>
            
            <div class="ticket-box">
                <div class="ticket-header">
                    <div class="ref-code">{{ reference }}</div>
                    <p style="margin: 5px 0; color: #64748b;">Booking Reference</p>
                </div>
                
                <div class="route-box">
                    <span class="route-city">{{ origin }}</span>
                    <span class="route-arrow">→</span>
                    <span class="route-city">{{ destination }}</span>
                </div>
                
                <div class="detail-row">
                    <span class="detail-label">Travel Date</span>
                    <span class="detail-value">{{ date }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Departure Time</span>
                    <span class="detail-value">{{ time }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Seat Number</span>
                    <span class="detail-value">{{ seat_number }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Vehicle</span>
                    <span class="detail-value">{{ vehicle }}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Fare Paid</span>
                    <span class="detail-value">KES {{ fare }}</span>
                </div>
            </div>
            
            <div class="highlight">
                <p class="highlight-title">⏰ Important Reminder</p>
                <p style="margin: 5px 0;">Please arrive at the departure point <strong>30 minutes</strong> before your scheduled departure time. Carry a valid ID for verification.</p>
            </div>
            
            <p style="text-align: center;">
                <a href="{{ receipt_url }}" class="cta-button">Download E-Ticket</a>
            </p>
            
            <p>If you have any questions, please contact us:</p>
            <ul>
                <li>Phone: 0712 345 678</li>
                <li>Email: support@mauashark.com</li>
            </ul>
            
            <p>Thank you for choosing Maua Shark Sacco. Have a safe journey!</p>
        </div>
        <div class="footer">
            <p>© {{ year }} Maua Shark Sacco. All Rights Reserved.</p>
            <p>This is an automated message. Please do not reply directly to this email.</p>
        </div>
    </div>
</body>
</html>
''',

    'parcel_confirmation': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #059669 0%, #10b981 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px; }
        .parcel-box { background: #f0fdf4; border: 2px solid #059669; border-radius: 10px; padding: 20px; margin: 20px 0; }
        .ref-code { font-size: 28px; font-weight: bold; color: #059669; letter-spacing: 2px; text-align: center; }
        .detail-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e2e8f0; }
        .detail-label { color: #64748b; }
        .detail-value { font-weight: 600; color: #1e293b; }
        .status-badge { display: inline-block; background: #fef3c7; color: #92400e; padding: 5px 15px; border-radius: 20px; font-weight: bold; }
        .footer { background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 MAUA SHARK SACCO</h1>
            <p>Parcel Registered Successfully!</p>
        </div>
        <div class="content">
            <p>Dear <strong>{{ sender_name }}</strong>,</p>
            <p>Your parcel has been registered and payment confirmed!</p>
            
            <div class="parcel-box">
                <p style="text-align: center; margin: 0 0 10px;">Tracking Reference</p>
                <div class="ref-code">{{ ref_code }}</div>
                
                <div style="margin-top: 20px;">
                    <div class="detail-row">
                        <span class="detail-label">From</span>
                        <span class="detail-value">{{ origin }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">To</span>
                        <span class="detail-value">{{ destination }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Receiver</span>
                        <span class="detail-value">{{ receiver_name }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Receiver Phone</span>
                        <span class="detail-value">{{ receiver_phone }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Amount</span>
                        <span class="detail-value">KES {{ price }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Status</span>
                        <span class="status-badge">{{ status }}</span>
                    </div>
                </div>
            </div>
            
            <p>Track your parcel anytime using the reference code above.</p>
            <p>Thank you for choosing Maua Shark Sacco!</p>
        </div>
        <div class="footer">
            <p>© {{ year }} Maua Shark Sacco. All Rights Reserved.</p>
        </div>
    </div>
</body>
</html>
''',

    'trip_reminder': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 30px; }
        .reminder-box { background: #fffbeb; border: 2px solid #f59e0b; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center; }
        .big-text { font-size: 48px; font-weight: bold; color: #f59e0b; }
        .footer { background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⏰ TRIP REMINDER</h1>
            <p>Your Trip is Tomorrow!</p>
        </div>
        <div class="content">
            <p>Dear <strong>{{ passenger_name }}</strong>,</p>
            
            <div class="reminder-box">
                <p class="big-text">TOMORROW</p>
                <p style="font-size: 18px; margin: 10px 0;"><strong>{{ origin }}</strong> → <strong>{{ destination }}</strong></p>
                <p>Departure: <strong>{{ time }}</strong></p>
                <p>Seat: <strong>{{ seat_number }}</strong> | Vehicle: <strong>{{ vehicle }}</strong></p>
            </div>
            
            <h3>📋 Checklist:</h3>
            <ul>
                <li>✅ Arrive 30 minutes before departure</li>
                <li>✅ Bring valid ID (National ID/Passport)</li>
                <li>✅ Have your booking reference ready: <strong>{{ reference }}</strong></li>
            </ul>
            
            <p>Safe travels!</p>
        </div>
        <div class="footer">
            <p>© {{ year }} Maua Shark Sacco</p>
        </div>
    </div>
</body>
</html>
''',

    'thank_you': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%); color: white; padding: 40px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; }
        .content { padding: 30px; text-align: center; }
        .emoji { font-size: 60px; margin: 20px 0; }
        .footer { background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🙏 Thank You!</h1>
        </div>
        <div class="content">
            <div class="emoji">🎉</div>
            <h2>Trip Completed Successfully!</h2>
            <p>Dear <strong>{{ passenger_name }}</strong>,</p>
            <p>Thank you for traveling with Maua Shark Sacco from <strong>{{ origin }}</strong> to <strong>{{ destination }}</strong>.</p>
            <p>We hope you had a pleasant and comfortable journey!</p>
            <p>Your satisfaction is our priority. We look forward to serving you again soon.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
            <p style="color: #64748b;">Have feedback? We'd love to hear from you!</p>
        </div>
        <div class="footer">
            <p>© {{ year }} Maua Shark Sacco. Safe Travels, Always!</p>
        </div>
    </div>
</body>
</html>
''',

    'parcel_receipt': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .container { max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #059669 0%, #10b981 100%); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 10px 0 0; opacity: 0.9; }
        .content { padding: 30px; }
        .receipt-box { background: #f0fdf4; border: 2px solid #059669; border-radius: 10px; padding: 25px; margin: 20px 0; }
        .ref-code { font-size: 32px; font-weight: bold; color: #059669; letter-spacing: 3px; text-align: center; margin-bottom: 20px; }
        .route-display { background: #059669; color: white; padding: 15px; border-radius: 8px; text-align: center; margin: 15px 0; }
        .route-display .from-to { font-size: 18px; font-weight: bold; }
        .section-title { font-weight: bold; color: #059669; margin: 20px 0 10px; padding-bottom: 5px; border-bottom: 2px solid #059669; }
        .detail-grid { display: table; width: 100%; }
        .detail-row { display: table-row; }
        .detail-label { display: table-cell; padding: 8px 10px 8px 0; color: #64748b; width: 40%; }
        .detail-value { display: table-cell; padding: 8px 0; font-weight: 600; color: #1e293b; }
        .amount-box { background: #dcfce7; padding: 15px; border-radius: 8px; text-align: center; margin: 20px 0; }
        .amount { font-size: 28px; font-weight: bold; color: #059669; }
        .status-badge { display: inline-block; background: #fef3c7; color: #92400e; padding: 8px 20px; border-radius: 20px; font-weight: bold; }
        .paid-badge { background: #dcfce7; color: #059669; }
        .track-info { background: #eff6ff; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .track-info p { margin: 5px 0; }
        .footer { background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 MAUA SHARK SACCO</h1>
            <p>Parcel Delivery Receipt</p>
        </div>
        <div class="content">
            <p>Dear <strong>{{ recipient_name }}</strong>,</p>
            <p>{{ message_intro }}</p>
            
            <div class="receipt-box">
                <p style="text-align: center; margin: 0 0 5px; color: #64748b;">Tracking Reference</p>
                <div class="ref-code">{{ ref_code }}</div>
                
                <div class="route-display">
                    <span class="from-to">{{ origin }} → {{ destination }}</span>
                </div>
                
                <p class="section-title">📋 Parcel Details</p>
                <div class="detail-grid">
                    <div class="detail-row">
                        <span class="detail-label">Date Created</span>
                        <span class="detail-value">{{ date }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Weight</span>
                        <span class="detail-value">{{ weight }} kg</span>
                    </div>
                </div>
                
                <p class="section-title">👤 Sender</p>
                <div class="detail-grid">
                    <div class="detail-row">
                        <span class="detail-label">Name</span>
                        <span class="detail-value">{{ sender_name }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Phone</span>
                        <span class="detail-value">{{ sender_phone }}</span>
                    </div>
                </div>
                
                <p class="section-title">📍 Receiver</p>
                <div class="detail-grid">
                    <div class="detail-row">
                        <span class="detail-label">Name</span>
                        <span class="detail-value">{{ receiver_name }}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Phone</span>
                        <span class="detail-value">{{ receiver_phone }}</span>
                    </div>
                </div>
                
                <div class="amount-box">
                    <p style="margin: 0 0 5px; color: #64748b;">Amount</p>
                    <span class="amount">KES {{ price }}</span>
                    <br>
                    <span class="status-badge {{ 'paid-badge' if payment_status == 'Paid' else '' }}">{{ payment_status }}</span>
                </div>
            </div>
            
            <div class="track-info">
                <p><strong>🔍 Track Your Parcel</strong></p>
                <p>Visit: <strong>maua-shark.onrender.com/parcels/track</strong></p>
                <p>Enter reference: <strong>{{ ref_code }}</strong></p>
            </div>
            
            <p style="text-align: center; color: #64748b;">
                Thank you for choosing Maua Shark Sacco for your delivery needs!
            </p>
        </div>
        <div class="footer">
            <p>© {{ year }} Maua Shark Sacco. All Rights Reserved.</p>
            <p>This is your official parcel receipt. Please keep it for your records.</p>
        </div>
    </div>
</body>
</html>
''',
}


class NotificationService:
    """Unified notification service for SMS and Email"""
    
    @staticmethod
    def send_sms(phone_number: str, message: str, user_email: str = None) -> bool:
        """Send SMS notification"""
        from maua.notifications.sms import send_sms as _send_sms
        try:
            return _send_sms(phone_number, message, user_email=user_email)
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False
    
    @staticmethod
    def _send_email_sync(app, to_email: str, subject: str, html_content: str):
        """Synchronous email send (runs in background thread)"""
        try:
            from flask_mail import Message
            
            with app.app_context():
                msg = Message(
                    subject=f"MAUA SHARK - {subject}",
                    recipients=[to_email],
                    html=html_content,
                    sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@mauashark.com')
                )
                app.mail.send(msg)
                logger.info(f"Email sent to {to_email}: {subject}")
        except Exception as e:
            logger.error(f"Email send error to {to_email}: {e}")
    
    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """Send Email notification (non-blocking, runs in background thread)"""
        try:
            from threading import Thread
            
            # Get app instance for background thread
            app = current_app._get_current_object()
            
            # Send in background thread to avoid blocking request
            thread = Thread(
                target=NotificationService._send_email_sync,
                args=(app, to_email, subject, html_content)
            )
            thread.daemon = True
            thread.start()
            
            logger.info(f"Email queued for {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email queue error for {to_email}: {e}")
            return False
    
    # =========================================================================
    # BOOKING NOTIFICATIONS
    # =========================================================================
    
    @classmethod
    def notify_booking_confirmed(cls, booking) -> dict:
        """Send booking confirmation SMS and Email"""
        results = {'sms': False, 'email': False}
        
        try:
            # Prepare data
            data = {
                'passenger_name': booking.passenger_name,
                'reference': booking.reference,
                'origin': booking.trip.route.origin.town,
                'destination': booking.trip.route.destination.town,
                'date': booking.trip.depart_at.strftime('%Y-%m-%d'),
                'time': booking.trip.depart_at.strftime('%H:%M'),
                'seat_number': booking.seat_number,
                'vehicle': getattr(booking.trip.vehicle, 'plate_no', 'TBA'),
                'fare': f"{booking.fare:,.0f}",
                'year': datetime.now().year,
                'receipt_url': '#',  # Would be actual URL in production
            }
            
            # Send SMS
            sms_message = SMS_TEMPLATES['booking_confirmed'].format(**data)
            results['sms'] = cls.send_sms(
                booking.passenger_phone, 
                sms_message,
                user_email=booking.passenger.email if booking.passenger else None
            )
            
            # Send Email if user has email
            if booking.passenger and booking.passenger.email:
                html = render_template_string(EMAIL_TEMPLATES['booking_confirmation'], **data)
                results['email'] = cls.send_email(
                    booking.passenger.email,
                    "Booking Confirmed!",
                    html
                )
            
            # Check if first-time customer
            if booking.passenger:
                from maua.booking.models import Booking
                booking_count = Booking.query.filter_by(user_id=booking.passenger.id).count()
                if booking_count == 1:
                    # First booking - send welcome message
                    welcome_msg = SMS_TEMPLATES['thank_you_first_booking'].format(
                        passenger_name=booking.passenger_name
                    )
                    cls.send_sms(booking.passenger_phone, welcome_msg,
                                user_email=booking.passenger.email if booking.passenger else None)
                elif booking_count % 5 == 0:
                    # Loyalty appreciation every 5 bookings
                    loyalty_msg = SMS_TEMPLATES['loyalty_appreciation'].format(
                        passenger_name=booking.passenger_name,
                        booking_count=booking_count
                    )
                    cls.send_sms(booking.passenger_phone, loyalty_msg,
                                user_email=booking.passenger.email if booking.passenger else None)
            
            logger.info(f"Booking confirmation sent for {booking.reference}")
            
        except Exception as e:
            logger.error(f"Error sending booking confirmation: {e}")
        
        return results
    
    @classmethod
    def notify_payment_received(cls, booking, amount) -> dict:
        """Send payment received notification"""
        results = {'sms': False, 'email': False}
        
        try:
            data = {
                'passenger_name': booking.passenger_name,
                'reference': booking.reference,
                'route': f"{booking.trip.route.origin.town} to {booking.trip.route.destination.town}",
                'date': booking.trip.depart_at.strftime('%Y-%m-%d'),
                'time': booking.trip.depart_at.strftime('%H:%M'),
                'seat_number': booking.seat_number,
                'amount': f"{amount:,.0f}",
            }
            
            sms_message = SMS_TEMPLATES['booking_payment_received'].format(**data)
            results['sms'] = cls.send_sms(
                booking.passenger_phone, 
                sms_message,
                user_email=booking.passenger.email if booking.passenger else None
            )
            
        except Exception as e:
            logger.error(f"Error sending payment notification: {e}")
        
        return results
    
    @classmethod
    def notify_booking_checked_in(cls, booking) -> dict:
        """Send check-in notification"""
        results = {'sms': False}
        
        try:
            data = {
                'passenger_name': booking.passenger_name,
                'origin': booking.trip.route.origin.town,
                'destination': booking.trip.route.destination.town,
                'seat_number': booking.seat_number,
            }
            
            sms_message = SMS_TEMPLATES['booking_checked_in'].format(**data)
            results['sms'] = cls.send_sms(
                booking.passenger_phone, 
                sms_message,
                user_email=booking.passenger.email if booking.passenger else None
            )
            
        except Exception as e:
            logger.error(f"Error sending check-in notification: {e}")
        
        return results
    
    @classmethod
    def notify_booking_completed(cls, booking) -> dict:
        """Send trip completion thank you notification"""
        results = {'sms': False, 'email': False}
        
        try:
            data = {
                'passenger_name': booking.passenger_name,
                'origin': booking.trip.route.origin.town,
                'destination': booking.trip.route.destination.town,
                'year': datetime.now().year,
            }
            
            # SMS
            sms_message = SMS_TEMPLATES['booking_completed'].format(**data)
            results['sms'] = cls.send_sms(
                booking.passenger_phone, 
                sms_message,
                user_email=booking.passenger.email if booking.passenger else None
            )
            
            # Email
            if booking.passenger and booking.passenger.email:
                html = render_template_string(EMAIL_TEMPLATES['thank_you'], **data)
                results['email'] = cls.send_email(
                    booking.passenger.email,
                    "Thank You for Traveling with Us!",
                    html
                )
            
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")
        
        return results
    
    @classmethod
    def notify_booking_cancelled(cls, booking) -> dict:
        """Send booking cancellation notification"""
        results = {'sms': False}
        
        try:
            data = {
                'reference': booking.reference,
            }
            
            sms_message = SMS_TEMPLATES['booking_cancelled'].format(**data)
            results['sms'] = cls.send_sms(
                booking.passenger_phone, 
                sms_message,
                user_email=booking.passenger.email if booking.passenger else None
            )
            
        except Exception as e:
            logger.error(f"Error sending cancellation notification: {e}")
        
        return results
    
    @classmethod
    def notify_trip_reminder(cls, booking) -> dict:
        """Send trip reminder (day before)"""
        results = {'sms': False, 'email': False}
        
        try:
            data = {
                'passenger_name': booking.passenger_name,
                'reference': booking.reference,
                'origin': booking.trip.route.origin.town,
                'destination': booking.trip.route.destination.town,
                'time': booking.trip.depart_at.strftime('%H:%M'),
                'vehicle': getattr(booking.trip.vehicle, 'plate_no', 'TBA'),
                'seat_number': booking.seat_number,
                'year': datetime.now().year,
            }
            
            # SMS
            sms_message = SMS_TEMPLATES['booking_reminder'].format(**data)
            results['sms'] = cls.send_sms(
                booking.passenger_phone, 
                sms_message,
                user_email=booking.passenger.email if booking.passenger else None
            )
            
            # Email
            if booking.passenger and booking.passenger.email:
                html = render_template_string(EMAIL_TEMPLATES['trip_reminder'], **data)
                results['email'] = cls.send_email(
                    booking.passenger.email,
                    "Trip Reminder - Tomorrow!",
                    html
                )
            
        except Exception as e:
            logger.error(f"Error sending trip reminder: {e}")
        
        return results
    
    # =========================================================================
    # PARCEL NOTIFICATIONS
    # =========================================================================
    
    @classmethod
    def notify_parcel_created(cls, parcel, user_email=None) -> dict:
        """Send parcel creation notification and receipt to sender and receiver"""
        results = {'sender_sms': False, 'receiver_sms': False, 'sender_email': False, 'receiver_email': False}
        
        try:
            # Use parcel's stored emails, fallback to provided user_email
            sender_email = getattr(parcel, 'sender_email', None) or user_email
            receiver_email = getattr(parcel, 'receiver_email', None)
            
            # Basic data for SMS
            sms_data = {
                'ref_code': parcel.ref_code,
                'origin': parcel.origin_name,
                'destination': parcel.destination_name,
                'sender_name': parcel.sender_name,
                'receiver_name': parcel.receiver_name,
                'receiver_phone': parcel.receiver_phone,
                'price': f"{parcel.price:,.0f}",
                'status': parcel.status.replace('_', ' ').title(),
                'year': datetime.now().year,
            }
            
            # SMS to sender (with email fallback)
            sender_msg = SMS_TEMPLATES['parcel_created'].format(**sms_data)
            results['sender_sms'] = cls.send_sms(parcel.sender_phone, sender_msg, user_email=sender_email)
            
            # SMS to receiver (with email fallback)
            receiver_msg = SMS_TEMPLATES['parcel_receiver_notification'].format(**sms_data)
            results['receiver_sms'] = cls.send_sms(parcel.receiver_phone, receiver_msg, user_email=receiver_email)
            
            # Full receipt data for email
            receipt_data = {
                'ref_code': parcel.ref_code,
                'origin': parcel.origin_name,
                'destination': parcel.destination_name,
                'sender_name': parcel.sender_name,
                'sender_phone': parcel.sender_phone,
                'receiver_name': parcel.receiver_name,
                'receiver_phone': parcel.receiver_phone,
                'price': f"{parcel.price:,.0f}",
                'weight': f"{parcel.weight_kg:.1f}" if parcel.weight_kg else "N/A",
                'date': parcel.created_at.strftime('%B %d, %Y at %I:%M %p') if parcel.created_at else 'N/A',
                'payment_status': 'Paid' if parcel.payment_status == 'paid' else 'Pending',
                'year': datetime.now().year,
            }
            
            # Send receipt email to SENDER
            if sender_email:
                sender_receipt_data = receipt_data.copy()
                sender_receipt_data['recipient_name'] = parcel.sender_name
                sender_receipt_data['message_intro'] = 'Your parcel has been registered successfully! Here is your receipt:'
                
                html = render_template_string(EMAIL_TEMPLATES['parcel_receipt'], **sender_receipt_data)
                results['sender_email'] = cls.send_email(sender_email, f"Parcel Receipt - {parcel.ref_code}", html)
                logger.info(f"Receipt email sent to sender: {sender_email}")
            
            # Send receipt email to RECEIVER
            if receiver_email:
                receiver_receipt_data = receipt_data.copy()
                receiver_receipt_data['recipient_name'] = parcel.receiver_name
                receiver_receipt_data['message_intro'] = f'A parcel is being sent to you by {parcel.sender_name}. Here are the details:'
                
                html = render_template_string(EMAIL_TEMPLATES['parcel_receipt'], **receiver_receipt_data)
                results['receiver_email'] = cls.send_email(receiver_email, f"Parcel Incoming - {parcel.ref_code}", html)
                logger.info(f"Receipt email sent to receiver: {receiver_email}")
            
        except Exception as e:
            logger.error(f"Error sending parcel creation notification: {e}")
        
        return results
    
    @classmethod
    def notify_parcel_payment_confirmed(cls, parcel, user_email=None) -> dict:
        """Send parcel payment confirmation with receipt emails"""
        results = {'sms': False, 'sender_email': False, 'receiver_email': False}
        
        try:
            # Use parcel's stored emails
            sender_email = getattr(parcel, 'sender_email', None) or user_email
            receiver_email = getattr(parcel, 'receiver_email', None)
            
            sms_data = {
                'ref_code': parcel.ref_code,
                'origin': parcel.origin_name,
                'destination': parcel.destination_name,
                'price': f"{parcel.price:,.0f}",
            }
            
            # SMS to sender
            sms_message = SMS_TEMPLATES['parcel_payment_confirmed'].format(**sms_data)
            results['sms'] = cls.send_sms(parcel.sender_phone, sms_message, user_email=sender_email)
            
            # Full receipt data for email
            receipt_data = {
                'ref_code': parcel.ref_code,
                'origin': parcel.origin_name,
                'destination': parcel.destination_name,
                'sender_name': parcel.sender_name,
                'sender_phone': parcel.sender_phone,
                'receiver_name': parcel.receiver_name,
                'receiver_phone': parcel.receiver_phone,
                'price': f"{parcel.price:,.0f}",
                'weight': f"{parcel.weight_kg:.1f}" if parcel.weight_kg else "N/A",
                'date': parcel.created_at.strftime('%B %d, %Y at %I:%M %p') if parcel.created_at else 'N/A',
                'payment_status': 'Paid',
                'year': datetime.now().year,
            }
            
            # Send paid receipt email to SENDER
            if sender_email:
                sender_receipt_data = receipt_data.copy()
                sender_receipt_data['recipient_name'] = parcel.sender_name
                sender_receipt_data['message_intro'] = 'Payment confirmed! Your parcel is ready for dispatch. Here is your receipt:'
                
                html = render_template_string(EMAIL_TEMPLATES['parcel_receipt'], **sender_receipt_data)
                results['sender_email'] = cls.send_email(sender_email, f"Payment Confirmed - Parcel {parcel.ref_code}", html)
                logger.info(f"Payment receipt email sent to sender: {sender_email}")
            
            # Send notification to RECEIVER that parcel is paid and ready
            if receiver_email:
                receiver_receipt_data = receipt_data.copy()
                receiver_receipt_data['recipient_name'] = parcel.receiver_name
                receiver_receipt_data['message_intro'] = f'Great news! A parcel from {parcel.sender_name} has been paid for and is ready for dispatch to you:'
                
                html = render_template_string(EMAIL_TEMPLATES['parcel_receipt'], **receiver_receipt_data)
                results['receiver_email'] = cls.send_email(receiver_email, f"Parcel Ready - {parcel.ref_code}", html)
                logger.info(f"Payment notification email sent to receiver: {receiver_email}")
            
        except Exception as e:
            logger.error(f"Error sending parcel payment notification: {e}")
        
        return results
    
    @classmethod
    def notify_parcel_in_transit(cls, parcel, vehicle=None, driver_name=None, driver_phone=None, user_email=None) -> dict:
        """Send parcel in transit notification"""
        results = {'sender_sms': False, 'receiver_sms': False}
        
        try:
            # Use parcel's stored emails
            sender_email = getattr(parcel, 'sender_email', None) or user_email
            receiver_email = getattr(parcel, 'receiver_email', None)
            
            data = {
                'ref_code': parcel.ref_code,
                'destination': parcel.destination_name,
                'sender_name': parcel.sender_name,
                'receiver_name': parcel.receiver_name,
                'vehicle': vehicle or parcel.vehicle_plate or 'N/A',
                'driver_name': driver_name or getattr(parcel, 'driver_name', None) or 'N/A',
                'driver_phone': driver_phone or parcel.driver_phone or 'N/A',
            }
            
            # SMS to sender (with email fallback)
            sender_msg = SMS_TEMPLATES['parcel_in_transit'].format(**data)
            results['sender_sms'] = cls.send_sms(parcel.sender_phone, sender_msg, user_email=sender_email)
            
            # SMS to receiver (with email fallback)
            receiver_msg = SMS_TEMPLATES['parcel_in_transit_receiver'].format(**data)
            results['receiver_sms'] = cls.send_sms(parcel.receiver_phone, receiver_msg, user_email=receiver_email)
            
        except Exception as e:
            logger.error(f"Error sending parcel transit notification: {e}")
        
        return results
    
    @classmethod
    def notify_parcel_delivered(cls, parcel, user_email=None) -> dict:
        """Send parcel delivery notification with appreciation"""
        results = {'sender_sms': False, 'receiver_sms': False}
        
        try:
            # Use parcel's stored emails
            sender_email = getattr(parcel, 'sender_email', None) or user_email
            receiver_email = getattr(parcel, 'receiver_email', None)
            
            data = {
                'ref_code': parcel.ref_code,
                'receiver_name': parcel.receiver_name,
            }
            
            # SMS to sender (with email fallback)
            sender_msg = SMS_TEMPLATES['parcel_delivered'].format(**data)
            results['sender_sms'] = cls.send_sms(parcel.sender_phone, sender_msg, user_email=sender_email)
            
            # SMS to receiver (with email fallback)
            receiver_msg = SMS_TEMPLATES['parcel_delivered_receiver'].format(**data)
            results['receiver_sms'] = cls.send_sms(parcel.receiver_phone, receiver_msg, user_email=receiver_email)
            
        except Exception as e:
            logger.error(f"Error sending parcel delivery notification: {e}")
        
        return results


# Convenience function for direct import
def send_notification(notification_type: str, **kwargs):
    """Send notification by type
    
    notification_type can be:
    - booking_confirmed
    - booking_payment
    - booking_checked_in
    - booking_completed
    - booking_cancelled
    - trip_reminder
    - parcel_created
    - parcel_payment
    - parcel_in_transit
    - parcel_delivered
    """
    service = NotificationService()
    
    handlers = {
        'booking_confirmed': service.notify_booking_confirmed,
        'booking_payment': service.notify_payment_received,
        'booking_checked_in': service.notify_booking_checked_in,
        'booking_completed': service.notify_booking_completed,
        'booking_cancelled': service.notify_booking_cancelled,
        'trip_reminder': service.notify_trip_reminder,
        'parcel_created': service.notify_parcel_created,
        'parcel_payment': service.notify_parcel_payment_confirmed,
        'parcel_in_transit': service.notify_parcel_in_transit,
        'parcel_delivered': service.notify_parcel_delivered,
    }
    
    handler = handlers.get(notification_type)
    if handler:
        return handler(**kwargs)
    else:
        logger.warning(f"Unknown notification type: {notification_type}")
        return {}

