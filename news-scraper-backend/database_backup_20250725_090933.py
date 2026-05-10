from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.models import NewsArticle, NewsArticleCreate, NewsArticleUpdate, NewsCategory, SentimentScore
import threading

class InMemoryDatabase:
    def __init__(self):
        self._articles: Dict[int, NewsArticle] = {}
        self._next_id = 1
        self._lock = threading.Lock()
    
    def create_article(self, article_data: NewsArticleCreate) -> NewsArticle:
        with self._lock:
            now = datetime.utcnow()
            article = NewsArticle(
                id=self._next_id,
                created_at=now,
                updated_at=now,
                **article_data.model_dump()
            )
            self._articles[self._next_id] = article
            self._next_id += 1
            return article
    
    def get_article(self, article_id: int) -> Optional[NewsArticle]:
        return self._articles.get(article_id)
    
    def get_articles(
        self, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[NewsCategory] = None,
        sentiment: Optional[SentimentScore] = None,
        min_profit_score: Optional[float] = None,
        search: Optional[str] = None
    ) -> tuple[List[NewsArticle], int]:
        articles = list(self._articles.values())
        
        if category:
            articles = [a for a in articles if a.category == category]
        
        if sentiment:
            articles = [a for a in articles if a.sentiment == sentiment]
        
        if min_profit_score is not None:
            articles = [a for a in articles if a.profit_score is not None and a.profit_score >= min_profit_score]
        
        if search:
            search_lower = search.lower()
            articles = [
                a for a in articles 
                if search_lower in a.title.lower() 
                or search_lower in a.content.lower()
                or search_lower in a.source.lower()
                or any(search_lower in keyword.lower() for keyword in (a.keywords or []))
            ]
        
        articles.sort(key=lambda x: x.created_at, reverse=True)
        
        total = len(articles)
        articles = articles[skip:skip + limit]
        
        return articles, total
    
    def update_article(self, article_id: int, article_data: NewsArticleUpdate) -> Optional[NewsArticle]:
        with self._lock:
            if article_id not in self._articles:
                return None
            
            article = self._articles[article_id]
            update_data = article_data.model_dump(exclude_unset=True)
            
            for field, value in update_data.items():
                setattr(article, field, value)
            
            article.updated_at = datetime.utcnow()
            return article
    
    def delete_article(self, article_id: int) -> bool:
        with self._lock:
            if article_id in self._articles:
                del self._articles[article_id]
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        articles = list(self._articles.values())
        total = len(articles)
        
        if total == 0:
            return {
                "total_articles": 0,
                "categories": {},
                "sentiments": {},
                "avg_profit_score": None,
                "latest_article": None,
                "high_profit_opportunities": 0,
                "market_trends": []
            }
        
        categories = {}
        for article in articles:
            categories[article.category.value] = categories.get(article.category.value, 0) + 1
        
        sentiments = {}
        for article in articles:
            if article.sentiment:
                sentiments[article.sentiment.value] = sentiments.get(article.sentiment.value, 0) + 1
        
        profit_scores = [a.profit_score for a in articles if a.profit_score is not None]
        avg_profit_score = sum(profit_scores) / len(profit_scores) if profit_scores else None
        
        latest_article = max(articles, key=lambda x: x.created_at) if articles else None
        
        # Calculate high-profit opportunities (score >= 7.0)
        high_profit_count = len([a for a in articles if a.profit_score and a.profit_score >= 7.0])
        
        # Calculate market trends
        market_trends = self._calculate_market_trends(articles)
        
        return {
            "total_articles": total,
            "categories": categories,
            "sentiments": sentiments,
            "avg_profit_score": avg_profit_score,
            "latest_article": latest_article.created_at if latest_article else None,
            "high_profit_opportunities": high_profit_count,
            "market_trends": market_trends
        }
    
    def get_profit_opportunities(self, min_score: float = 7.0, limit: int = 20) -> List[Dict[str, Any]]:
        """Get high-profit potential opportunities"""
        articles = list(self._articles.values())
        opportunities = [
            {
                "id": article.id,
                "title": article.title,
                "profit_score": article.profit_score,
                "category": article.category,
                "sentiment": article.sentiment,
                "created_at": article.created_at,
                "source": article.source,
                "url": article.url
            }
            for article in articles
            if article.profit_score and article.profit_score >= min_score
        ]
        
        # Sort by profit score descending
        opportunities.sort(key=lambda x: x["profit_score"], reverse=True)
        return opportunities[:limit]
    
    def get_market_trends(self) -> List[Dict[str, Any]]:
        """Get market trends analysis"""
        articles = list(self._articles.values())
        if not articles:
            return []
        
        # Group by category and analyze trends
        trends = []
        for category in set(article.category for article in articles):
            category_articles = [a for a in articles if a.category == category]
            if len(category_articles) < 3:  # Need at least 3 articles for trend analysis
                continue
            
            # Calculate average profit score for category
            avg_score = sum(a.profit_score or 0 for a in category_articles) / len(category_articles)
            
            # Determine trend direction
            recent_articles = sorted(category_articles, key=lambda x: x.created_at, reverse=True)[:5]
            recent_avg = sum(a.profit_score or 0 for a in recent_articles) / len(recent_articles)
            
            if recent_avg > avg_score + 1:
                trend_direction = "up"
            elif recent_avg < avg_score - 1:
                trend_direction = "down"
            else:
                trend_direction = "stable"
            
            trends.append({
                "category": category,
                "trend_direction": trend_direction,
                "confidence_score": min(abs(recent_avg - avg_score) / 2, 1.0),
                "avg_profit_score": avg_score,
                "recent_avg_score": recent_avg,
                "article_count": len(category_articles)
            })
        
        return trends
    
    def get_profit_alerts(self, threshold: float = 8.0) -> List[Dict[str, Any]]:
        """Get high-priority profit alerts"""
        articles = list(self._articles.values())
        alerts = []
        
        for article in articles:
            if article.profit_score and article.profit_score >= threshold:
                alerts.append({
                    "id": article.id,
                    "title": article.title,
                    "profit_score": article.profit_score,
                    "category": article.category,
                    "sentiment": article.sentiment,
                    "created_at": article.created_at,
                    "source": article.source,
                    "urgency": "high" if article.profit_score >= 9.0 else "medium"
                })
        
        # Sort by profit score descending
        alerts.sort(key=lambda x: x["profit_score"], reverse=True)
        return alerts
    
    def get_company_mentions(self) -> List[Dict[str, Any]]:
        """Get companies mentioned in recent articles"""
        articles = list(self._articles.values())
        company_mentions = {}
        
        major_companies = [
            'apple', 'google', 'microsoft', 'amazon', 'tesla', 'meta', 'facebook',
            'netflix', 'nvidia', 'amd', 'intel', 'oracle', 'salesforce', 'adobe',
            'paypal', 'square', 'stripe', 'airbnb', 'uber', 'lyft', 'zoom',
            'slack', 'dropbox', 'spotify', 'twitter', 'linkedin', 'snapchat',
            'openai', 'anthropic', 'palantir', 'databricks', 'coinbase', 'binance'
        ]
        
        for article in articles:
            text = f"{article.title} {article.content}".lower()
            for company in major_companies:
                if company in text:
                    if company not in company_mentions:
                        company_mentions[company] = {
                            "name": company.title(),
                            "mention_count": 0,
                            "avg_profit_score": 0,
                            "articles": []
                        }
                    
                    company_mentions[company]["mention_count"] += 1
                    company_mentions[company]["articles"].append({
                        "id": article.id,
                        "title": article.title,
                        "profit_score": article.profit_score,
                        "created_at": article.created_at
                    })
        
        # Calculate average profit scores
        for company_data in company_mentions.values():
            if company_data["articles"]:
                scores = [a["profit_score"] for a in company_data["articles"] if a["profit_score"]]
                if scores:
                    company_data["avg_profit_score"] = sum(scores) / len(scores)
        
        # Sort by mention count descending
        return sorted(company_mentions.values(), key=lambda x: x["mention_count"], reverse=True)
    
    def get_category_trends(self, category: NewsCategory) -> Dict[str, Any]:
        """Get trends for a specific category"""
        articles = [a for a in self._articles.values() if a.category == category]
        if not articles:
            return {"category": category, "trends": [], "message": "No articles found for this category"}
        
        # Sort by date
        articles.sort(key=lambda x: x.created_at)
        
        # Calculate daily profit scores
        daily_scores = {}
        for article in articles:
            date_str = article.created_at.strftime("%Y-%m-%d")
            if date_str not in daily_scores:
                daily_scores[date_str] = []
            if article.profit_score:
                daily_scores[date_str].append(article.profit_score)
        
        # Calculate daily averages
        trend_data = []
        for date, scores in daily_scores.items():
            if scores:
                trend_data.append({
                    "date": date,
                    "avg_score": sum(scores) / len(scores),
                    "article_count": len(scores)
                })
        
        return {
            "category": category,
            "trends": trend_data,
            "total_articles": len(articles),
            "avg_profit_score": sum(a.profit_score or 0 for a in articles) / len(articles)
        }
    
    def _calculate_market_trends(self, articles: List[NewsArticle]) -> List[Dict[str, Any]]:
        """Calculate market trends from articles"""
        if not articles:
            return []
        
        # Simple trend calculation based on recent vs older articles
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_articles = [a for a in articles if a.created_at >= recent_cutoff]
        older_articles = [a for a in articles if a.created_at < recent_cutoff]
        
        if not recent_articles or not older_articles:
            return []
        
        recent_avg = sum(a.profit_score or 0 for a in recent_articles) / len(recent_articles)
        older_avg = sum(a.profit_score or 0 for a in older_articles) / len(older_articles)
        
        trend_direction = "up" if recent_avg > older_avg else "down" if recent_avg < older_avg else "stable"
        
        return [{
            "trend_direction": trend_direction,
            "recent_avg_score": recent_avg,
            "older_avg_score": older_avg,
            "change_percentage": ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        }]

db = InMemoryDatabase()
