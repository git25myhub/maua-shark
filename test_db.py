import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ Error: DATABASE_URL is not set in .env file")
        return False

    print(f"Attempting to connect to database...")
    
    try:
        # Create engine and test connection
        engine = create_engine(db_url)
        with engine.connect() as conn:
            print("✅ Successfully connected to the database!")
            # Get PostgreSQL version using text() for proper SQL statement handling
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"PostgreSQL version: {version}")
            return True
    except OperationalError as e:
        print("❌ Failed to connect to the database")
        print(f"Error: {str(e)}")
        return False
    except Exception as e:
        print("❌ An unexpected error occurred")
        print(f"Error: {str(e)}")
        return False

if __name__ == '__main__':
    test_connection()