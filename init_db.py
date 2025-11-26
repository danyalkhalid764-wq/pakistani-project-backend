#!/usr/bin/env python3
"""
Database initialization script
Run this to create the database tables
"""

from database import engine, Base
from models import User, VoiceHistory, Payment, GeneratedVideo, Admin
import os
from dotenv import load_dotenv

load_dotenv()

def init_database():
    """Create all database tables and initialize default admin"""
    print("🔄 Creating database tables...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        
        # Test database connection
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Initialize default admin user if it doesn't exist
        default_admin = db.query(Admin).filter(Admin.name == "Sohaib").first()
        if not default_admin:
            print("📝 Creating default admin user...")
            admin = Admin(name="Sohaib", password="123456")
            db.add(admin)
            db.commit()
            print("✅ Default admin created: Name='Sohaib', Password='123456'")
        else:
            print("ℹ️  Default admin already exists")
        
        # Test query
        user_count = db.query(User).count()
        print(f"📊 Database connected! Current users: {user_count}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Initializing MyAIStudio Database")
    print("=" * 40)
    
    if init_database():
        print("\n✅ Database initialization completed!")
        print("You can now run the server and register users.")
    else:
        print("\n❌ Database initialization failed!")
        print("Please check your database configuration.")





















