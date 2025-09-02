from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from maua.extensions import db
from datetime import datetime

parcels_bp = Blueprint('parcels', __name__)

@parcels_bp.route('/')
@login_required
def index():
    return render_template('parcels/index.html')

@parcels_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        # Handle parcel creation logic here
        flash('Parcel created successfully!', 'success')
        return redirect(url_for('parcels.index'))
    return render_template('parcels/create.html')