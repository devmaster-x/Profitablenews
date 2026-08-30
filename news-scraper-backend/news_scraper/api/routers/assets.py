"""Trending-asset endpoint: the news → trading-pair signal (Track C).

Consumed by the trading system's news collector; the response carries its own
parameters (window, half-life) so every ranking is reproducible.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from news_scraper import timeutil
from news_scraper.api.deps import get_db
from news_scraper.trending import aggregate_trending

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/assets/trending")
async def get_trending_assets(
    hours: int = Query(6, ge=1, le=168, description="Look-back window for articles"),
    half_life_hours: float = Query(2.0, gt=0, le=48, description="Recency half-life for the rank score"),
    min_score: float = Query(0.0, ge=0.0, le=10.0, description="Ignore articles below this profit score"),
    limit: int = Query(20, ge=1, le=100, description="Max assets returned"),
    db=Depends(get_db),
):
    """Assets mentioned in recent news, ranked by recency-weighted score mass."""
    try:
        now = timeutil.utcnow()
        articles = db.get_articles_in_timerange(now - timedelta(hours=hours), now)
        if min_score > 0:
            articles = [a for a in articles if (a.get("profit_score") or 0.0) >= min_score]
        ranked = aggregate_trending(articles, now, half_life_hours)
        return {
            "generated_at": now.isoformat(),
            "window_hours": hours,
            "half_life_hours": half_life_hours,
            "min_score": min_score,
            "articles_considered": len(articles),
            "assets": ranked[:limit],
        }
    except Exception as e:
        logger.error("Failed to compute trending assets: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to compute trending assets: {str(e)}")
