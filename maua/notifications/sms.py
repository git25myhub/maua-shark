import os
import logging
from typing import Optional
from threading import Thread

from flask import current_app


def _twilio_client_or_none():
    """Return a Twilio client if credentials exist, else None.

    This lets us run locally without breaking if env vars are missing.
    """
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_FROM_NUMBER')
    if not (account_sid and auth_token and from_number):
        return None
    try:
        from twilio.rest import Client  # type: ignore
    except Exception:
        return None
    try:
        client = Client(account_sid, auth_token)
        return client
    except Exception:
        return None


def _send_email_sync(app, email_address: str, phone_number: str, message: str) -> bool:
    """Synchronous email send (runs in background thread)."""
    logger = logging.getLogger(__name__)
    logger.info('Starting email fallback send to %s', email_address)
    try:
        from flask_mail import Message
        
        with app.app_context():
            mail = getattr(app, 'mail', None)
            if mail is None:
                # Try to get mail from extensions
                mail = app.extensions.get('mail')
            
            if mail is None:
                logger.error('Flask-Mail not configured - cannot send email fallback')
                return False
            
            msg = Message(
                subject="MAUA SHARK - SMS Notification",
                recipients=[email_address],
                body=f"SMS intended for {phone_number}:\n\n{message}",
                sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@mauashark.com')
            )
            mail.send(msg)
            logger.info('Email fallback sent successfully to %s for phone %s', email_address, phone_number)
            return True
    except Exception as exc:
        logger.error('Email fallback failed to %s: %s', email_address, exc)
        return False


def _send_email_fallback(phone_number: str, message: str, user_email: str = None) -> bool:
    """Send email as fallback when SMS fails (non-blocking).
    
    Sends email in background thread to avoid blocking the request.
    """
    try:
        # Determine recipient email - user_email takes priority
        if not user_email:
            # No email provided, just log and return success
            logging.getLogger(__name__).info('No email for SMS fallback to %s: %s', phone_number, message[:50])
            return True
        
        email_address = user_email
        
        # Get app instance for background thread
        app = current_app._get_current_object()
        
        # Send in background thread to avoid blocking
        thread = Thread(target=_send_email_sync, args=(app, email_address, phone_number, message))
        thread.daemon = True
        thread.start()
        
        logging.getLogger(__name__).info('Email fallback queued for %s', email_address)
        return True
    except Exception as exc:
        logging.getLogger(__name__).error('Email fallback setup failed: %s', exc)
        return False


def normalize_phone(phone: str) -> str:
    """Basic phone normalization. Customize as needed for KE numbers.

    - Removes spaces and dashes
    - If starts with 0 and length 10, assume KE and prefix +254
    - If starts with 254 and length 12, prefix +
    - If already starts with +, keep as is
    """
    if not phone:
        return phone
    p = phone.replace(' ', '').replace('-', '')
    if p.startswith('+'):
        return p
    if p.startswith('0') and len(p) == 10:
        return '+254' + p[1:]
    if p.startswith('254') and len(p) == 12:
        return '+' + p
    return p


def _send_twilio_async(app, client, phone: str, from_number: str, message: str, user_email: str = None):
    """Send Twilio SMS in background thread."""
    logger = logging.getLogger(__name__)
    try:
        with app.app_context():
            client.messages.create(
                to=phone,
                from_=from_number,
                body=message,
            )
            logger.info('Twilio SMS sent to %s', phone)
    except Exception as exc:
        logger.warning('Twilio send failed: %s', exc)
        # Try email fallback when Twilio fails
        if user_email:
            logger.info('Attempting email fallback to %s for phone %s', user_email, phone)
            # _send_email_sync creates its own app_context, so just call it directly
            _send_email_sync(app, user_email, phone, message)
        else:
            logger.warning('No email provided for fallback - SMS to %s will not be delivered', phone)


def send_sms(phone_number: str, message: str, sender_id: Optional[str] = None, user_email: str = None) -> bool:
    """Send an SMS via available provider (non-blocking).

    Returns True immediately after queuing the SMS. Actual delivery happens in background.
    """
    try:
        phone = normalize_phone(phone_number)
        if not phone or not message:
            return False

        # Try Twilio first if configured
        client = _twilio_client_or_none()
        if client is not None:
            from_number = os.environ.get('TWILIO_FROM_NUMBER')
            
            # Get app instance for background thread
            try:
                app = current_app._get_current_object()
                
                # Send in background thread to avoid blocking request
                thread = Thread(
                    target=_send_twilio_async, 
                    args=(app, client, phone, from_number, message, user_email)
                )
                thread.daemon = True
                thread.start()
                
                logging.getLogger(__name__).info('SMS queued for %s', phone)
                return True
            except RuntimeError:
                # No app context (e.g., during testing) - try synchronous
                try:
                    client.messages.create(to=phone, from_=from_number, body=message)
                    return True
                except Exception as exc:
                    logging.getLogger(__name__).warning('Twilio send failed: %s', exc)
                    return _send_email_fallback(phone, message, user_email)

        # No Twilio configured - log message (development mode)
        logging.getLogger(__name__).info('SMS to %s: %s', phone, message[:50])
        return True
    except Exception as exc:
        logging.getLogger(__name__).error('send_sms error: %s', exc)
        return False


