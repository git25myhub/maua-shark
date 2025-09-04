from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from maua.extensions import db
from maua.payment.models import Payment
from maua.booking.models import Booking
from maua.parcels.models import Parcel
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
    """Process M-Pesa payment"""
    data = request.get_json()
    payment_id = data.get('payment_id')
    phone = data.get('phone')
    
    try:
        payment = Payment.query.get_or_404(payment_id)
        
        # TODO: Implement actual M-Pesa API integration
        # This is a placeholder for the M-Pesa payment processing logic
        mpesa_response = {
            'status': 'success',
            'transaction_id': f'MPESA{datetime.utcnow().strftime("%Y%m%d%H%M%S")}',
            'amount': str(payment.amount),
            'phone': phone
        }
        
        # Update payment status
        payment.status = 'completed'
        payment.payment_method = 'mpesa'
        payment.transaction_id = mpesa_response['transaction_id']
        payment.payment_date = datetime.utcnow()
        
        # Update related booking or parcel status
        if payment.booking_id:
            booking = Booking.query.get(payment.booking_id)
            if booking:
                booking.status = 'confirmed'
        elif payment.parcel_id:
            parcel = Parcel.query.get(payment.parcel_id)
            if parcel:
                parcel.payment_status = 'paid'
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Payment processed successfully',
            'payment': {
                'id': payment.id,
                'amount': str(payment.amount),
                'transaction_id': payment.transaction_id,
                'status': payment.status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'M-Pesa payment failed: {str(e)}')
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
        
        # TODO: Implement M-Pesa callback processing
        # This should validate the callback and update the payment status
        
        return jsonify({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        current_app.logger.error(f'Error processing M-Pesa callback: {str(e)}')
        return jsonify({'ResultCode': 1, 'ResultDesc': 'Error'}), 500

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
