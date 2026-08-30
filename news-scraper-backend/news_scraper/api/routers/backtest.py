"""Backtesting endpoints (Phase 3): trigger batches and read accuracy metrics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from news_scraper.api.deps import get_backtester, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/backtest/run")
async def run_backtest(
    hours_ago: int = Query(24, ge=0, le=8760, description="Window END: this many hours before now"),
    window_hours: int = Query(1, ge=1, le=8760, description="Window WIDTH in hours (sweep [end-width, end))"),
    backtester=Depends(get_backtester),
):
    """Manually trigger a backtest batch. Blocks until done (makes rate-limited
    external price API calls — expect ~1.5s per asset)."""
    try:
        result = await backtester.backtest_batch(hours_ago, window_hours=window_hours)
        return {"message": "Backtest completed", "result": result}
    except Exception as e:
        logger.error("Backtest failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/backtest/accuracy")
async def get_backtest_accuracy(
    time_window: str = Query("24h", description="1h, 24h, or 7d"),
    min_samples: int = Query(10, ge=1, description="Minimum samples required"),
    db=Depends(get_db),
):
    """Spearman correlation between predicted scores and actual EXCESS returns."""
    try:
        stats = db.get_backtest_accuracy(time_window, min_samples)
        return {
            "time_window": time_window,
            "correlation": stats.get("correlation"),
            "p_value": stats.get("p_value"),
            "total_samples": stats.get("total_samples"),
            "avg_predicted_score": stats.get("avg_predicted"),
            "avg_excess_movement": stats.get("avg_actual"),
            "score_buckets": stats.get("score_buckets"),
            "error": stats.get("error"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backtest accuracy: {str(e)}")


@router.get("/backtest/keywords")
async def get_keyword_performance(
    limit: int = Query(50, ge=1, le=200, description="Top N keywords"),
    db=Depends(get_db),
):
    """Keywords ranked by average 24h excess movement of backtested articles."""
    try:
        keywords = db.get_keyword_performance(limit)
        return {"keywords": keywords, "count": len(keywords)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get keyword performance: {str(e)}")


@router.get("/backtest/sources")
async def get_source_accuracy(db=Depends(get_db)):
    """Per-source accuracy metrics, to validate the source credibility weights."""
    try:
        sources = db.get_source_accuracy()
        return {"sources": sources, "count": len(sources)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get source accuracy: {str(e)}")
