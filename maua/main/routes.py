from flask import render_template, Blueprint, flash, redirect, url_for
from flask_login import current_user, login_required
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/home')
def home():
    return render_template('home.html', title='Home')

@main_bp.route('/about')
def about():
    return render_template('about.html', title='About Us')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html', title='Contact Us')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', title='Dashboard')
