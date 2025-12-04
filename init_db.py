import os
from maua import create_app, db
from maua.auth.models import User
from maua.catalog.models import Depot, Route, Vehicle
from datetime import datetime, timedelta

def init_db():
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Create admin user
            admin = User(
                username='admin',
                email='admin@mauashark.co.ke',
                phone='+254700000000',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Create sample depots
            nairobi = Depot(
                name='Nairobi Main Terminal',
                town='Nairobi',
                address='Moi Avenue, CBD',
                phone='+254700000001'
            )
            
            mombasa = Depot(
                name='Mombasa Terminal',
                town='Mombasa',
                address='Mombasa CBD',
                phone='+254700000002'
            )
            
            db.session.add_all([nairobi, mombasa])
            db.session.commit()
            
            # Create sample route
            route = Route(
                code='NRB-MSA',
                origin_depot_id=nairobi.id,
                destination_depot_id=mombasa.id,
                distance_km=485,
                estimated_duration=timedelta(hours=8)
            )
            
            # Create sample vehicle
            vehicle = Vehicle(
                plate_no='KDA 123A',
                make='Nissan',
                model='NV350',
                year=2022,
                seat_count=14,
                seat_layout=[
                    {"seat": str(i), "label": f"{i}"} for i in range(1, 15)
                ]
            )
            
            db.session.add_all([route, vehicle])
            db.session.commit()
            
            # Create sample trip
            trip = Trip(
                route_id=route.id,
                vehicle_id=vehicle.id,
                depart_at=datetime.utcnow() + timedelta(days=1),
                arrive_eta=datetime.utcnow() + timedelta(days=1, hours=8),
                base_fare=1200.00
            )
            
            db.session.add(trip)
            db.session.commit()
            
            print("Database initialized successfully!")
            print(f"Admin credentials:")
            print(f"Username: admin")
            print(f"Password: admin123")
        else:
            print("Database already initialized.")

if __name__ == '__main__':
    init_db()
