#!/usr/bin/env python3
"""
Migration script to add payment fields to parcels table
Run this script to add the new payment-related fields to the parcels table
"""

from maua import create_app
from maua.extensions import db
from sqlalchemy import text, inspect

def add_parcel_payment_fields():
    """Add payment status fields to parcels table"""
    app = create_app()
    
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing_columns = {col['name'] for col in inspector.get_columns('parcels')}

            # Add payment_status column if it doesn't exist
            if 'payment_status' not in existing_columns:
                db.session.execute(text(
                    "ALTER TABLE parcels ADD COLUMN payment_status VARCHAR(20) DEFAULT 'pending'"
                ))
            
            # Update existing parcels to have 'paid' status (assuming they were already created)
            db.session.execute(text(
                """
                UPDATE parcels 
                SET payment_status = 'paid', status = 'created' 
                WHERE status = 'created' AND (payment_status IS NULL OR payment_status = '')
                """
            ))

            # Add vehicle and driver columns if missing
            if 'vehicle_plate' not in existing_columns:
                db.session.execute(text(
                    "ALTER TABLE parcels ADD COLUMN vehicle_plate VARCHAR(20)"
                ))
            if 'driver_phone' not in existing_columns:
                db.session.execute(text(
                    "ALTER TABLE parcels ADD COLUMN driver_phone VARCHAR(30)"
                ))

            db.session.commit()
            
            print("✅ Successfully added payment fields to parcels table")
            print("📦 Existing parcels have been updated to 'paid' status")
            
        except Exception as e:
            print(f"❌ Error adding payment fields: {e}")
            print("💡 You may need to run this manually in your database")

if __name__ == "__main__":
    print("🚀 Adding Payment Fields to Parcels Table")
    print("=" * 50)
    add_parcel_payment_fields()
