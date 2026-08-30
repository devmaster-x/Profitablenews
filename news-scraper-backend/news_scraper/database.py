from news_scraper.persistent_database import persistent_db as db

__all__ = ["db"]

# Export the persistent database as the main database
# This allows traditional database tools like Navicat, pgAdmin, etc. to access the data
