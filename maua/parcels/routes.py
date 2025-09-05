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
        parcels = Parcel.query.order_by(Parcel.created_at.desc()).limit(200).all()
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
        )
        db.session.add(parcel)
        db.session.commit()
        # SMS: notify both sender and receiver on creation
        try:
            msg_sender = (
                f"Maua Shark: Parcel {ref_code} created from {origin_name} to {destination_name}. "
                f"Receiver: {receiver_name} ({receiver_phone}). Price KES {price}."
            )
            msg_receiver = (
                f"Maua Shark: A parcel for you ({receiver_name}) has been created. Ref {ref_code}. "
                f"From {sender_name} ({sender_phone}) to be sent to {destination_name}."
            )
            send_sms(sender_phone, msg_sender, user_email=current_user.email)
            send_sms(receiver_phone, msg_receiver, user_email=current_user.email)
        except Exception:
            pass
        flash('Parcel created successfully!', 'success')
        return redirect(url_for('parcels.index'))
    return render_template('parcels/create.html')