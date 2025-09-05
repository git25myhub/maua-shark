from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, make_response
from flask_login import login_required, current_user
from maua.extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from .models import Parcel
from maua.notifications.sms import send_sms
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO

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

@parcels_bp.route('/receipt/<int:parcel_id>')
@login_required
def receipt(parcel_id):
    """Generate and download parcel receipt as PDF"""
    parcel = Parcel.query.get_or_404(parcel_id)
    
    # Ensure user owns this parcel
    if parcel.created_by != current_user.id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('parcels.index'))
    
    # Only allow receipt for paid parcels
    if parcel.payment_status != 'paid':
        flash('Receipt is only available for paid parcels.', 'warning')
        return redirect(url_for('parcels.index'))
    
    # Get the payment record
    payment = parcel.payment
    if not payment:
        flash('Payment record not found.', 'danger')
        return redirect(url_for('parcels.index'))
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#007bff')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#007bff')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Build PDF content
    story = []
    
    # Company Header
    story.append(Paragraph("Maua Sacco", title_style))
    story.append(Paragraph("Parcel Delivery Service", normal_style))
    story.append(Spacer(1, 20))
    
    # Receipt Title
    story.append(Paragraph("PARCEL RECEIPT", heading_style))
    story.append(Spacer(1, 10))
    
    # Receipt Info Table
    receipt_data = [
        ['Receipt #:', parcel.ref_code, 'Date:', parcel.created_at.strftime('%B %d, %Y')],
        ['Time:', parcel.created_at.strftime('%I:%M %p'), 'Status:', parcel.status.replace('_', ' ').title()],
    ]
    
    receipt_table = Table(receipt_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.5*inch])
    receipt_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(receipt_table)
    story.append(Spacer(1, 20))
    
    # Parcel Details
    story.append(Paragraph("PARCEL INFORMATION", heading_style))
    
    # Format weight properly
    weight_str = f"{parcel.weight_kg:.1f} kg" if parcel.weight_kg else "0.0 kg"
    
    parcel_data = [
        ['Reference Code:', parcel.ref_code],
        ['Weight:', weight_str],
        ['Route:', f"{parcel.origin_name} → {parcel.destination_name}"],
    ]
    
    parcel_table = Table(parcel_data, colWidths=[2*inch, 4*inch])
    parcel_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(parcel_table)
    story.append(Spacer(1, 15))
    
    # Sender and Receiver Details
    story.append(Paragraph("SENDER & RECEIVER DETAILS", heading_style))
    
    contact_data = [
        ['Sender Name:', parcel.sender_name, 'Receiver Name:', parcel.receiver_name],
        ['Sender Phone:', parcel.sender_phone, 'Receiver Phone:', parcel.receiver_phone],
    ]
    
    contact_table = Table(contact_data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
    contact_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(contact_table)
    story.append(Spacer(1, 15))
    
    # Payment Details
    story.append(Paragraph("PAYMENT INFORMATION", heading_style))
    
    payment_data = [
        ['Amount:', f"KES {float(parcel.price):.2f}"],
        ['Payment Method:', payment.payment_method.replace('_', ' ').title()],
        ['Transaction ID:', payment.transaction_id or 'N/A'],
        ['Payment Status:', payment.status.title()],
    ]
    
    payment_table = Table(payment_data, colWidths=[2*inch, 4*inch])
    payment_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph("Thank you for choosing Maua Sacco!", normal_style))
    story.append(Paragraph("For inquiries, contact us at: +254 XXX XXX XXX", normal_style))
    story.append(Paragraph("Email: info@mauasacco.co.ke", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("This is a computer-generated receipt. No signature required.", 
                          ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.grey)))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Create response
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=receipt_{parcel.ref_code}.pdf'
    
    return response