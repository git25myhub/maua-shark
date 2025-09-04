from datetime import datetime
from maua.extensions import db


class Parcel(db.Model):
    __tablename__ = "parcels"
    id = db.Column(db.Integer, primary_key=True)
    ref_code = db.Column(db.String(20), unique=True, nullable=False)
    sender_name = db.Column(db.String(120), nullable=False)
    sender_phone = db.Column(db.String(30), nullable=False)
    receiver_name = db.Column(db.String(120), nullable=False)
    receiver_phone = db.Column(db.String(30), nullable=False)
    origin_name = db.Column(db.String(120), nullable=False)
    destination_name = db.Column(db.String(120), nullable=False)
    weight_kg = db.Column(db.Float)
    price = db.Column(db.Numeric(10,2), nullable=False)
    status = db.Column(db.String(20), default="created")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photo_filename = db.Column(db.String(255))


class ParcelEvent(db.Model):
    __tablename__ = "parcel_events"
    id = db.Column(db.Integer, primary_key=True)
    # Add fields later as needed (e.g., parcel_id, event, created_at)