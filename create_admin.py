"""
Script to create admin and staff users for Maua Sacco
Uses the same User model and bcrypt hashing as the main app
"""
from dotenv import load_dotenv
load_dotenv()

from maua import create_app, db, bcrypt
from maua.auth.models import User
from datetime import datetime

def create_user(email, password, username, phone, role='staff'):
    """
    Create or update a user account
    
    Args:
        email: User email (unique)
        password: Password (will be hashed)
        username: Username (unique)
        phone: Phone number
        role: 'admin', 'staff', or 'customer'
    """
    app = create_app()
    
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        
        if existing_user:
            print(f"User with email {email} already exists.")
            print("Updating password and role...")
            existing_user.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
            existing_user.is_admin = (role == 'admin')
            existing_user.is_staff = (role in ['admin', 'staff'])
            db.session.commit()
            print(f"✓ User updated successfully!")
            print(f"  Email: {existing_user.email}")
            print(f"  Username: {existing_user.username}")
            print(f"  Role: {role}")
        else:
            # Create new user
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(
                username=username,
                email=email,
                phone=phone,
                password_hash=hashed_password,
                is_admin=(role == 'admin'),
                is_staff=(role in ['admin', 'staff']),
                is_active=True,
                date_joined=datetime.utcnow()
            )
            db.session.add(user)
            db.session.commit()
            print(f"✓ User created successfully!")
            print(f"  Email: {user.email}")
            print(f"  Username: {user.username}")
            print(f"  Phone: {user.phone}")
            print(f"  Role: {role}")

def create_admin_user(email, password, username, phone):
    """Create an admin user"""
    create_user(email, password, username, phone, role='admin')

def create_staff_user(email, password, username, phone):
    """Create a staff user"""
    create_user(email, password, username, phone, role='staff')

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Maua Sacco User Management")
    print("=" * 60)
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'admin':
            # Create default admin
            create_admin_user(
                email="admin@mauasacco.com",
                password="admin123",
                username="admin",
                phone="0700000000"
            )
            print("\n" + "=" * 60)
            print("Admin Login Credentials:")
            print("  Email: admin@mauasacco.com")
            print("  Password: admin123")
            print("=" * 60)
            
        elif command == 'staff':
            # Create sample staff user
            create_staff_user(
                email="staff@mauasacco.com",
                password="staff123",
                username="staff1",
                phone="0711111111"
            )
            print("\n" + "=" * 60)
            print("Staff Login Credentials:")
            print("  Email: staff@mauasacco.com")
            print("  Password: staff123")
            print("=" * 60)
            
        elif command == 'both':
            # Create both admin and staff
            create_admin_user(
                email="admin@mauasacco.com",
                password="admin123",
                username="admin",
                phone="0700000000"
            )
            print()
            create_staff_user(
                email="staff@mauasacco.com",
                password="staff123",
                username="staff1",
                phone="0711111111"
            )
            print("\n" + "=" * 60)
            print("Login Credentials:")
            print("-" * 30)
            print("Admin:")
            print("  Email: admin@mauasacco.com")
            print("  Password: admin123")
            print("-" * 30)
            print("Staff:")
            print("  Email: staff@mauasacco.com")
            print("  Password: staff123")
            print("=" * 60)
            
        else:
            print("Usage: python create_admin.py [admin|staff|both]")
            print()
            print("Commands:")
            print("  admin  - Create admin user")
            print("  staff  - Create staff user")
            print("  both   - Create both admin and staff users")
    else:
        # Default: create admin user
        create_admin_user(
            email="admin@mauasacco.com",
            password="admin123",
            username="admin",
            phone="0700000000"
        )
        print("\n" + "=" * 60)
        print("Admin Login Credentials:")
        print("  Email: admin@mauasacco.com")
        print("  Password: admin123")
        print("=" * 60)
        print()
        print("To create a staff user, run: python create_admin.py staff")
        print("To create both, run: python create_admin.py both")
