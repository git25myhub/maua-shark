from flask import Flask
import os
from .extensions import db, bcrypt, login_manager, migrate
from flask_mail import Mail


def create_app(config_class='config.DevelopmentConfig'):
    app = Flask(__name__, 
                static_folder='static', 
                static_url_path='/static')
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(__file__), '..', 'migrations'))
    
    # Initialize Flask-Mail
    mail = Mail()
    mail.init_app(app)
    
    # Make mail available globally
    app.mail = mail
    
    # Create database directory if it doesn't exist
    db_dir = os.path.join(app.instance_path, 'database')
    os.makedirs(db_dir, exist_ok=True)
    
    # Register blueprints
    from maua.auth.routes import auth_bp
    from maua.main.routes import main_bp
    from maua.main.health import health_bp
    from maua.booking.routes import booking_bp
    from maua.parcels.routes import parcels_bp
    from maua.admin.routes import admin_bp
    from maua.payment.routes import payment_bp
    from maua.catalog.routes import bp as catalog_bp
    from maua.staff import staff_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(parcels_bp, url_prefix='/parcels')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(payment_bp)
    app.register_blueprint(catalog_bp, url_prefix='/catalog')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    
    # Create upload folder if it doesn't exist
    os.makedirs(os.path.join(app.instance_path, 'uploads'), exist_ok=True)
    
    # Import models to ensure they are registered with SQLAlchemy
    with app.app_context():
        from maua.auth import models as auth_models
        from maua.catalog import models as catalog_models
        from maua.booking import models as booking_models
        from maua.payment import models as payment_models
    
    return app