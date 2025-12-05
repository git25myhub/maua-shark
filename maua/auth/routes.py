from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from maua import db, bcrypt
from maua.auth.forms import LoginForm, RegistrationForm
from maua.auth.models import User

auth_bp = Blueprint('auth', __name__)


def get_redirect_for_user(user):
    """Determine the appropriate redirect URL based on user role"""
    if user.is_admin:
        return url_for('admin.dashboard')
    elif user.is_staff:
        return url_for('staff.dashboard')
    else:
        return url_for('main.home')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(get_redirect_for_user(current_user))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            # Check if user account is active
            if not user.is_active:
                flash('Your account has been deactivated. Please contact administrator.', 'danger')
                return render_template('auth/login.html', title='Login', form=form)
            
            login_user(user, remember=form.remember.data)
            
            # Check for next parameter first
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            # Redirect based on user role
            if user.is_admin:
                flash(f'Welcome back, {user.username}! You are logged in as Administrator.', 'success')
                return redirect(url_for('admin.dashboard'))
            elif user.is_staff:
                flash(f'Welcome back, {user.username}! You are logged in as Staff.', 'success')
                return redirect(url_for('staff.dashboard'))
            else:
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('main.home'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    
    return render_template('auth/login.html', title='Login', form=form)


@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.home'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Public registration - creates customer accounts only"""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already taken. Please choose a different one.', 'danger')
            return render_template('auth/register.html', title='Register', form=form)
        
        # Check if email exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please use a different email or login.', 'danger')
            return render_template('auth/register.html', title='Register', form=form)
        
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            password_hash=hashed_password,
            date_joined=datetime.utcnow(),
            is_admin=False,  # Public registration creates customers only
            is_staff=False,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register', form=form)
