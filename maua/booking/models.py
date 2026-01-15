from datetime import datetime, time
from maua.extensions import db
from maua.catalog.models import Trip

class BookingSeat(db.Model):
    """Represents a seat within a booking. A booking can have multiple seats."""
    __tablename__ = "booking_seats"
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    seat_number = db.Column(db.String(5), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    booking = db.relationship('Booking', backref='booking_seats', lazy=True)
    trip = db.relationship('Trip', backref='booking_seats', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint("trip_id", "seat_number", name="uq_trip_seat_booking"),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'trip_id': self.trip_id,
            'seat_number': self.seat_number,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Booking(db.Model):
    __tablename__ = "bookings"
    
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # Made nullable - no login required
    seat_number = db.Column(db.String(5), nullable=True)  # Made nullable - use BookingSeat for multi-seat bookings
    status = db.Column(db.String(20), default="reserved")
    fare = db.Column(db.Numeric(10,2), nullable=False)  # Total fare for all seats
    reference = db.Column(db.String(30), unique=True, nullable=False)
    hold_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Passenger Details
    passenger_name = db.Column(db.String(100), nullable=False, default='Passenger')
    passenger_sex = db.Column(db.String(10), nullable=False, default='other')  # 'male', 'female', 'other'
    passenger_age = db.Column(db.Integer, nullable=False, default=18)
    passenger_phone = db.Column(db.String(20), nullable=False, default='N/A')
    passenger_email = db.Column(db.String(120), nullable=False)  # Email for notifications
    # National ID Number
    passenger_id_number = db.Column(db.String(30), nullable=False, default='N/A')
    # Optional pickup location (if passenger will be fetched on the way)
    pickup_location = db.Column(db.String(255))
    
    # Relationships
    ticket = db.relationship('Ticket', backref='booking', uselist=False, lazy=True)
    payment = db.relationship('Payment', backref=db.backref('booking', uselist=False), uselist=False)
    
    # Note: Removed unique constraint on (trip_id, seat_number) as we now use BookingSeat
    # Old constraint kept for backward compatibility but seat_number is now nullable
    
    @property
    def seats(self):
        """Get all seats for this booking. Returns list of seat numbers."""
        if self.booking_seats:
            return [bs.seat_number for bs in self.booking_seats]
        elif self.seat_number:
            # Backward compatibility: return single seat if using old format
            return [self.seat_number]
        return []
    
    @property
    def seat_count(self):
        """Get the number of seats in this booking."""
        if self.booking_seats:
            return len(self.booking_seats)
        elif self.seat_number:
            return 1
        return 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'user_id': self.user_id,
            'seat_number': self.seat_number,  # For backward compatibility
            'seats': self.seats,  # List of all seats
            'seat_count': self.seat_count,
            'status': self.status,
            'fare': float(self.fare) if self.fare else None,
            'reference': self.reference,
            'hold_expires_at': self.hold_expires_at.isoformat() if self.hold_expires_at else None,
            'passenger_name': self.passenger_name,
            'passenger_sex': self.passenger_sex,
            'passenger_age': self.passenger_age,
            'passenger_phone': self.passenger_phone,
            'passenger_email': self.passenger_email,
            'passenger_id_number': self.passenger_id_number,
            'pickup_location': self.pickup_location,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Ticket(db.Model):
    __tablename__ = "tickets"
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), unique=True, nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='valid')
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'status': self.status
        }
    qr_code = db.Column(db.LargeBinary)  # store PNG bytes
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)