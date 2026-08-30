"""Article CRUD + list endpoints.

Static paths (``/articles/high-profit``, ``/articles/category/{category}``) are
registered before ``/articles/{article_id}`` so FastAPI's path matching never
treats them as an article id.
"""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from news_scraper.api.deps import get_db
from news_scraper.models import (
    NewsArticle,
    NewsArticleCreate,
    NewsArticleResponse,
    NewsArticleUpdate,
    NewsCategory,
    SentimentScore,
)

router = APIRouter()


@router.post("/articles", response_model=NewsArticle, status_code=201)
async def create_article(article: NewsArticleCreate, db=Depends(get_db)):
    """Create a new news article."""
    try:
        return db.create_article(article)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create article: {str(e)}")


@router.get("/articles/high-profit")
async def get_high_profit_articles(
    min_score: float = Query(7.0, ge=0.0, le=10.0, description="Minimum profit score"),
    limit: int = Query(20, ge=1, le=100, description="Number of opportunities to return"),
    db=Depends(get_db),
):
    """Shortcut for /opportunities scoped under the articles resource."""
    try:
        opportunities = db.get_profit_opportunities(min_score=min_score, limit=limit)
        return {"opportunities": opportunities, "count": len(opportunities), "min_score": min_score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get high-profit articles: {str(e)}")


@router.get("/articles/category/{category}")
async def get_articles_by_category(
    category: NewsCategory,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db=Depends(get_db),
):
    """List articles filtered by category, newest first."""
    try:
        skip = (page - 1) * per_page
        articles, total = db.get_articles(skip=skip, limit=per_page, category=category)
        total_pages = math.ceil(total / per_page) if total > 0 else 1
        return NewsArticleResponse(
            articles=articles,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve articles: {str(e)}")


@router.get("/articles/{article_id}", response_model=NewsArticle)
async def get_article(article_id: int, db=Depends(get_db)):
    """Get a specific news article by ID."""
    article = db.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/articles", response_model=NewsArticleResponse)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[NewsCategory] = Query(None, description="Filter by category"),
    sentiment: Optional[SentimentScore] = Query(None, description="Filter by sentiment"),
    min_profit_score: Optional[float] = Query(None, ge=0.0, le=10.0, description="Minimum profit score"),
    search: Optional[str] = Query(None, description="Search in title, content, source, and keywords"),
    sort_by: str = Query("created_at", description="Sort field (created_at, profit_score, title, source, category)"),
    order: str = Query("desc", description="Sort direction: asc or desc"),
    db=Depends(get_db),
):
    """Get paginated list of news articles with optional filters."""
    skip = (page - 1) * per_page

    try:
        articles, total = db.get_articles(
            skip=skip,
            limit=per_page,
            category=category,
            sentiment=sentiment,
            min_profit_score=min_profit_score,
            search=search,
            sort_by=sort_by,
            order=order,
        )
        total_pages = math.ceil(total / per_page) if total > 0 else 1
        return NewsArticleResponse(
            articles=articles,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve articles: {str(e)}")


@router.put("/articles/{article_id}", response_model=NewsArticle)
async def update_article(article_id: int, article_update: NewsArticleUpdate, db=Depends(get_db)):
    """Update a news article."""
    try:
        updated_article = db.update_article(article_id, article_update)
        if not updated_article:
            raise HTTPException(status_code=404, detail="Article not found")
        return updated_article
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update article: {str(e)}")


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int, db=Depends(get_db)):
    """Delete a news article."""
    try:
        success = db.delete_article(article_id)
        if not success:
            raise HTTPException(status_code=404, detail="Article not found")
        return {"message": "Article deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete article: {str(e)}")
