from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from maua.extensions import db
from maua.payment.models import Payment
from maua.booking.models import Booking
from maua.parcels.models import Parcel
from maua.payment.mpesa_service import MpesaService
from maua.payment.cache import PaymentStatusCache
from maua.booking.services import broker
import json

payment_bp = Blueprint('payment', __name__, url_prefix='/payments')

@payment_bp.route('/', methods=['GET'])
@login_required
def index():
    """Display payment dashboard"""
    return render_template('payment/index.html')

@payment_bp.route('/initiate', methods=['POST'])
@login_required
def initiate_payment():
    """Initiate a new payment"""
    data = request.get_json()
    
    try:
        amount = float(data.get('amount'))
        payment_type = data.get('type')  # 'booking' or 'parcel'
        reference_id = data.get('reference_id')
        
        if not all([amount, payment_type, reference_id]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
            
        # Create a new payment record
        payment = Payment(
            amount=amount,
            payment_method='pending',  # Will be updated after payment method selection
            status='pending',
            user_id=current_user.id,
            booking_id=reference_id if payment_type == 'booking' else None,
            parcel_id=reference_id if payment_type == 'parcel' else None
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'payment_id': payment.id,
            'amount': str(amount),
            'message': 'Payment initiated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Payment initiation failed: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Failed to initiate payment'
        }), 500

@payment_bp.route('/process/mpesa', methods=['POST'])
@login_required
def process_mpesa():
    """Process M-Pesa STK push payment"""
    data = request.get_json()
    payment_id = data.get('payment_id')
    phone = data.get('phone')
    
    try:
        payment = Payment.query.get_or_404(payment_id)
        
        # Initialize M-Pesa service
        mpesa_service = MpesaService()
        
        # Generate account reference
        account_reference = f"BOOKING-{payment.id}"
        transaction_desc = f"Booking payment for {payment.booking.reference if payment.booking else 'Parcel'}"
        
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
            
            return jsonify({
                'status': 'success',
                'message': stk_response.get('customer_message', 'STK push sent successfully'),
                'checkout_request_id': stk_response.get('checkout_request_id'),
                'payment_id': payment.id
            })
        else:
            return jsonify({
                'status': 'error',
                'message': stk_response.get('message', 'STK push failed')
            }), 400
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'M-Pesa STK push failed: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Payment processing failed'
        }), 500

