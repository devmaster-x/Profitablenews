#!/usr/bin/env python3
"""
Switch to Persistent Database
This script switches the application from in-memory to persistent SQLite database
"""

import os
import shutil
from datetime import datetime

def switch_to_persistent_database():
    """Switch the application to use persistent database"""
    
    print("🔄 Switching to Persistent Database...")
    print("=" * 50)
    
    # Backup current database.py
    backup_path = f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    if os.path.exists("app/database.py"):
        shutil.copy("app/database.py", backup_path)
        print(f"✅ Backed up current database to: {backup_path}")
    
    # Create new database.py that uses persistent database
    new_database_content = '''from app.persistent_database import persistent_db as db

# Export the persistent database as the main database
# This allows traditional database tools like Navicat, pgAdmin, etc. to access the data
'''
    
    with open("app/database.py", "w") as f:
        f.write(new_database_content)
    
    print("✅ Switched to persistent database")
    print("📁 Database file: news_scraper.db")
    print("🔧 You can now use database tools like:")
    print("   - Navicat")
    print("   - pgAdmin")
    print("   - SQLite Browser")
    print("   - DBeaver")
    print("   - Any SQLite-compatible tool")
    
    # Create a simple database info script
    info_script = '''#!/usr/bin/env python3
"""
Database Information
Shows information about the persistent database
"""

from app.persistent_database import persistent_db

def show_database_info():
    print("🗄️  PERSISTENT DATABASE INFORMATION")
    print("=" * 40)
    print(f"Database Path: {persistent_db.get_database_path()}")
    print(f"Database File: {persistent_db.db_path}")
    print(f"File Size: {os.path.getsize(persistent_db.db_path) if os.path.exists(persistent_db.db_path) else 'Not created yet'} bytes")
    
    # Get basic stats
    stats = persistent_db.get_stats()
    print(f"Total Articles: {stats['total_articles']}")
    print(f"Categories: {list(stats['categories'].keys())}")
    
    print("\\n🔧 To connect with database tools:")
    print("   - Database Type: SQLite")
    print("   - File Path: news_scraper.db")
    print("   - No username/password required")
    print("   - Main table: articles")

if __name__ == "__main__":
    import os
    show_database_info()
'''
    
    with open("database_info.py", "w") as f:
        f.write(info_script)
    
    print("\n📋 Created database_info.py - run it to see database details")
    print("\n🚀 Next steps:")
    print("   1. Start the backend: python -m app.main")
    print("   2. Run scraper to populate data: curl -X POST http://localhost:8000/scrape")
    print("   3. Open database file with your preferred tool")
    print("   4. Run: python database_info.py (for database details)")

if __name__ == "__main__":
    switch_to_persistent_database() 