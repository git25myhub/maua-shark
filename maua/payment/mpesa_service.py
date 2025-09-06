import requests
import base64
from datetime import datetime
import json
from flask import current_app
import uuid

class MpesaService:
    # Class-level caches shared across instances (single-process only)
    _cached_access_token = None
    _cached_token_expiry_epoch = 0
    _last_query_epoch_by_checkout_id = {}
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super(MpesaService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
            
        import os
        self.consumer_key = os.environ.get('MPESA_CONSUMER_KEY', 'sRJfXqDpeoDGlJPACEFKmTTkdSOndbUy964qXLbRo6YUPylf')
        self.consumer_secret = os.environ.get('MPESA_CONSUMER_SECRET', 'Xgro9DdR82NEK19ijOMmbEsNDQvJc3W0ocwSCHayZGoWgBhyAyiDoi5oBxkSAZcC')
        self.business_short_code = os.environ.get('MPESA_BUSINESS_SHORT_CODE', '174379')
        self.passkey = os.environ.get('MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
        
        # Set base URL based on environment
        environment = os.environ.get('MPESA_ENVIRONMENT', 'sandbox')
        if environment == 'production':
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.base_url = "https://sandbox.safaricom.co.ke"
        
        # Only log configuration once
        if not hasattr(MpesaService, '_config_logged'):
            current_app.logger.info(f"M-Pesa configured for {environment} environment")
            current_app.logger.info(f"Consumer key present: {bool(self.consumer_key)}")
            current_app.logger.info(f"Consumer secret present: {bool(self.consumer_secret)}")
            current_app.logger.info(f"Business short code: {self.business_short_code}")
            current_app.logger.info(f"Base URL: {self.base_url}")
            MpesaService._config_logged = True
            
        self._initialized = True
        
    def get_access_token(self):
        """Get M-Pesa access token"""
        try:
            # Reuse cached token if still valid (buffer 60s)
            import time
            if (
                MpesaService._cached_access_token
                and time.time() < MpesaService._cached_token_expiry_epoch - 60
            ):
                return MpesaService._cached_access_token

            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            
            # Create credentials string
            credentials = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3599)
            if access_token:
                MpesaService._cached_access_token = access_token
                MpesaService._cached_token_expiry_epoch = time.time() + int(expires_in)
            return access_token
            
        except requests.exceptions.HTTPError as e:
            current_app.logger.error(f"HTTP Error getting M-Pesa access token: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            current_app.logger.error(f"Error getting M-Pesa access token: {str(e)}")
            return None
    
    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK push payment"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'message': 'Failed to get access token'
                }
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            
            # Format phone number (remove + and ensure it starts with 254)
            if phone_number.startswith('+'):
                phone_number = phone_number[1:]
            if phone_number.startswith('0'):
                phone_number = '254' + phone_number[1:]
            elif not phone_number.startswith('254'):
                phone_number = '254' + phone_number
            
            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Generate password
            password_string = f"{self.business_short_code}{self.passkey}{timestamp}"
            password = base64.b64encode(password_string.encode()).decode()
            
            payload = {
                "BusinessShortCode": self.business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.business_short_code,
                "PhoneNumber": phone_number,
                "CallBackURL": f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/payments/callback/mpesa",
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'merchant_request_id': data.get('MerchantRequestID'),
                    'response_code': data.get('ResponseCode'),
                    'response_description': data.get('ResponseDescription'),
                    'customer_message': data.get('CustomerMessage')
                }
            else:
                return {
                    'success': False,
                    'message': data.get('ResponseDescription', 'STK push failed'),
                    'response_code': data.get('ResponseCode')
                }
                
        except Exception as e:
            current_app.logger.error(f"Error initiating STK push: {str(e)}")
            return {
                'success': False,
                'message': f'STK push failed: {str(e)}'
            }
    
    def query_stk_push_status(self, checkout_request_id):
        """Query STK push status"""
        try:
            # Simple in-memory throttle to avoid sandbox 429 rate limits
            import time
            now = time.time()
            last = MpesaService._last_query_epoch_by_checkout_id.get(checkout_request_id, 0)
            # enforce 15s minimum interval per CheckoutRequestID (increased from 10s)
            if now - last < 15:
                return {
                    'success': False,
                    'message': 'Query throttled locally to respect rate limits',
                }
            # Reserve the slot BEFORE making the request so bursts don't bypass throttle
            MpesaService._last_query_epoch_by_checkout_id[checkout_request_id] = now

            access_token = self.get_access_token()
            if not access_token:
                return {
                    'success': False,
                    'message': 'Failed to get access token'
                }
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_string = f"{self.business_short_code}{self.passkey}{timestamp}"
            password = base64.b64encode(password_string.encode()).decode()
            
            payload = {
                "BusinessShortCode": self.business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers)
            # If unauthorized, refresh token once and retry
            if response.status_code == 401:
                MpesaService._cached_access_token = None
                access_token = self.get_access_token()
                if not access_token:
                    return {'success': False, 'message': 'Failed to refresh access token'}
                headers['Authorization'] = f'Bearer {access_token}'
                response = requests.post(url, json=payload, headers=headers)
            # Gracefully handle sandbox rate limits
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', '10')
                return {
                    'success': False,
                    'message': 'rate_limited',
                    'retry_after': int(retry_after) if str(retry_after).isdigit() else 10,
                }
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'success': True,
                'response_code': data.get('ResponseCode'),
                'response_description': data.get('ResponseDescription'),
                'merchant_request_id': data.get('MerchantRequestID'),
                'checkout_request_id': data.get('CheckoutRequestID'),
                'result_code': data.get('ResultCode'),
                'result_desc': data.get('ResultDesc')
            }
            
        except Exception as e:
            current_app.logger.error(f"Error querying STK push status: {str(e)}")
            return {
                'success': False,
                'message': f'STK push query failed: {str(e)}'
            }
    
    def process_callback(self, callback_data):
        """Process M-Pesa callback"""
        try:
            # Extract callback data
            body = callback_data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            
            if result_code == 0:
                # Payment successful
                callback_metadata = stk_callback.get('CallbackMetadata', {})
                items = callback_metadata.get('Item', [])
                
                # Extract payment details
                payment_data = {}
                for item in items:
                    name = item.get('Name')
                    value = item.get('Value')
                    if name == 'Amount':
                        payment_data['amount'] = value
                    elif name == 'MpesaReceiptNumber':
                        payment_data['receipt_number'] = value
                    elif name == 'TransactionDate':
                        payment_data['transaction_date'] = value
                    elif name == 'PhoneNumber':
                        payment_data['phone_number'] = value
                
                return {
                    'success': True,
                    'checkout_request_id': checkout_request_id,
                    'result_code': result_code,
                    'result_desc': result_desc,
                    'payment_data': payment_data
                }
            else:
                # Payment failed
                return {
                    'success': False,
                    'checkout_request_id': checkout_request_id,
                    'result_code': result_code,
                    'result_desc': result_desc
                }
                
        except Exception as e:
            current_app.logger.error(f"Error processing M-Pesa callback: {str(e)}")
            return {
                'success': False,
                'message': f'Callback processing failed: {str(e)}'
            }
