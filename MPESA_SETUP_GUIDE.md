# M-Pesa Setup Guide for MAUA SACCO

## 🔧 Environment Configuration

### Step 1: Create .env File

Create a `.env` file in your project root directory (same level as `app.py`) with the following content:

```env
# MAUA SACCO Environment Configuration

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost/maua-db

# Application Configuration
SECRET_KEY=be8b97bc83215c5b8b661e27a8f2e2635eba3e6d7b2b387812e170f221fdb393
BASE_URL=http://localhost:5000

# M-Pesa Daraja API Credentials
MPESA_CONSUMER_KEY=sRJfXqDpeoDGlJPACEFKmTTkdSOndbUy964qXLbRo6YUPylf
MPESA_CONSUMER_SECRET=Xgro9DdR82NEK19ijOMmbEsNDQvJc3W0ocwSCHayZGoWgBhyAyiDoi5oBxkSAZcC
MPESA_BUSINESS_SHORT_CODE=174379
MPESA_PASSKEY=bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919

# M-Pesa Environment (sandbox for testing, production for live)
MPESA_ENVIRONMENT=sandbox

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=kariukistephen964@gmail.com
MAIL_PASSWORD=lszd yuds pgry pesv

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True

# Security
WTF_CSRF_ENABLED=True
WTF_CSRF_TIME_LIMIT=3600

# File Upload
UPLOAD_FOLDER=maua/static/uploads
MAX_CONTENT_LENGTH=16777216

# Session Configuration
PERMANENT_SESSION_LIFETIME=2592000
REMEMBER_COOKIE_DURATION=2592000
```

### Step 2: Install python-dotenv (if not already installed)

```bash
pip install python-dotenv
```

### Step 3: Update your app.py to load environment variables

Add this to the top of your `app.py` file:

```python
from dotenv import load_dotenv
load_dotenv()
```

### Step 4: Update BASE_URL for Production

When deploying to production, update the `BASE_URL` in your `.env` file:

```env
BASE_URL=https://your-domain.com
```

## 🔐 Security Notes

1. **Never commit your `.env` file to version control**
2. **Add `.env` to your `.gitignore` file**
3. **Use different credentials for development and production**
4. **Keep your M-Pesa credentials secure**

## 🧪 Testing

### Sandbox Testing
- Use `MPESA_ENVIRONMENT=sandbox` for testing
- Test with Safaricom's test phone numbers
- No real money will be charged

### Production Deployment
- Change `MPESA_ENVIRONMENT=production`
- Use your live M-Pesa credentials
- Ensure your callback URL is accessible from the internet

## 📱 M-Pesa Test Numbers (Sandbox)

For testing in sandbox mode, you can use these test numbers:
- **254708374149** - Test number 1
- **254711111111** - Test number 2
- **254722222222** - Test number 3

## 🔄 Callback URL Configuration

Make sure your callback URL is accessible:
- **Development**: `http://localhost:5000/payments/callback/mpesa`
- **Production**: `https://your-domain.com/payments/callback/mpesa`

## 🚀 Deployment Checklist

- [ ] Create `.env` file with production credentials
- [ ] Set `MPESA_ENVIRONMENT=production`
- [ ] Update `BASE_URL` to your production domain
- [ ] Ensure callback URL is accessible
- [ ] Test payment flow thoroughly
- [ ] Monitor logs for any issues

## 📞 Support

If you encounter any issues:
1. Check the application logs
2. Verify your M-Pesa credentials
3. Ensure your callback URL is accessible
4. Test with sandbox environment first
