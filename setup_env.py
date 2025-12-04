#!/usr/bin/env python3
"""
Setup script to create .env file for MAUA SACCO
Run this script to automatically create your .env file
"""

import os

def create_env_file():
    """Create .env file with M-Pesa credentials"""
    
    env_content = """# MAUA SACCO Environment Configuration

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
"""
    
    # Check if .env already exists
    if os.path.exists('.env'):
        response = input("⚠️  .env file already exists. Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("❌ Setup cancelled. .env file not modified.")
            return
    
    # Create .env file
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ .env file created successfully!")
        print("🔧 Your M-Pesa credentials have been configured.")
        print("📝 You can now run your application with: python app.py")
        print("🧪 For testing, use sandbox mode with test phone numbers.")
        print("🚀 For production, change MPESA_ENVIRONMENT=production in .env")
        
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")

if __name__ == "__main__":
    print("🚀 MAUA SACCO Environment Setup")
    print("=" * 40)
    create_env_file()
