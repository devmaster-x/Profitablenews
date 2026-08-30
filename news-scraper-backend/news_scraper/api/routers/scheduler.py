"""Scheduler control endpoints (daily scrape + backtest jobs)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from news_scraper.api.deps import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scheduler/start")
async def start_scheduler(scheduler=Depends(get_scheduler)):
    """Start the daily news scraping scheduler."""
    try:
        scheduler.start_scheduler()
        return {"message": "Scheduler started successfully", "status": scheduler.get_status()}
    except Exception as e:
        logger.error("Failed to start scheduler: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")


@router.post("/scheduler/stop")
async def stop_scheduler(scheduler=Depends(get_scheduler)):
    """Stop the daily news scraping scheduler."""
    try:
        scheduler.stop_scheduler()
        return {"message": "Scheduler stopped successfully", "status": scheduler.get_status()}
    except Exception as e:
        logger.error("Failed to stop scheduler: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")


@router.get("/scheduler/status")
async def get_scheduler_status(scheduler=Depends(get_scheduler)):
    """Get the current status of the scheduler."""
    try:
        return scheduler.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")


@router.post("/scheduler/run-now")
async def run_scheduler_now(scheduler=Depends(get_scheduler)):
    """Manually trigger the scraping job immediately."""
    try:
        result = scheduler.run_now()
        return {"message": "Manual scraping completed successfully", "result": result, "status": scheduler.get_status()}
    except Exception as e:
        logger.error("Manual scraping failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Manual scraping failed: {str(e)}")


@router.post("/scheduler/reschedule")
async def reschedule_scraping(time_str: str = "00:00", scheduler=Depends(get_scheduler)):
    """Reschedule the daily scraping to a different time (HH:MM format)."""
    try:
        success = scheduler.reschedule(time_str)
        if success:
            return {"message": f"Rescheduled daily scraping to {time_str}", "status": scheduler.get_status()}
        raise HTTPException(status_code=400, detail=f"Invalid time format: {time_str}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reschedule: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to reschedule: {str(e)}")
