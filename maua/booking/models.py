from datetime import datetime, time
from maua.extensions import db
from maua.catalog.models import Trip

class Booking(db.Model):
    __tablename__ = "bookings"
    
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    seat_number = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(20), default="reserved")
    fare = db.Column(db.Numeric(10,2), nullable=False)
    reference = db.Column(db.String(30), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    ticket = db.relationship('Ticket', backref='booking', uselist=False, lazy=True)
    # One-to-one relationship with Payment (one booking has one payment)
    payment = db.relationship('Payment', backref=db.backref('booking', uselist=False), uselist=False)
    
    __table_args__ = (
        db.UniqueConstraint("trip_id", "seat_number", name="uq_trip_seat"),
    )

class Ticket(db.Model):
    __tablename__ = "tickets"
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    qr_code = db.Column(db.LargeBinary)  # store PNG bytes
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)