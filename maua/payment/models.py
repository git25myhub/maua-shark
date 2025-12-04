from datetime import datetime
from maua.extensions import db

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # mpesa, card, cash
    transaction_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, refunded
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=True)
    # Relationship is handled by backref in Booking model
    
    parcel_id = db.Column(db.Integer, db.ForeignKey('parcels.id'), nullable=True)
    # Relationship with Parcel is handled by backref in Parcel model
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Relationship with User is handled by backref 'user_payments' in User model
    
    def __repr__(self):
        return f'<Payment {self.transaction_id} - {self.amount}>'
