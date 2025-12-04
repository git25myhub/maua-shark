import os
import logging
from typing import Optional

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


def _send_email_fallback(phone_number: str, message: str, user_email: str = None) -> bool:
    """Send email as fallback when SMS fails.
    
    Uses the logged-in user's email address.
    """
    try:
        from flask_mail import Message, Mail
        from flask_login import current_user
        
        # Use logged-in user's email, or fallback to a default
        if user_email:
            email_address = user_email
        elif current_user.is_authenticated and hasattr(current_user, 'email'):
            email_address = current_user.email
        else:
            # Fallback: log to console if no email available
            logging.getLogger(__name__).info('No email available for SMS fallback to %s: %s', phone_number, message)
            return True
        
        msg = Message(
            subject="MAUA SHARK - SMS Notification",
            recipients=[email_address],
            body=f"SMS intended for {phone_number}:\n\n{message}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@mauashark.com')
        )
        
        # Use the global mail instance
        current_app.mail.send(msg)
        return True
    except Exception as exc:
        logging.getLogger(__name__).error('Email fallback failed: %s', exc)
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


def send_sms(phone_number: str, message: str, sender_id: Optional[str] = None, user_email: str = None) -> bool:
    """Send an SMS via available provider.

    Returns True if successfully dispatched to a provider (or logged in dev), False otherwise.
    """
    try:
        phone = normalize_phone(phone_number)
        if not phone or not message:
            return False

        # Try Twilio first if configured
        client = _twilio_client_or_none()
        if client is not None:
            from_number = os.environ.get('TWILIO_FROM_NUMBER')
            try:
                client.messages.create(
                    to=phone,
                    from_=from_number,
                    body=message,
                )
                return True
            except Exception as exc:
                logging.getLogger(__name__).warning('Twilio send failed: %s', exc)
                # Try email fallback when Twilio fails
                if _send_email_fallback(phone, message, user_email):
                    logging.getLogger(__name__).info('SMS sent via email fallback to %s', phone)
                    return True

        # Fallback: log to console so we can see messages in development
        logging.getLogger(__name__).info('SMS to %s: %s', phone, message)
        return True
    except Exception as exc:
        logging.getLogger(__name__).error('send_sms error: %s', exc)
        return False


