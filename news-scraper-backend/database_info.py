#!/usr/bin/env python3
"""
Database Information
Shows information about the persistent database
"""

import os
from app.persistent_database import persistent_db

def show_database_info():
    print("PERSISTENT DATABASE INFORMATION")
    print("=" * 40)
    print(f"Database Path: {persistent_db.get_database_path()}")
    print(f"Database File: {persistent_db.db_path}")
    print(f"File Size: {os.path.getsize(persistent_db.db_path) if os.path.exists(persistent_db.db_path) else 'Not created yet'} bytes")
    
    # Get basic stats
    stats = persistent_db.get_stats()
    print(f"Total Articles: {stats['total_articles']}")
    print(f"Categories: {list(stats['categories'].keys())}")
    
    print("\nTo connect with database tools:")
    print("   - Database Type: SQLite")
    print("   - File Path: news_scraper.db")
    print("   - No username/password required")
    print("   - Main table: articles")

if __name__ == "__main__":
    show_database_info()
