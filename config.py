import os
from datetime import timedelta


class Config:
    # App settings
    SECRET_KEY = 'be8b97bc83215c5b8b661e27a8f2e2635eba3e6d7b2b387812e170f221fdb393'  # Generated secure key
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost/maua-db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection pooling for memory optimization
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,           # Number of connections to maintain in pool
        'max_overflow': 10,       # Additional connections beyond pool_size
        'pool_timeout': 30,       # Seconds to wait for connection from pool
        'pool_recycle': 3600,     # Recycle connections after 1 hour
        'pool_pre_ping': True,    # Validate connections before use
    }
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    
    # Security settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # File upload settings
    UPLOAD_FOLDER = os.path.join('maua', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Email settings - Using SendGrid SMTP relay (works on cloud platforms like Render)
    # SendGrid: smtp.sendgrid.net, port 587, TLS, username="apikey", password=<API_KEY>
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.sendgrid.net')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'apikey')  # SendGrid uses "apikey" as username
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')  # SendGrid API key goes here
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@mauashark.com')
    MAIL_TIMEOUT = 30  # 30 second timeout for email operations
    
    # SendGrid API key (alternative to SMTP - for future use)
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', os.environ.get('MAIL_PASSWORD', ''))
    
    # M-Pesa settings
    BASE_URL = os.environ.get('BASE_URL') or 'http://localhost:5000'
    
    # M-Pesa API Credentials
    MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY')
    MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET')
    MPESA_BUSINESS_SHORT_CODE = os.environ.get('MPESA_BUSINESS_SHORT_CODE')
    MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY')
    MPESA_ENVIRONMENT = os.environ.get('MPESA_ENVIRONMENT', 'sandbox')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False  # Set to False to disable SQL query logging
    
    @classmethod
    def init_app(cls, app):
        # Configure logging
        import logging
        from logging.handlers import RotatingFileHandler
        import os
        
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')
            
        # Set SQLAlchemy logging level to WARNING to reduce noise
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        
        # File handler for application logs
        file_handler = RotatingFileHandler('logs/maua.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        
        # Add handlers to the root logger
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Maua Sacco startup')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to stderr
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}