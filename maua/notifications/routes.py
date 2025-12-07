from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from maua.extensions import db
from maua.notifications.models import Notification
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


def staff_or_admin_required(f):
    """Decorator to require staff or admin role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if not (current_user.is_admin or current_user.is_staff):
            return jsonify({'error': 'Staff access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# CUSTOMER NOTIFICATION ENDPOINTS
# ============================================================================

@notifications_bp.route('/api/customer/list')
@login_required
def customer_list():
    """Get notifications for the current customer"""
    notifications = Notification.get_recent_for_customer(current_user.id, limit=30)
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': Notification.get_unread_count_for_customer(current_user.id)
    })


@notifications_bp.route('/api/customer/unread-count')
@login_required
def customer_unread_count():
    """Get unread notification count for customer"""
    count = Notification.get_unread_count_for_customer(current_user.id)
    return jsonify({'unread_count': count})


@notifications_bp.route('/api/customer/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def customer_mark_read(notification_id):
    """Mark a notification as read"""
    notification = Notification.query.filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    notification.mark_as_read()
    db.session.commit()
    
    return jsonify({'success': True})


@notifications_bp.route('/api/customer/mark-all-read', methods=['POST'])
@login_required
def customer_mark_all_read():
    """Mark all notifications as read for customer"""
    Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.audience == 'customer',
        Notification.is_read == False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/api/customer/clear-all', methods=['POST'])
@login_required
def customer_clear_all():
    """Delete all notifications for customer"""
    Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.audience == 'customer'
    ).delete()
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'All notifications cleared'})


# ============================================================================
# STAFF NOTIFICATION ENDPOINTS
# ============================================================================

@notifications_bp.route('/api/staff/list')
@login_required
@staff_or_admin_required
def staff_list():
    """Get notifications for staff"""
    notifications = Notification.get_recent_for_staff(limit=50)
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': Notification.get_unread_count_for_staff()
    })


@notifications_bp.route('/api/staff/unread-count')
@login_required
@staff_or_admin_required
def staff_unread_count():
    """Get unread notification count for staff"""
    count = Notification.get_unread_count_for_staff()
    return jsonify({'unread_count': count})


@notifications_bp.route('/api/staff/mark-read/<int:notification_id>', methods=['POST'])
@login_required
@staff_or_admin_required
def staff_mark_read(notification_id):
    """Mark a staff notification as read"""
    notification = Notification.query.filter(
        Notification.id == notification_id,
        Notification.audience == 'staff'
    ).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    notification.mark_as_read()
    db.session.commit()
    
    return jsonify({'success': True})


@notifications_bp.route('/api/staff/mark-all-read', methods=['POST'])
@login_required
@staff_or_admin_required
def staff_mark_all_read():
    """Mark all staff notifications as read"""
    Notification.query.filter(
        Notification.audience == 'staff',
        Notification.is_read == False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/api/staff/clear-all', methods=['POST'])
@login_required
@staff_or_admin_required
def staff_clear_all():
    """Delete all staff notifications"""
    Notification.query.filter(
        Notification.audience == 'staff'
    ).delete()
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'All notifications cleared'})


# ============================================================================
# NOTIFICATION VIEW PAGES
# ============================================================================

@notifications_bp.route('/customer')
@login_required
def customer_notifications_page():
    """Full page view of customer notifications"""
    notifications = Notification.get_recent_for_customer(current_user.id, limit=100)
    return render_template('notifications/customer_list.html', notifications=notifications)


@notifications_bp.route('/staff')
@login_required
@staff_or_admin_required
def staff_notifications_page():
    """Full page view of staff notifications"""
    notifications = Notification.get_recent_for_staff(limit=100)
    return render_template('notifications/staff_list.html', notifications=notifications)

