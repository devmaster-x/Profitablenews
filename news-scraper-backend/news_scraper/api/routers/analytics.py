"""Analytics endpoints: stats, categories, opportunities, trends, alerts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from news_scraper.api.deps import get_db
from news_scraper.models import NewsCategory, SentimentScore

router = APIRouter()


@router.get("/stats")
async def get_stats(db=Depends(get_db)):
    """Get database statistics."""
    try:
        return db.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")


@router.get("/categories")
async def get_categories():
    """Get available news categories."""
    return {"categories": [category.value for category in NewsCategory]}


@router.get("/sentiments")
async def get_sentiments():
    """Get available sentiment scores."""
    return {"sentiments": [sentiment.value for sentiment in SentimentScore]}


@router.get("/opportunities")
async def get_profit_opportunities(
    min_score: float = Query(7.0, ge=0.0, le=10.0, description="Minimum profit score"),
    limit: int = Query(20, ge=1, le=100, description="Number of opportunities to return"),
    db=Depends(get_db),
):
    """Get high-profit potential opportunities."""
    try:
        opportunities = db.get_profit_opportunities(min_score=min_score, limit=limit)
        return {"opportunities": opportunities, "count": len(opportunities), "min_score": min_score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get opportunities: {str(e)}")


@router.get("/trends")
async def get_market_trends(db=Depends(get_db)):
    """Get market trends analysis."""
    try:
        trends = db.get_market_trends()
        return {"trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trends: {str(e)}")


@router.get("/alerts")
async def get_profit_alerts(
    threshold: float = Query(8.0, ge=0.0, le=10.0, description="Profit score threshold for alerts"),
    db=Depends(get_db),
):
    """Get high-priority profit alerts."""
    try:
        alerts = db.get_profit_alerts(threshold=threshold)
        return {"alerts": alerts, "count": len(alerts), "threshold": threshold}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.get("/companies")
async def get_company_mentions(db=Depends(get_db)):
    """Get companies mentioned in recent articles."""
    try:
        companies = db.get_company_mentions()
        return {"companies": companies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get companies: {str(e)}")


@router.get("/categories/{category}/trends")
async def get_category_trends(category: NewsCategory, db=Depends(get_db)):
    """Get trends for a specific category."""
    try:
        trends = db.get_category_trends(category)
        return {"category": category, "trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get category trends: {str(e)}")
