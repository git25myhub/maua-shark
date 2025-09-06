"""
Health check endpoints for monitoring server status
"""
from flask import Blueprint, jsonify, current_app
from maua.extensions import db
from maua.payment.cache import PaymentStatusCache
from sqlalchemy import text
import time

health_bp = Blueprint('health', __name__, url_prefix='/health')

@health_bp.route('/')
def health_check():
    """Basic health check endpoint"""
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        
        # Get cache statistics
        cache_stats = {
            'cache_size': len(PaymentStatusCache._cache),
            'cache_ttl': PaymentStatusCache._cache_ttl
        }
        
        return jsonify({
            'status': 'healthy',
            'timestamp': time.time(),
            'database': 'connected',
            'cache': cache_stats,
            'version': '1.0.0'
        }), 200
    except Exception as e:
        current_app.logger.error(f'Health check failed: {str(e)}')
        return jsonify({
            'status': 'unhealthy',
            'timestamp': time.time(),
            'error': str(e)
        }), 500

@health_bp.route('/ready')
def readiness_check():
    """Readiness check for load balancers"""
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        
        return jsonify({
            'status': 'ready',
            'timestamp': time.time()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'timestamp': time.time(),
            'error': str(e)
        }), 503

@health_bp.route('/cache/clear')
def clear_cache():
    """Clear payment status cache (for debugging)"""
    try:
        PaymentStatusCache._cache.clear()
        return jsonify({
            'status': 'success',
            'message': 'Cache cleared',
            'timestamp': time.time()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': time.time()
        }), 500
