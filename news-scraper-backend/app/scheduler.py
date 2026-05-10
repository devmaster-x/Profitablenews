import asyncio
import logging
from datetime import datetime, time
from typing import Optional
import schedule
import threading
import time as time_module

from app.scraper import scraper
from app.database import db
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsScrapingScheduler:
    def __init__(self):
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        
    def schedule_daily_scraping(self):
        """Schedule the scraper to run daily at 0 AM (midnight)"""
        schedule.clear()  # Clear any existing schedules
        schedule.every().day.at(settings.default_scraping_time).do(self._run_scraping_job)
        logger.info(f"Scheduled daily news scraping at {settings.default_scraping_time}")
        
        self._update_next_run_time()
    
    def _update_next_run_time(self):
        """Update the next scheduled run time"""
        jobs = schedule.get_jobs()
        if jobs:
            self.next_run = jobs[0].next_run
            logger.info(f"Next scheduled scraping: {self.next_run}")
    
    def _run_scraping_job(self):
        """Execute the scraping job with error handling and logging"""
        logger.info("Starting scheduled news scraping job...")
        self.total_runs += 1
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(scraper.scrape_and_store())
            
            self.last_run = datetime.utcnow()
            self.successful_runs += 1
            
            logger.info(f"Scheduled scraping completed successfully: {result}")
            logger.info(f"Scraped {result['scraped_count']} articles, stored {result['stored_count']}")
            
            self._update_next_run_time()
            
            return result
            
        except Exception as e:
            self.failed_runs += 1
            logger.error(f"Scheduled scraping failed: {e}")
            
            self._update_next_run_time()
            
            raise
        finally:
            loop.close()
    
    def start_scheduler(self):
        """Start the scheduler in a background thread"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.schedule_daily_scraping()
        
        def run_scheduler():
            logger.info("News scraping scheduler started")
            while self.is_running:
                try:
                    schedule.run_pending()
                    time_module.sleep(settings.scheduler_check_interval)  # Check every minute
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    time_module.sleep(settings.scheduler_check_interval)  # Continue running even on error
            
            logger.info("News scraping scheduler stopped")
        
        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Scheduler thread started successfully")
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        logger.info("News scraping scheduler stopped")
    
    def get_status(self) -> dict:
        """Get the current status of the scheduler"""
        return {
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": (self.successful_runs / self.total_runs * 100) if self.total_runs > 0 else 0,
            "scheduled_time": "00:00 UTC daily"
        }
    
    def run_now(self):
        """Manually trigger a scraping job immediately"""
        logger.info("Manually triggering scraping job...")
        return self._run_scraping_job()
    
    def reschedule(self, time_str: str = "00:00"):
        """Reschedule the daily scraping to a different time"""
        try:
            datetime.strptime(time_str, "%H:%M")
            
            schedule.clear()
            schedule.every().day.at(time_str).do(self._run_scraping_job)
            
            self._update_next_run_time()
            
            logger.info(f"Rescheduled daily scraping to {time_str}")
            return True
            
        except ValueError as e:
            logger.error(f"Invalid time format '{time_str}': {e}")
            return False

news_scheduler = NewsScrapingScheduler()
