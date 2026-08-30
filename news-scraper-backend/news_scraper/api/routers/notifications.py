"""Slack notification endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from news_scraper.api.deps import get_db
from news_scraper.slack_notifier import get_slack_notifier

router = APIRouter()


class NotificationResponse(BaseModel):
    """Response model for notification operations."""
    success: bool
    message: str
    sent_count: int
    article_ids: Optional[List[int]] = None


class NotificationStatusResponse(BaseModel):
    """Response model for checking notification status."""
    total_unsent: int
    min_score: float
    articles: List[dict]


@router.post("/notifications/send", response_model=NotificationResponse)
async def send_slack_notifications(
    min_score: float = Query(5.0, ge=0.0, le=10.0, description="Minimum profit score"),
    limit: int = Query(10, ge=1, le=50, description="Maximum articles per notification"),
    db=Depends(get_db),
):
    """Send high-profit articles to Slack that haven't been sent yet.
    
    This endpoint:
    1. Fetches articles with profit_score >= min_score that haven't been sent
    2. Limits to 'limit' articles (default 10, max 50 due to Slack constraints)
    3. Sends them to the configured Slack webhook
    4. Marks them as sent to prevent duplicates
    
    Note: Slack has a 50-block limit per message. Each article uses ~3 blocks.
    The limit parameter ensures we don't exceed Slack's constraints.
    """
    try:
        # Get unsent high-profit articles
        articles = db.get_unsent_high_profit_articles(min_score=min_score)
        
        if not articles:
            return NotificationResponse(
                success=True,
                message="No new high-profit articles to send",
                sent_count=0,
                article_ids=[]
            )

        # Limit articles to prevent Slack API errors
        if len(articles) > limit:
            articles = articles[:limit]

        # Send to Slack
        notifier = get_slack_notifier()
        result = notifier.send_notification(articles)

        if result["success"]:
            # Mark articles as sent
            article_ids = [article["id"] for article in articles]
            db.mark_articles_as_notified(article_ids)
            
            return NotificationResponse(
                success=True,
                message=result["message"],
                sent_count=result["sent_count"],
                article_ids=article_ids
            )
        else:
            return NotificationResponse(
                success=False,
                message=result["message"],
                sent_count=0,
                article_ids=[]
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send notifications: {str(e)}"
        )


@router.get("/notifications/status", response_model=NotificationStatusResponse)
async def get_notification_status(
    min_score: float = Query(5.0, ge=0.0, le=10.0, description="Minimum profit score"),
    db=Depends(get_db),
):
    """Check how many high-profit articles are pending notification.
    
    This endpoint shows articles that meet the score threshold but haven't
    been sent to Slack yet.
    """
    try:
        articles = db.get_unsent_high_profit_articles(min_score=min_score)
        
        return NotificationStatusResponse(
            total_unsent=len(articles),
            min_score=min_score,
            articles=articles
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get notification status: {str(e)}"
        )


@router.post("/notifications/test")
async def test_slack_notification(db=Depends(get_db)):
    """Send a test notification to Slack with sample data.
    
    This endpoint sends a test message to verify the Slack webhook is configured
    correctly. It doesn't mark any articles as sent.
    """
    try:
        notifier = get_slack_notifier()
        
        # Create a sample article for testing
        test_articles = [
            {
                "id": 0,
                "title": "Test Notification from News Scraper",
                "url": "https://example.com/test",
                "profit_score": 8.5,
                "source": "Test Source",
                "category": "general",
                "sentiment": "positive"
            }
        ]
        
        result = notifier.send_notification(test_articles)
        
        return {
            "success": result["success"],
            "message": result["message"],
            "is_test": True
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test notification: {str(e)}"
        )


@router.post("/notifications/reset")
async def reset_notification_status(
    article_ids: List[int],
    db=Depends(get_db),
):
    """Reset notification status for specific articles to allow re-sending.
    
    This is useful if you want to re-send certain articles to Slack.
    """
    try:
        if not article_ids:
            raise HTTPException(
                status_code=400,
                detail="No article IDs provided"
            )
        
        success = db.reset_notification_status(article_ids)
        
        if success:
            return {
                "success": True,
                "message": f"Reset notification status for {len(article_ids)} article(s)",
                "article_ids": article_ids
            }
        else:
            return {
                "success": False,
                "message": "No articles were updated",
                "article_ids": []
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset notification status: {str(e)}"
        )
