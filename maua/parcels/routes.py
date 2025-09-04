from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from maua.extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from .models import Parcel

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
        flash('Parcel created successfully!', 'success')
        return redirect(url_for('parcels.index'))
    return render_template('parcels/create.html')