"""
Script to add the 'requested' column to the users table
"""
import sys
import os

# Add the current directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError

def add_requested_column():
    """Add the requested column to users table if it doesn't exist"""
    print("=" * 80)
    print("Adding 'requested' column to users table...")
    print("=" * 80)
    
    # Check if column already exists
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'requested' in columns:
        print("✅ Column 'requested' already exists in users table")
        print(f"   Existing columns: {columns}")
        return True
    
    print(f"   Current columns: {columns}")
    print("   Column 'requested' not found. Adding it...")
    
    # Add the column using raw SQL
    try:
        with engine.connect() as conn:
            # Use a transaction
            trans = conn.begin()
            try:
                # SQLite syntax
                if 'sqlite' in str(engine.url):
                    conn.execute(text("ALTER TABLE users ADD COLUMN requested BOOLEAN DEFAULT 0"))
                    print("   Using SQLite syntax")
                else:
                    # PostgreSQL syntax
                    conn.execute(text("ALTER TABLE users ADD COLUMN requested BOOLEAN DEFAULT FALSE"))
                    print("   Using PostgreSQL syntax")
                
                trans.commit()
                print("✅ Column 'requested' added successfully!")
                
                # Verify it was added
                inspector = inspect(engine)
                columns_after = [col['name'] for col in inspector.get_columns('users')]
                print(f"   Updated columns: {columns_after}")
                
                return True
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except OperationalError as e:
        error_msg = str(e).lower()
        if "duplicate column name" in error_msg or "already exists" in error_msg:
            print("✅ Column 'requested' already exists (detected via error message)")
            return True
        else:
            print(f"❌ Error adding column: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = add_requested_column()
    print("=" * 80)
    if success:
        print("✅ Script completed successfully!")
        print("   You can now restart your backend server.")
    else:
        print("❌ Script failed. Please check the error messages above.")
    print("=" * 80)
    sys.exit(0 if success else 1)



