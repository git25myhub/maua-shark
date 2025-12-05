from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from maua import db, bcrypt
from maua.auth.forms import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm
from maua.auth.models import User, PasswordResetToken

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


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password request - for customers only"""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()
        
        # Check if user is admin or staff - they cannot use self-service password reset
        if user and (user.is_admin or user.is_staff):
            flash(
                'Staff and Admin accounts cannot use self-service password reset for security reasons. '
                'Please contact the system administrator to reset your password.',
                'warning'
            )
            return render_template('auth/forgot_password.html', title='Forgot Password', form=form)
        
        # Always show the same message to prevent email enumeration (for customers)
        success_message = (
            'If a customer account with that email exists, you will receive a password reset link shortly. '
            'Please check your email inbox and spam folder.'
        )
        
        if user:
            try:
                # Generate reset token
                token = PasswordResetToken.generate_token(user)
                
                # Build reset URL
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                
                # Send reset email
                send_password_reset_email(user, reset_url)
                
                # Also send SMS notification
                send_password_reset_sms(user, reset_url)
                
                current_app.logger.info(f'Password reset requested for {email}')
            except Exception as e:
                current_app.logger.error(f'Error sending password reset: {e}')
        
        flash(success_message, 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html', title='Forgot Password', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handle password reset with token - for customers only"""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    # Verify the token
    user = PasswordResetToken.verify_token(token)
    
    if not user:
        flash('The password reset link is invalid or has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    # Extra security: Block admin/staff from using reset tokens
    if user.is_admin or user.is_staff:
        flash(
            'Staff and Admin accounts cannot use self-service password reset. '
            'Please contact the system administrator.',
            'danger'
        )
        # Invalidate the token
        PasswordResetToken.use_token(token)
        return redirect(url_for('auth.login'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        # Update the password
        user.set_password(form.password.data)
        
        # Mark the token as used
        PasswordResetToken.use_token(token)
        
        db.session.commit()
        
        # Send confirmation email
        try:
            send_password_changed_email(user)
        except Exception as e:
            current_app.logger.error(f'Error sending password change confirmation: {e}')
        
        flash('Your password has been reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', title='Reset Password', form=form, token=token)


# =============================================================================
# EMAIL FUNCTIONS
# =============================================================================

def send_password_reset_email(user, reset_url):
    """Send password reset email to user"""
    try:
        from flask_mail import Message
        
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 30px; }}
        .reset-box {{ background: #fef2f2; border: 2px solid #dc2626; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center; }}
        .reset-button {{ display: inline-block; background: #dc2626; color: white; padding: 15px 40px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px; margin: 20px 0; }}
        .reset-button:hover {{ background: #b91c1c; }}
        .warning {{ background: #fef3c7; padding: 15px; border-radius: 8px; border-left: 4px solid #f59e0b; margin: 20px 0; }}
        .footer {{ background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }}
        .link-text {{ word-break: break-all; font-size: 12px; color: #64748b; background: #f1f5f9; padding: 10px; border-radius: 4px; margin-top: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Password Reset Request</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{user.username}</strong>,</p>
            <p>We received a request to reset your password for your MAUA SHARK SACCO account.</p>
            
            <div class="reset-box">
                <p style="margin: 0 0 15px; color: #dc2626; font-weight: 600;">Click the button below to reset your password:</p>
                <a href="{reset_url}" class="reset-button">Reset My Password</a>
                <p style="margin: 15px 0 0; color: #64748b; font-size: 14px;">This link expires in 30 minutes.</p>
            </div>
            
            <div class="warning">
                <p style="margin: 0; color: #92400e;"><strong>⚠️ Security Notice:</strong></p>
                <p style="margin: 5px 0 0; color: #92400e;">If you did not request this password reset, please ignore this email. Your password will remain unchanged.</p>
            </div>
            
            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <div class="link-text">{reset_url}</div>
            
            <p style="margin-top: 20px;">If you have any questions, please contact our support team.</p>
        </div>
        <div class="footer">
            <p>© {datetime.now().year} MAUA SHARK SACCO. All Rights Reserved.</p>
            <p>This is an automated message. Please do not reply directly to this email.</p>
        </div>
    </div>
</body>
</html>
'''
        
        msg = Message(
            subject="MAUA SHARK - Password Reset Request",
            recipients=[user.email],
            html=html_content,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@mauashark.com')
        )
        
        current_app.mail.send(msg)
        current_app.logger.info(f'Password reset email sent to {user.email}')
        
    except Exception as e:
        current_app.logger.error(f'Failed to send password reset email: {e}')
        raise


def send_password_reset_sms(user, reset_url):
    """Send password reset SMS notification"""
    try:
        from maua.notifications.sms import send_sms
        
        message = (
            f"MAUA SHARK: Password reset requested for your account. "
            f"If this was you, check your email ({user.email}) for the reset link. "
            f"Link expires in 30 mins. If not you, ignore this message."
        )
        
        send_sms(user.phone, message, user_email=user.email)
        
    except Exception as e:
        current_app.logger.error(f'Failed to send password reset SMS: {e}')


def send_password_changed_email(user):
    """Send confirmation email after password change"""
    try:
        from flask_mail import Message
        
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 20px auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #059669 0%, #10b981 100%); color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; }}
        .success-box {{ background: #f0fdf4; border: 2px solid #059669; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center; }}
        .success-icon {{ font-size: 48px; }}
        .warning {{ background: #fef2f2; padding: 15px; border-radius: 8px; border-left: 4px solid #dc2626; margin: 20px 0; }}
        .footer {{ background: #1e293b; color: #94a3b8; padding: 20px; text-align: center; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Password Changed Successfully</h1>
        </div>
        <div class="content">
            <p>Hello <strong>{user.username}</strong>,</p>
            
            <div class="success-box">
                <div class="success-icon">🔒</div>
                <h2 style="color: #059669; margin: 10px 0;">Your password has been changed!</h2>
                <p style="color: #64748b; margin: 0;">Your MAUA SHARK SACCO account password was successfully updated.</p>
            </div>
            
            <p><strong>Change Details:</strong></p>
            <ul>
                <li>Account: {user.email}</li>
                <li>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
            
            <div class="warning">
                <p style="margin: 0; color: #dc2626;"><strong>🚨 Didn't make this change?</strong></p>
                <p style="margin: 5px 0 0; color: #dc2626;">
                    If you did not change your password, your account may be compromised. 
                    Please contact our support team immediately at support@mauashark.com
                </p>
            </div>
            
            <p>You can now log in with your new password.</p>
        </div>
        <div class="footer">
            <p>© {datetime.now().year} MAUA SHARK SACCO. All Rights Reserved.</p>
        </div>
    </div>
</body>
</html>
'''
        
        msg = Message(
            subject="MAUA SHARK - Password Changed Successfully",
            recipients=[user.email],
            html=html_content,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@mauashark.com')
        )
        
        current_app.mail.send(msg)
        
        # Also send SMS notification
        from maua.notifications.sms import send_sms
        sms_msg = (
            f"MAUA SHARK: Your password was just changed. "
            f"If this was you, no action needed. "
            f"If not, contact support immediately!"
        )
        send_sms(user.phone, sms_msg, user_email=user.email)
        
    except Exception as e:
        current_app.logger.error(f'Failed to send password changed confirmation: {e}')
