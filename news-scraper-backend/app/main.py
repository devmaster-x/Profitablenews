from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import math
import logging

logger = logging.getLogger(__name__)

from app.models import (
    NewsArticle, NewsArticleCreate, NewsArticleUpdate, NewsArticleResponse,
    NewsCategory, SentimentScore, ErrorResponse
)
from app.database import db
from app.config import settings

app = FastAPI(
    title="News Scraper API",
    description="API for managing scraped news articles with profit analysis",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "message": "News Scraper API is running"}

@app.post("/articles", response_model=NewsArticle, status_code=201)
async def create_article(article: NewsArticleCreate):
    """Create a new news article"""
    try:
        return db.create_article(article)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create article: {str(e)}")

@app.get("/articles/{article_id}", response_model=NewsArticle)
async def get_article(article_id: int):
    """Get a specific news article by ID"""
    article = db.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@app.get("/articles", response_model=NewsArticleResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[NewsCategory] = Query(None, description="Filter by category"),
    sentiment: Optional[SentimentScore] = Query(None, description="Filter by sentiment"),
    min_profit_score: Optional[float] = Query(None, ge=0.0, le=10.0, description="Minimum profit score"),
    search: Optional[str] = Query(None, description="Search in title, content, source, and keywords")
):
    """Get paginated list of news articles with optional filters"""
    skip = (page - 1) * per_page
    
    try:
        articles, total = db.get_articles(
            skip=skip,
            limit=per_page,
            category=category,
            sentiment=sentiment,
            min_profit_score=min_profit_score,
            search=search
        )
        
        total_pages = math.ceil(total / per_page) if total > 0 else 1
        
        return NewsArticleResponse(
            articles=articles,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve articles: {str(e)}")

@app.put("/articles/{article_id}", response_model=NewsArticle)
async def update_article(article_id: int, article_update: NewsArticleUpdate):
    """Update a news article"""
    try:
        updated_article = db.update_article(article_id, article_update)
        if not updated_article:
            raise HTTPException(status_code=404, detail="Article not found")
        return updated_article
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update article: {str(e)}")

@app.delete("/articles/{article_id}")
async def delete_article(article_id: int):
    """Delete a news article"""
    try:
        success = db.delete_article(article_id)
        if not success:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"message": "Article deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete article: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get database statistics"""
    try:
        return db.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")

@app.get("/categories")
async def get_categories():
    """Get available news categories"""
    return {"categories": [category.value for category in NewsCategory]}

@app.get("/sentiments")
async def get_sentiments():
    """Get available sentiment scores"""
    return {"sentiments": [sentiment.value for sentiment in SentimentScore]}

@app.post("/scrape")
async def trigger_scraping():
    """Manually trigger news scraping from all sources"""
    try:
        from app.scraper import scraper
        result = await scraper.scrape_and_store()
        return {
            "message": "Scraping completed successfully",
            "result": result
        }
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/scrape/status")
async def get_scraping_status():
    """Get the current status of the scraping system"""
    try:
        from app.scraper import scraper
        return {
            "sources_configured": list(scraper.news_sources.keys()),
            "total_sources": len(scraper.news_sources),
            "last_scrape": "Not implemented yet",  # TODO: Add timestamp tracking
            "status": "ready"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scraping status: {str(e)}")

@app.post("/scheduler/start")
async def start_scheduler():
    """Start the daily news scraping scheduler"""
    try:
        from app.scheduler import news_scheduler
        news_scheduler.start_scheduler()
        return {
            "message": "Scheduler started successfully",
            "status": news_scheduler.get_status()
        }
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {str(e)}")

@app.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the daily news scraping scheduler"""
    try:
        from app.scheduler import news_scheduler
        news_scheduler.stop_scheduler()
        return {
            "message": "Scheduler stopped successfully",
            "status": news_scheduler.get_status()
        }
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {str(e)}")

@app.get("/scheduler/status")
async def get_scheduler_status():
    """Get the current status of the scheduler"""
    try:
        from app.scheduler import news_scheduler
        return news_scheduler.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")

@app.post("/scheduler/run-now")
async def run_scheduler_now():
    """Manually trigger the scraping job immediately"""
    try:
        from app.scheduler import news_scheduler
        result = news_scheduler.run_now()
        return {
            "message": "Manual scraping completed successfully",
            "result": result,
            "status": news_scheduler.get_status()
        }
    except Exception as e:
        logger.error(f"Manual scraping failed: {e}")
        raise HTTPException(status_code=500, detail=f"Manual scraping failed: {str(e)}")

@app.post("/scheduler/reschedule")
async def reschedule_scraping(time_str: str = "00:00"):
    """Reschedule the daily scraping to a different time (HH:MM format)"""
    try:
        from app.scheduler import news_scheduler
        success = news_scheduler.reschedule(time_str)
        if success:
            return {
                "message": f"Rescheduled daily scraping to {time_str}",
                "status": news_scheduler.get_status()
            }
        else:
            raise HTTPException(status_code=400, detail=f"Invalid time format: {time_str}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reschedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reschedule: {str(e)}")

# New enhanced profit analysis endpoints
@app.get("/opportunities")
async def get_profit_opportunities(
    min_score: float = Query(7.0, ge=0.0, le=10.0, description="Minimum profit score"),
    limit: int = Query(20, ge=1, le=100, description="Number of opportunities to return")
):
    """Get high-profit potential opportunities"""
    try:
        opportunities = db.get_profit_opportunities(min_score=min_score, limit=limit)
        return {
            "opportunities": opportunities,
            "count": len(opportunities),
            "min_score": min_score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get opportunities: {str(e)}")

@app.get("/trends")
async def get_market_trends():
    """Get market trends analysis"""
    try:
        trends = db.get_market_trends()
        return {"trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trends: {str(e)}")

@app.get("/alerts")
async def get_profit_alerts(
    threshold: float = Query(8.0, ge=0.0, le=10.0, description="Profit score threshold for alerts")
):
    """Get high-priority profit alerts"""
    try:
        alerts = db.get_profit_alerts(threshold=threshold)
        return {
            "alerts": alerts,
            "count": len(alerts),
            "threshold": threshold
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")

@app.get("/companies")
async def get_company_mentions():
    """Get companies mentioned in recent articles"""
    try:
        companies = db.get_company_mentions()
        return {"companies": companies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get companies: {str(e)}")

@app.get("/categories/{category}/trends")
async def get_category_trends(category: NewsCategory):
    """Get trends for a specific category"""
    try:
        trends = db.get_category_trends(category)
        return {"category": category, "trends": trends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get category trends: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level=settings.log_level.lower()
    )