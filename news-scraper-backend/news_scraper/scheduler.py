"""Daily scraping scheduler (standalone thread-based; one per process).

The scraper instance is injected so a host app can drive the same scraper
instance it wires into the API. ``basicConfig`` is deliberately NOT called at
import time — worker entrypoints own logging configuration.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import schedule
import threading
import time as time_module

from news_scraper import timeutil
from news_scraper.config import settings

logger = logging.getLogger(__name__)


class NewsScrapingScheduler:
    def __init__(self, scraper=None):
        self.scraper = scraper
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        # reschedule() override; None -> settings.default_scraping_time
        self._time_override: Optional[str] = None

    def _scraper(self):
        """Resolve the scraper instance (injected wins, module singleton falls back)."""
        if self.scraper is not None:
            return self.scraper
        from news_scraper.scraper import scraper

        return scraper

    def schedule_daily_scraping(self):
        """Schedule scraping: every N minutes (interval mode) or daily at a time."""
        schedule.clear()  # Clear any existing schedules
        if settings.scrape_interval_minutes > 0:
            schedule.every(settings.scrape_interval_minutes).minutes.do(self._run_scraping_job)
            logger.info(
                "Scheduled news scraping every %s minutes (interval mode)",
                settings.scrape_interval_minutes,
            )
        else:
            scrape_time = self._time_override or settings.default_scraping_time
            schedule.every().day.at(scrape_time).do(self._run_scraping_job)
            logger.info("Scheduled daily news scraping at %s", scrape_time)

        # Phase 3: backtest jobs (24h window daily, 7d window daily)
        if settings.backtest_enabled:
            schedule.every().day.at(settings.backtest_time_24h).do(self._run_backtest_job, hours_ago=24)
            schedule.every().day.at(settings.backtest_time_7d).do(self._run_backtest_job, hours_ago=168)
            logger.info(
                "Scheduled backtesting jobs at %s (24h) and %s (7d)",
                settings.backtest_time_24h,
                settings.backtest_time_7d,
            )

        self._update_next_run_time()

    def _run_backtest_job(self, hours_ago: int):
        """Execute a backtest batch in its own event loop (same pattern as scraping)."""
        logger.info("Starting scheduled backtest job (hours_ago=%s)...", hours_ago)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from news_scraper.backtester import backtester

            result = loop.run_until_complete(backtester.backtest_batch(hours_ago))
            logger.info("Scheduled backtest completed: %s", result)
            self._update_next_run_time()
            return result
        except Exception as e:
            logger.error("Scheduled backtest failed: %s", e)
            self._update_next_run_time()
            raise
        finally:
            loop.close()

    def _update_next_run_time(self):
        """Update the next scheduled run time."""
        jobs = schedule.get_jobs()
        if jobs:
            self.next_run = jobs[0].next_run
            logger.info("Next scheduled scraping: %s", self.next_run)

    def _run_scraping_job(self):
        """Execute the scraping job with error handling and logging."""
        logger.info("Starting scheduled news scraping job...")
        self.total_runs += 1

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._scraper().scrape_and_store(trigger="scheduled"))

            self.last_run = timeutil.utcnow()
            self.successful_runs += 1

            logger.info("Scheduled scraping completed successfully: %s", result)
            logger.info("Scraped %s articles, stored %s", result["scraped_count"], result["stored_count"])

            self._update_next_run_time()
            return result
        except Exception as e:
            self.failed_runs += 1
            logger.error("Scheduled scraping failed: %s", e)
            self._update_next_run_time()
            raise
        finally:
            loop.close()

    def start_scheduler(self):
        """Start the scheduler in a background thread."""
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
                    logger.error("Scheduler error: %s", e)
                    time_module.sleep(settings.scheduler_check_interval)  # Continue running even on error
            logger.info("News scraping scheduler stopped")

        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()

        logger.info("Scheduler thread started successfully")

    def stop_scheduler(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        self.is_running = False
        schedule.clear()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)

        logger.info("News scraping scheduler stopped")

    def get_status(self) -> dict:
        """Get the current status of the scheduler."""
        return {
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": (self.successful_runs / self.total_runs * 100) if self.total_runs > 0 else 0,
            "scheduled_time": (
                f"every {settings.scrape_interval_minutes} minutes"
                if settings.scrape_interval_minutes > 0
                else f"{self._time_override or settings.default_scraping_time} daily (server local time)"
            ),
        }

    def run_now(self):
        """Manually trigger a scraping job immediately."""
        logger.info("Manually triggering scraping job...")
        return self._run_scraping_job()

    def reschedule(self, time_str: str = "00:00"):
        """Reschedule the daily scraping to a different time.

        Delegates to schedule_daily_scraping so the backtest jobs are re-added
        too (the historical implementation cleared them and never restored them).
        No-op semantics in interval mode: the interval wins over the daily time.
        """
        try:
            datetime.strptime(time_str, "%H:%M")
            self._time_override = time_str
            self.schedule_daily_scraping()
            logger.info("Rescheduled daily scraping to %s", time_str)
            return True
        except ValueError as e:
            logger.error("Invalid time format '%s': %s", time_str, e)
            return False
