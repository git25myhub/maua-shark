from datetime import datetime
from flask_login import UserMixin
from maua.extensions import db, login_manager, bcrypt

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