@payment_bp.route('/callback/mpesa', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa callback"""
    try:
        data = request.get_json()
        current_app.logger.info(f'M-Pesa callback received: {json.dumps(data)}')
        
        # Initialize M-Pesa service
        mpesa_service = MpesaService()
        
        # Process callback
        callback_result = mpesa_service.process_callback(data)
        
        if callback_result['success']:
            # Find payment by checkout request ID
            checkout_request_id = callback_result['checkout_request_id']
            payment = Payment.query.filter_by(transaction_id=checkout_request_id).first()
            
            if payment:
                # Update payment status
                payment_data = callback_result.get('payment_data', {})
                payment.status = 'completed'
                payment.payment_method = 'mpesa'
                payment.transaction_id = payment_data.get('receipt_number', checkout_request_id)
                payment.payment_date = datetime.utcnow()
                
                # Update related booking or parcel status
                if payment.booking_id:
                    booking = Booking.query.get(payment.booking_id)
                    if booking:
                        booking.status = 'confirmed'
                        # Create ticket
                        from maua.booking.models import Ticket
                        ticket = Ticket(booking_id=booking.id, status='confirmed')
                        db.session.add(ticket)
                elif payment.parcel_id:
                    parcel = Parcel.query.get(payment.parcel_id)
                    if parcel:
                        parcel.status = 'created'  # Change from pending_payment to created
                        parcel.payment_status = 'paid'
                        
                        # Send SMS notifications
                        try:
                            from maua.notifications.sms import send_sms
                            msg_sender = (
                                f"Maua Shark: Parcel {parcel.ref_code} payment confirmed from {parcel.origin_name} to {parcel.destination_name}. "
                                f"Receiver: {parcel.receiver_name} ({parcel.receiver_phone}). Price KES {parcel.price}."
                            )
                            msg_receiver = (
                                f"Maua Shark: A parcel for you ({parcel.receiver_name}) payment confirmed. Ref {parcel.ref_code}. "
                                f"From {parcel.sender_name} ({parcel.sender_phone}) to be sent to {parcel.destination_name}."
                            )
                            send_sms(parcel.sender_phone, msg_sender, user_email=payment.user.email)
                            send_sms(parcel.receiver_phone, msg_receiver, user_email=payment.user.email)
                        except Exception:
                            pass
                
                db.session.commit()
                current_app.logger.info(f'Payment {payment.id} completed successfully')
            else:
                current_app.logger.warning(f'Payment not found for checkout request ID: {checkout_request_id}')
        else:
            # Payment failed
            checkout_request_id = callback_result.get('checkout_request_id')
            if checkout_request_id:
                payment = Payment.query.filter_by(transaction_id=checkout_request_id).first()
                if payment:
                    payment.status = 'failed'
                    # Cancel related booking and free seat if exists
                    if payment.booking_id:
                        booking = Booking.query.get(payment.booking_id)
                        if booking and booking.status == 'pending_payment':
                            booking.status = 'cancelled'
                            try:
                                broker.publish(booking.trip_id, {"type": "seat_cancelled", "seat": booking.seat_number, "status": "available"})
                            except Exception:
                                pass
                    db.session.commit()
                    current_app.logger.info(f'Payment {payment.id} failed: {callback_result.get("result_desc")}')
        
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        current_app.logger.error(f'Error processing M-Pesa callback: {str(e)}')
        return jsonify({'ResultCode': 1, 'ResultDesc': 'Error'}), 500

@payment_bp.route('/status/<int:payment_id>', methods=['GET'])
@login_required
def check_payment_status(payment_id):
    """Check payment status"""
    try:
        payment = Payment.query.get_or_404(payment_id)
        
        # Ensure the user has permission to view this payment
        if payment.user_id != current_user.id and not current_user.is_admin:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized'
            }), 403
        
        # If payment is still pending and using STK push, check status
        if payment.status == 'pending' and payment.payment_method == 'mpesa_stk':
            # Check cache first to avoid unnecessary API calls
            cached_status = PaymentStatusCache.get_status(payment.id)
            if cached_status:
                return jsonify({
                    'status': 'success',
                    'payment': cached_status
                })
            
            # Use singleton instance to avoid re-initialization
            mpesa_service = MpesaService()
            status_response = mpesa_service.query_stk_push_status(payment.transaction_id)
            
            if status_response['success']:
                result_code = status_response.get('result_code')
                if result_code == 0:
                    # Payment completed
                    payment.status = 'completed'
                    payment.payment_method = 'mpesa'
                    payment.payment_date = datetime.utcnow()
                    
                    # Update related booking or parcel status
                    if payment.booking_id:
                        booking = Booking.query.get(payment.booking_id)
                        if booking:
                            booking.status = 'confirmed'
                            # Create ticket
                            from maua.booking.models import Ticket
                            ticket = Ticket(booking_id=booking.id, status='confirmed')
                            db.session.add(ticket)
                    elif payment.parcel_id:
                        parcel = Parcel.query.get(payment.parcel_id)
                        if parcel:
                            parcel.status = 'created'  # Change from pending_payment to created
                            parcel.payment_status = 'paid'
                            
                            # Send SMS notifications
                            try:
                                from maua.notifications.sms import send_sms
                                msg_sender = (
                                    f"Maua Shark: Parcel {parcel.ref_code} payment confirmed from {parcel.origin_name} to {parcel.destination_name}. "
                                    f"Receiver: {parcel.receiver_name} ({parcel.receiver_phone}). Price KES {parcel.price}."
                                )
                                msg_receiver = (
                                    f"Maua Shark: A parcel for you ({parcel.receiver_name}) payment confirmed. Ref {parcel.ref_code}. "
                                    f"From {parcel.sender_name} ({parcel.sender_phone}) to be sent to {parcel.destination_name}."
                                )
                                send_sms(parcel.sender_phone, msg_sender, user_email=payment.user.email)
                                send_sms(parcel.receiver_phone, msg_receiver, user_email=payment.user.email)
                            except Exception:
                                pass
                    
                    db.session.commit()
                    
                    # Cache the updated status
                    PaymentStatusCache.set_status(payment.id, {
                        'id': payment.id,
                        'status': payment.status,
                        'amount': float(payment.amount),
                        'payment_method': payment.payment_method,
                        'transaction_id': payment.transaction_id,
                        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None
                    })
                elif result_code == 1032:
                    # User cancelled
                    payment.status = 'failed'
                    # Cancel related booking and free seat if exists
                    if payment.booking_id:
                        booking = Booking.query.get(payment.booking_id)
                        if booking and booking.status == 'pending_payment':
                            booking.status = 'cancelled'
                            try:
                                broker.publish(booking.trip_id, {"type": "seat_cancelled", "seat": booking.seat_number, "status": "available"})
                            except Exception:
                                pass
                    db.session.commit()
                    
                    # Cache the failed status
                    PaymentStatusCache.set_status(payment.id, {
                        'id': payment.id,
                        'status': payment.status,
                        'amount': float(payment.amount),
                        'payment_method': payment.payment_method,
                        'transaction_id': payment.transaction_id,
                        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                        'message': 'Payment was cancelled on your phone.'
                    })
                elif result_code == 2001:
                    # Wrong PIN
                    payment.status = 'failed'
                    # Cancel related booking and free seat if exists
                    if payment.booking_id:
                        booking = Booking.query.get(payment.booking_id)
                        if booking and booking.status == 'pending_payment':
                            booking.status = 'cancelled'
                            try:
                                broker.publish(booking.trip_id, {"type": "seat_cancelled", "seat": booking.seat_number, "status": "available"})
                            except Exception:
                                pass
                    db.session.commit()
                    
                    # Cache the failed status
                    PaymentStatusCache.set_status(payment.id, {
                        'id': payment.id,
                        'status': payment.status,
                        'amount': float(payment.amount),
                        'payment_method': payment.payment_method,
                        'transaction_id': payment.transaction_id,
                        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                        'message': 'Incorrect M-Pesa PIN entered.'
                    })
                else:
                    # Other failure codes
                    payment.status = 'failed'
                    if payment.booking_id:
                        booking = Booking.query.get(payment.booking_id)
                        if booking and booking.status == 'pending_payment':
                            booking.status = 'cancelled'
                            try:
                                broker.publish(booking.trip_id, {"type": "seat_cancelled", "seat": booking.seat_number, "status": "available"})
                            except Exception:
                                pass
                    db.session.commit()

                    PaymentStatusCache.set_status(payment.id, {
                        'id': payment.id,
                        'status': payment.status,
                        'amount': float(payment.amount),
                        'payment_method': payment.payment_method,
                        'transaction_id': payment.transaction_id,
                        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                        'message': 'Your payment could not be completed. Please try again.'
                    })
            else:
                # API call failed, cache the current status to avoid repeated calls
                PaymentStatusCache.set_status(payment.id, {
                    'id': payment.id,
                    'status': payment.status,
                    'amount': float(payment.amount),
                    'payment_method': payment.payment_method,
                    'transaction_id': payment.transaction_id,
                    'payment_date': payment.payment_date.isoformat() if payment.payment_date else None
                })
        
        return jsonify({
            'status': 'success',
            'payment': {
                'id': payment.id,
                'amount': str(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'transaction_id': payment.transaction_id,
                'created_at': payment.payment_date.isoformat() if payment.payment_date else None,
                'message': (PaymentStatusCache.get_status(payment.id) or {}).get('message')
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Error checking payment status: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Failed to check payment status'
        }), 500

@payment_bp.route('/<int:payment_id>', methods=['GET'])
@login_required
def get_payment(payment_id):
    """Get payment details"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Ensure the user has permission to view this payment
    if payment.user_id != current_user.id and not current_user.is_admin:
        return jsonify({
            'status': 'error',
            'message': 'Unauthorized'
        }), 403
    
    return jsonify({
        'status': 'success',
        'payment': {
            'id': payment.id,
            'amount': str(payment.amount),
            'status': payment.status,
            'payment_method': payment.payment_method,
            'transaction_id': payment.transaction_id,
            'created_at': payment.payment_date.isoformat() if payment.payment_date else None
        }
    })

@payment_bp.route('/history', methods=['GET'])
@login_required
def payment_history():
    """Get payment history for the current user"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Payment.query.filter_by(user_id=current_user.id)
    payments = query.order_by(Payment.payment_date.desc()).paginate(page=page, per_page=per_page)
    
    return jsonify({
        'status': 'success',
        'payments': [{
            'id': p.id,
            'amount': str(p.amount),
            'status': p.status,
            'payment_method': p.payment_method,
            'transaction_id': p.transaction_id,
            'date': p.payment_date.isoformat() if p.payment_date else None,
            'reference': f'Booking #{p.booking_id}' if p.booking_id else f'Parcel #{p.parcel_id}'
        } for p in payments.items],
        'pagination': {
            'page': payments.page,
            'per_page': payments.per_page,
            'total': payments.total,
            'pages': payments.pages
        }
    })
