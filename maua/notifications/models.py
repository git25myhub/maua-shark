from datetime import datetime
from maua.extensions import db


class Notification(db.Model):
    """Notification model for both staff and customers"""
    __tablename__ = "notifications"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # Null for staff notifications
    
    # Notification type: booking, trip, parcel, system
    notification_type = db.Column(db.String(30), nullable=False)
    
    # Target audience: 'customer', 'staff', 'all'
    audience = db.Column(db.String(20), default='customer')
    
    # Title and message
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Icon and color for UI
    icon = db.Column(db.String(50), default='fa-bell')
    color = db.Column(db.String(20), default='primary')  # Bootstrap color class
    
    # Link to related resource
    link = db.Column(db.String(255), nullable=True)
    
    # Reference IDs for related objects
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id"), nullable=True)
    parcel_id = db.Column(db.Integer, db.ForeignKey("parcels.id"), nullable=True)
    
    # Status
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title[:30]}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'notification_type': self.notification_type,
            'audience': self.audience,
            'title': self.title,
            'message': self.message,
            'icon': self.icon,
            'color': self.color,
            'link': self.link,
            'booking_id': self.booking_id,
            'trip_id': self.trip_id,
            'parcel_id': self.parcel_id,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'time_ago': self._time_ago()
        }
    
    def _time_ago(self):
        """Return human-readable time ago string"""
        if not self.created_at:
            return ''
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f'{mins}m ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours}h ago'
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f'{days}d ago'
        else:
            return self.created_at.strftime('%b %d')
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
    
    @classmethod
    def create_for_customer(cls, user_id, notification_type, title, message, 
                           icon='fa-bell', color='primary', link=None,
                           booking_id=None, trip_id=None, parcel_id=None):
        """Create a notification for a specific customer"""
        notification = cls(
            user_id=user_id,
            notification_type=notification_type,
            audience='customer',
            title=title,
            message=message,
            icon=icon,
            color=color,
            link=link,
            booking_id=booking_id,
            trip_id=trip_id,
            parcel_id=parcel_id
        )
        db.session.add(notification)
        return notification
    
    @classmethod
    def create_for_staff(cls, notification_type, title, message,
                        icon='fa-bell', color='primary', link=None,
                        booking_id=None, trip_id=None, parcel_id=None):
        """Create a notification for all staff members"""
        notification = cls(
            user_id=None,  # Staff notifications don't have a specific user
            notification_type=notification_type,
            audience='staff',
            title=title,
            message=message,
            icon=icon,
            color=color,
            link=link,
            booking_id=booking_id,
            trip_id=trip_id,
            parcel_id=parcel_id
        )
        db.session.add(notification)
        return notification
    
    @classmethod
    def get_unread_count_for_customer(cls, user_id):
        """Get unread notification count for a customer"""
        return cls.query.filter(
            cls.user_id == user_id,
            cls.audience == 'customer',
            cls.is_read == False
        ).count()
    
    @classmethod
    def get_unread_count_for_staff(cls):
        """Get unread notification count for staff (shared notifications)"""
        return cls.query.filter(
            cls.audience == 'staff',
            cls.is_read == False
        ).count()
    
    @classmethod
    def get_recent_for_customer(cls, user_id, limit=20):
        """Get recent notifications for a customer"""
        return cls.query.filter(
            cls.user_id == user_id,
            cls.audience == 'customer'
        ).order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_recent_for_staff(cls, limit=20):
        """Get recent notifications for staff"""
        return cls.query.filter(
            cls.audience == 'staff'
        ).order_by(cls.created_at.desc()).limit(limit).all()

