from datetime import datetime, timedelta
from flask_login import UserMixin
from maua.extensions import db, login_manager, bcrypt
import secrets
import hashlib

# This is a workaround for SQLAlchemy's handling of reserved words
# We'll use 'user_' as a prefix for all column names to avoid conflicts
# with SQL reserved words

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}  # Allow table redefinition
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_staff = db.Column(db.Boolean, default=False)  # Staff can manage bookings/parcels
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def role(self):
        """Return user role as string"""
        if self.is_admin:
            return 'admin'
        elif self.is_staff:
            return 'staff'
        return 'customer'
    
    # Relationships
    bookings = db.relationship('Booking', backref='passenger', lazy=True)
    parcels = db.relationship('Parcel', backref='sender', lazy=True)
    payments = db.relationship('Payment', backref='user_payments', lazy=True)
    
    def set_password(self, password):
        # Use bcrypt to match authentication
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class PasswordResetToken(db.Model):
    """Model for storing password reset tokens"""
    __tablename__ = 'password_reset_token'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(256), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True))
    
    # Token validity duration (30 minutes)
    TOKEN_VALIDITY_MINUTES = 30
    
    @classmethod
    def generate_token(cls, user):
        """Generate a new password reset token for a user"""
        # Invalidate any existing unused tokens for this user
        cls.query.filter_by(user_id=user.id, used=False).update({'used': True})
        db.session.commit()
        
        # Generate a secure random token
        raw_token = secrets.token_urlsafe(32)
        
        # Hash the token for storage (we'll verify against this)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Create the token record
        reset_token = cls(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(minutes=cls.TOKEN_VALIDITY_MINUTES)
        )
        
        db.session.add(reset_token)
        db.session.commit()
        
        # Return the raw token (this is what we send to the user)
        return raw_token
    
    @classmethod
    def verify_token(cls, token):
        """Verify a password reset token and return the user if valid"""
        # Hash the provided token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Find the token in the database
        reset_token = cls.query.filter_by(token_hash=token_hash, used=False).first()
        
        if not reset_token:
            return None
        
        # Check if token has expired
        if datetime.utcnow() > reset_token.expires_at:
            return None
        
        return reset_token.user
    
    @classmethod
    def use_token(cls, token):
        """Mark a token as used"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        reset_token = cls.query.filter_by(token_hash=token_hash).first()
        
        if reset_token:
            reset_token.used = True
            reset_token.used_at = datetime.utcnow()
            db.session.commit()
            return True
        return False
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired tokens (can be run periodically)"""
        expired = cls.query.filter(cls.expires_at < datetime.utcnow()).all()
        for token in expired:
            db.session.delete(token)
        db.session.commit()
    
    def __repr__(self):
        return f'<PasswordResetToken user_id={self.user_id} expires={self.expires_at}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
