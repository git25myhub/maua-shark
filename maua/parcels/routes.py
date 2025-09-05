from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from maua.extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from .models import Parcel
from maua.notifications.sms import send_sms

parcels_bp = Blueprint('parcels', __name__)

@parcels_bp.route('/')
@login_required
def index():
    parcels = []
    try:
        # Show all user's parcels once paid, regardless of current status
        # (created, in_transit, delivered, cancelled). Excludes only unpaid drafts.
        parcels = (
            Parcel.query
            .filter(
                Parcel.created_by == current_user.id,
                Parcel.payment_status == 'paid'
            )
            .order_by(Parcel.created_at.desc())
            .limit(200)
            .all()
        )
        # If none are paid yet, fall back to showing pending_payment created by the user
        if not parcels:
            parcels = (
                Parcel.query
                .filter(
                    Parcel.created_by == current_user.id
                )
                .order_by(Parcel.created_at.desc())
                .limit(200)
                .all()
            )
    except Exception:
        parcels = []
    return render_template('parcels/index.html', parcels=parcels)


@parcels_bp.route('/track')
def track():
    """Public parcel tracking by reference code.
    Example: /parcels/track?ref=P123456789
    """
    ref = request.args.get('ref', type=str)
    parcel = None
    if ref:
        try:
            parcel = Parcel.query.filter_by(ref_code=ref.strip()).first()
        except Exception:
            parcel = None
    not_found = bool(ref and not parcel)
    return render_template('parcels/track.html', parcel=parcel, ref=ref or '', not_found=not_found)

@parcels_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        sender_name = request.form.get('sender_name')
        sender_phone = request.form.get('sender_phone')
        receiver_name = request.form.get('receiver_name')
        receiver_phone = request.form.get('receiver_phone')
        origin_name = request.form.get('origin_name')
        destination_name = request.form.get('destination_name')
        weight_kg = request.form.get('weight_kg', type=float)
        price = request.form.get('price')

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
        parcel = Parcel(
            ref_code=ref_code,
            sender_name=sender_name,
            sender_phone=sender_phone,
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            origin_name=origin_name,
            destination_name=destination_name,
            weight_kg=weight_kg,
            price=price,
            created_by=current_user.id,
            photo_filename=photo_filename,
            status="pending_payment",  # Changed to pending_payment
            payment_status="pending"
        )
        db.session.add(parcel)
        db.session.commit()
        
        # Create payment record
        from maua.payment.models import Payment
        payment = Payment(
            amount=float(price),
            payment_method='pending',
            status='pending',
            user_id=current_user.id,
            parcel_id=parcel.id
        )
        db.session.add(payment)
        db.session.commit()
        
        # Redirect to payment page
        return redirect(url_for('parcels.payment', parcel_id=parcel.id))
    return render_template('parcels/create.html')

@parcels_bp.route('/payment/<int:parcel_id>', methods=['GET', 'POST'])
@login_required
def payment(parcel_id):
    """Handle payment for parcel"""
    parcel = Parcel.query.get_or_404(parcel_id)
    
    # Ensure user owns this parcel
    if parcel.created_by != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('parcels.index'))
    
    # Check if parcel is in pending payment status
    if parcel.status != 'pending_payment':
        flash('This parcel is not pending payment.', 'warning')
        return redirect(url_for('parcels.index'))
    
    # Get the payment record
    payment = parcel.payment
    if not payment:
        flash('Payment record not found.', 'danger')
        return redirect(url_for('parcels.index'))
    
    if request.method == 'POST':
        # Handle payment form submission
        phone = request.form.get('phone')
        if not phone:
            flash('Phone number is required.', 'danger')
            return redirect(url_for('parcels.payment', parcel_id=parcel_id))
        
        # Process M-Pesa STK push directly
        try:
            from maua.payment.mpesa_service import MpesaService
            
            # Initialize M-Pesa service
            mpesa_service = MpesaService()
            
            # Generate account reference
            account_reference = f"PARCEL-{payment.id}"
            transaction_desc = f"Parcel payment for {parcel.ref_code}"
            
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
                return redirect(url_for('parcels.payment_status', parcel_id=parcel_id))
            else:
                flash(f'Payment failed: {stk_response.get("message", "Unknown error")}', 'danger')
                
        except Exception as e:
            current_app.logger.error(f"Payment request error: {str(e)}")
            flash('Payment request failed. Please try again.', 'danger')
    
    return render_template('parcels/payment.html', 
                         parcel=parcel, 
                         payment=payment)

@parcels_bp.route('/payment/status/<int:parcel_id>')
@login_required
def payment_status(parcel_id):
    """Check payment status"""
    parcel = Parcel.query.get_or_404(parcel_id)
    
    # Ensure user owns this parcel
    if parcel.created_by != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('parcels.index'))
    
    # Get the payment record
    payment = parcel.payment
    if not payment:
        flash('Payment record not found.', 'danger')
        return redirect(url_for('parcels.index'))
    
    return render_template('parcels/payment_status.html', 
                         parcel=parcel, 
                         payment=payment)