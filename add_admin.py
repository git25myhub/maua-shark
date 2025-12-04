import os
import sys
from datetime import datetime

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

# Import config
from config import config

# Initialize Flask app
def create_app():
    app = Flask(__name__)
    app.config.from_object(config['development'])  # Using development config
    return app

app = create_app()
db = SQLAlchemy()
db.init_app(app)

# Define User model
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

def create_or_update_admin(email, password, username='admin', phone='0700000000'):
    with app.app_context():
        try:
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(email=email, username=username, phone=phone)
                print(f"Creating new admin user: {email}")
            else:
                print(f"Updating existing user: {email}")
                
            user.set_password(password)
            user.is_admin = True
            
            db.session.add(user)
            db.session.commit()
            print("\nAdmin user successfully created/updated:")
            print(f"Email: {user.email}")
            print(f"Username: {user.username}")
            print(f"Is Admin: {user.is_admin}")
            print(f"Phone: {user.phone}")
            return True
        except Exception as e:
            print(f"Error creating/updating admin: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create or update an admin user")
    parser.add_argument("email", help="Admin email")
    parser.add_argument("password", help="Admin password")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    parser.add_argument("--phone", default="0700000000", help="Admin phone number (default: 0700000000)")
    
    args = parser.parse_args()
    
    # Initialize the database with the app
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    
    success = create_or_update_admin(
        email=args.email,
        password=args.password,
        username=args.username,
        phone=args.phone
    )
    
    if not success:
        sys.exit(1)
