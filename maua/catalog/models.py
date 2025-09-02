from datetime import datetime
from maua.extensions import db

class Depot(db.Model):
    __tablename__ = "depots"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    town = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    
    # Relationships
    origin_routes = db.relationship('Route', foreign_keys='Route.origin_depot_id', backref='origin', lazy=True)
    destination_routes = db.relationship('Route', foreign_keys='Route.destination_depot_id', backref='destination', lazy=True)
    
    def __repr__(self):
        return f'<Depot {self.name}, {self.town}>'

class Route(db.Model):
    __tablename__ = "routes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    origin_depot_id = db.Column(db.Integer, db.ForeignKey("depots.id"), nullable=False)
    destination_depot_id = db.Column(db.Integer, db.ForeignKey("depots.id"), nullable=False)
    distance_km = db.Column(db.Float)
    active = db.Column(db.Boolean, default=True)
    estimated_duration = db.Column(db.Interval)  # Estimated travel time
    
    # Relationships
    trips = db.relationship('Trip', backref='route', lazy=True)
    
    def __repr__(self):
        return f'<Route {self.code}: {self.origin.town} to {self.destination.town}>'

class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    plate_no = db.Column(db.String(20), unique=True, nullable=False)
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.Integer)
    seat_count = db.Column(db.Integer, default=14)
    seat_layout = db.Column(db.JSON)  # [{"seat":"1","label":"1A"}, ...]
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    trips = db.relationship('Trip', backref='vehicle', lazy=True)
    
    def __repr__(self):
        return f'<Vehicle {self.plate_no} ({self.make} {self.model})>'

class Trip(db.Model):
    __tablename__ = "trips"
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    depart_at = db.Column(db.DateTime(timezone=True), index=True, nullable=False)
    arrive_eta = db.Column(db.DateTime(timezone=True))
    base_fare = db.Column(db.Numeric(10,2), nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('Booking', backref='trip', lazy=True)
    parcels = db.relationship('Parcel', backref='trip', lazy=True)
    
    def __repr__(self):
        return f'<Trip {self.id}: {self.route} on {self.depart_at}>'
    
    @property
    def available_seats(self):
        # Returns a list of available seat numbers
        if not self.vehicle or not self.vehicle.seat_layout:
            return []
        
        booked_seats = {booking.seat_number for booking in self.bookings 
                       if booking.status in ['confirmed', 'reserved']}
        
        return [seat['seat'] for seat in self.vehicle.seat_layout 
               if seat['seat'] not in booked_seats]

class Parcel(db.Model):
    __tablename__ = "parcels"
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_name = db.Column(db.String(100), nullable=False)
    recipient_phone = db.Column(db.String(20), nullable=False)
    recipient_id_number = db.Column(db.String(20))
    description = db.Column(db.Text)
    weight_kg = db.Column(db.Float, nullable=False)
    length_cm = db.Column(db.Float)
    width_cm = db.Column(db.Float)
    height_cm = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, in_transit, delivered, cancelled
    tracking_number = db.Column(db.String(20), unique=True)
    fare = db.Column(db.Numeric(10, 2))
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # One-to-one relationship with Payment
    payment = db.relationship('Payment', backref='parcel', uselist=False, foreign_keys='Payment.parcel_id')
    
    def __repr__(self):
        return f'<Parcel {self.tracking_number}: {self.status}>'