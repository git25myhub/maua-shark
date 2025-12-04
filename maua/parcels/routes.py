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
from maua.payment.cache import PaymentStatusCache

parcels_bp = Blueprint('parcels', __name__)

@parcels_bp.route('/')
def index():
    """
    Public parcel tracking page.
    Customers can track parcels by reference code - they don't create parcels.
    Parcel creation is handled by staff at the depot.
    """
    return redirect(url_for('parcels.track'))


@parcels_bp.route('/track')
def track():
    """Public parcel tracking by reference code.
    Example: /parcels/track?ref=P123456789
    
    Customers track parcels here. Parcel creation is done by staff at depots.
    """
    ref = request.args.get('ref', type=str)
    phone = request.args.get('phone', type=str)  # Optional: track by phone number
    parcel = None
    parcels_list = []
    
    if ref:
        try:
            parcel = Parcel.query.filter_by(ref_code=ref.strip()).first()
        except Exception:
            parcel = None
    elif phone:
        # Allow tracking by sender or receiver phone
        try:
            parcels_list = Parcel.query.filter(
                (Parcel.sender_phone == phone.strip()) | 
                (Parcel.receiver_phone == phone.strip())
            ).order_by(Parcel.created_at.desc()).limit(20).all()
        except Exception:
            parcels_list = []
    
    not_found = bool((ref and not parcel) or (phone and not parcels_list))
    return render_template('parcels/track.html', 
                          parcel=parcel, 
                          parcels_list=parcels_list,
                          ref=ref or '', 
                          phone=phone or '',
                          not_found=not_found)


@parcels_bp.route('/create', methods=['GET', 'POST'])
def create():
    """
    Parcel creation is now handled by staff at depots.
    Redirect customers to tracking page with instructions.
    """
    flash('To send a parcel, please visit any Maua Shark Sacco depot. '
          'Our staff will help you register your parcel and provide a tracking code.', 'info')
    return redirect(url_for('parcels.track'))

@parcels_bp.route('/status/<ref_code>')
def status(ref_code):
    """View parcel status by reference code - public access"""
    parcel = Parcel.query.filter_by(ref_code=ref_code).first()
    if not parcel:
        flash('Parcel not found.', 'warning')
        return redirect(url_for('parcels.track'))
    return render_template('parcels/status.html', parcel=parcel)
