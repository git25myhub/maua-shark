"""
Payment status caching module to reduce external API calls
"""
import time
from typing import Dict, Optional, Any
from flask import current_app

class PaymentStatusCache:
    """Simple in-memory cache for payment status to reduce M-Pesa API calls"""
    
    _cache: Dict[str, Dict[str, Any]] = {}
    _cache_ttl = 30  # Cache for 30 seconds
    
    @classmethod
    def get_status(cls, payment_id: int) -> Optional[Dict[str, Any]]:
        """Get cached payment status"""
        cache_key = str(payment_id)
        if cache_key in cls._cache:
            cached_data = cls._cache[cache_key]
            # Check if cache is still valid
            if time.time() - cached_data['timestamp'] < cls._cache_ttl:
                current_app.logger.debug(f"Cache hit for payment {payment_id}")
                return cached_data['data']
            else:
                # Remove expired cache entry
                del cls._cache[cache_key]
        return None
    
    @classmethod
    def set_status(cls, payment_id: int, status_data: Dict[str, Any]) -> None:
        """Cache payment status"""
        cache_key = str(payment_id)
        cls._cache[cache_key] = {
            'data': status_data,
            'timestamp': time.time()
        }
        current_app.logger.debug(f"Cached status for payment {payment_id}")
    
    @classmethod
    def invalidate(cls, payment_id: int) -> None:
        """Remove payment from cache"""
        cache_key = str(payment_id)
        if cache_key in cls._cache:
            del cls._cache[cache_key]
            current_app.logger.debug(f"Invalidated cache for payment {payment_id}")
    
    @classmethod
    def clear_expired(cls) -> None:
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, data in cls._cache.items()
            if current_time - data['timestamp'] >= cls._cache_ttl
        ]
        for key in expired_keys:
            del cls._cache[key]
        if expired_keys:
            current_app.logger.debug(f"Cleared {len(expired_keys)} expired cache entries")
