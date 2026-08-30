"""Scrape-trigger and scrape-status endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from news_scraper.api.deps import get_db, get_scraper

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/scrape")
async def trigger_scraping(scraper=Depends(get_scraper)):
    """Manually trigger news scraping from all sources."""
    try:
        result = await scraper.scrape_and_store(trigger="manual")
        return {"message": "Scraping completed successfully", "result": result}
    except Exception as e:
        logger.error("Scraping failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.get("/scrape/status")
async def get_scraping_status(
    runs: int = Query(10, ge=1, le=100, description="Recent scrape runs to include"),
    scraper=Depends(get_scraper),
    db=Depends(get_db),
):
    """Scraping system status, backed by the scrape_runs audit table."""
    try:
        recent = db.get_scrape_runs(limit=runs)
        return {
            "sources_configured": list(scraper.news_sources.keys()),
            "total_sources": len(scraper.news_sources),
            "last_scrape": recent[0] if recent else None,
            "recent_runs": recent,
            "status": "ready",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scraping status: {str(e)}")
