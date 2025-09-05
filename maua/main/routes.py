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

@main_bp.route('/terms')
def terms():
    return render_template('legal/terms.html', title='Terms of Service', now=datetime.utcnow())

@main_bp.route('/privacy')
def privacy():
    return render_template('legal/privacy.html', title='Privacy Policy', now=datetime.utcnow())

@main_bp.route('/faq')
def faq():
    return render_template('help/faq.html', title='FAQs')

@main_bp.route('/announcements')
def announcements():
    return render_template('news/announcements.html', title='Announcements')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', title='Dashboard')
