import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.models import NewsArticle, NewsArticleCreate, NewsArticleUpdate, NewsCategory, SentimentScore
import threading
import os

class PersistentDatabase:
    def __init__(self, db_path: str = "news_scraper.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create articles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    category TEXT NOT NULL,
                    sentiment TEXT,
                    profit_score REAL,
                    keywords TEXT,
                    market_impact TEXT,
                    investment_type TEXT,
                    potential_return REAL,
                    risk_level REAL,
                    time_horizon TEXT,
                    related_companies TEXT,
                    market_cap_impact TEXT,
                    regulatory_impact TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON articles(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment ON articles(sentiment)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_profit_score ON articles(profit_score)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON articles(source)')
            
            conn.commit()
    
    def create_article(self, article_data: NewsArticleCreate) -> NewsArticle:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO articles (
                        title, content, source, url, category, sentiment, profit_score,
                        keywords, market_impact, investment_type, potential_return,
                        risk_level, time_horizon, related_companies, market_cap_impact,
                        regulatory_impact, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article_data.title,
                    article_data.content,
                    article_data.source,
                    article_data.url,
                    article_data.category.value,
                    article_data.sentiment.value if article_data.sentiment else None,
                    article_data.profit_score,
                    ','.join(article_data.keywords) if article_data.keywords else None,
                    article_data.market_impact.value if article_data.market_impact else None,
                    article_data.investment_type.value if article_data.investment_type else None,
                    article_data.potential_return,
                    article_data.risk_level,
                    article_data.time_horizon,
                    ','.join(article_data.related_companies) if article_data.related_companies else None,
                    article_data.market_cap_impact,
                    article_data.regulatory_impact,
                    datetime.utcnow(),
                    datetime.utcnow()
                ))
                
                article_id = cursor.lastrowid
                conn.commit()
                
                return self.get_article(article_id)
    
    def get_article(self, article_id: int) -> Optional[NewsArticle]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM articles WHERE id = ?', (article_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_article(row)
            return None
    
    def get_articles(
        self, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[NewsCategory] = None,
        sentiment: Optional[SentimentScore] = None,
        min_profit_score: Optional[float] = None,
        search: Optional[str] = None
    ) -> tuple[List[NewsArticle], int]:
        
        query = 'SELECT * FROM articles WHERE 1=1'
        params = []
        
        if category:
            query += ' AND category = ?'
            params.append(category.value)
        
        if sentiment:
            query += ' AND sentiment = ?'
            params.append(sentiment.value)
        
        if min_profit_score is not None:
            query += ' AND profit_score >= ?'
            params.append(min_profit_score)
        
        if search:
            query += ' AND (title LIKE ? OR content LIKE ? OR source LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        # Get total count
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            count_query = query.replace('SELECT *', 'SELECT COUNT(*)')
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, skip])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            articles = [self._row_to_article(row) for row in rows]
            return articles, total
    
    def update_article(self, article_id: int, article_data: NewsArticleUpdate) -> Optional[NewsArticle]:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update query dynamically
                update_fields = []
                params = []
                
                if article_data.title is not None:
                    update_fields.append('title = ?')
                    params.append(article_data.title)
                
                if article_data.content is not None:
                    update_fields.append('content = ?')
                    params.append(article_data.content)
                
                if article_data.source is not None:
                    update_fields.append('source = ?')
                    params.append(article_data.source)
                
                if article_data.url is not None:
                    update_fields.append('url = ?')
                    params.append(article_data.url)
                
                if article_data.category is not None:
                    update_fields.append('category = ?')
                    params.append(article_data.category.value)
                
                if article_data.sentiment is not None:
                    update_fields.append('sentiment = ?')
                    params.append(article_data.sentiment.value)
                
                if article_data.profit_score is not None:
                    update_fields.append('profit_score = ?')
                    params.append(article_data.profit_score)
                
                if article_data.keywords is not None:
                    update_fields.append('keywords = ?')
                    params.append(','.join(article_data.keywords))
                
                if update_fields:
                    update_fields.append('updated_at = ?')
                    params.append(datetime.utcnow())
                    params.append(article_id)
                    
                    query = f'UPDATE articles SET {", ".join(update_fields)} WHERE id = ?'
                    cursor.execute(query, params)
                    conn.commit()
                    
                    return self.get_article(article_id)
                
                return None
    
    def delete_article(self, article_id: int) -> bool:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
                conn.commit()
                return cursor.rowcount > 0
    
    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get total articles
            cursor.execute('SELECT COUNT(*) FROM articles')
            total = cursor.fetchone()[0]
            
            if total == 0:
                return {
                    "total_articles": 0,
                    "categories": {},
                    "sentiments": {},
                    "average_profit_score": None,
                    "latest_article": None,
                    "high_profit_opportunities": 0,
                    "market_trends": []
                }
            
            # Get categories
            cursor.execute('SELECT category, COUNT(*) FROM articles GROUP BY category')
            categories = dict(cursor.fetchall())
            
            # Get sentiments
            cursor.execute('SELECT sentiment, COUNT(*) FROM articles WHERE sentiment IS NOT NULL GROUP BY sentiment')
            sentiments = dict(cursor.fetchall())
            
            # Get average profit score
            cursor.execute('SELECT AVG(profit_score) FROM articles WHERE profit_score IS NOT NULL')
            avg_profit_score = cursor.fetchone()[0]
            
            # Get latest article
            cursor.execute('SELECT created_at FROM articles ORDER BY created_at DESC LIMIT 1')
            latest_row = cursor.fetchone()
            latest_article = latest_row[0] if latest_row else None
            
            # Get high-profit opportunities
            cursor.execute('SELECT COUNT(*) FROM articles WHERE profit_score >= 7.0')
            high_profit_count = cursor.fetchone()[0]
            
            return {
                "total_articles": total,
                "categories": categories,
                "sentiments": sentiments,
                "average_profit_score": avg_profit_score,
                "latest_article": latest_article,
                "high_profit_opportunities": high_profit_count,
                "market_trends": []
            }
    
    def get_profit_opportunities(self, min_score: float = 7.0, limit: int = 20) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, profit_score, category, sentiment, created_at, source, url
                FROM articles 
                WHERE profit_score >= ? 
                ORDER BY profit_score DESC 
                LIMIT ?
            ''', (min_score, limit))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "profit_score": row[2],
                    "category": row[3],
                    "sentiment": row[4],
                    "created_at": row[5],
                    "source": row[6],
                    "url": row[7]
                }
                for row in rows
            ]
    
    def get_market_trends(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category, AVG(profit_score) as avg_score, COUNT(*) as count
                FROM articles 
                WHERE profit_score IS NOT NULL 
                GROUP BY category
                HAVING count >= 3
            ''')
            
            rows = cursor.fetchall()
            trends = []
            
            for row in rows:
                category, avg_score, count = row
                
                # Get recent articles for trend analysis
                cursor.execute('''
                    SELECT AVG(profit_score) 
                    FROM articles 
                    WHERE category = ? AND profit_score IS NOT NULL
                    ORDER BY created_at DESC 
                    LIMIT 5
                ''', (category,))
                
                recent_avg = cursor.fetchone()[0] or 0
                
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
                    "article_count": count
                })
            
            return trends
    
    def get_profit_alerts(self, threshold: float = 8.0) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, profit_score, category, sentiment, created_at, source
                FROM articles 
                WHERE profit_score >= ? 
                ORDER BY profit_score DESC
            ''', (threshold,))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "profit_score": row[2],
                    "category": row[3],
                    "sentiment": row[4],
                    "created_at": row[5],
                    "source": row[6],
                    "urgency": "high" if row[2] >= 9.0 else "medium"
                }
                for row in rows
            ]
    
    def get_company_mentions(self) -> List[Dict[str, Any]]:
        # This would need more complex implementation for company detection
        # For now, return empty list
        return []
    
    def get_category_trends(self, category: NewsCategory) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DATE(created_at) as date, AVG(profit_score) as avg_score, COUNT(*) as count
                FROM articles 
                WHERE category = ? AND profit_score IS NOT NULL
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (category.value,))
            
            rows = cursor.fetchall()
            trend_data = [
                {
                    "date": row[0],
                    "avg_score": row[1],
                    "article_count": row[2]
                }
                for row in rows
            ]
            
            # Get total stats
            cursor.execute('''
                SELECT COUNT(*), AVG(profit_score) 
                FROM articles 
                WHERE category = ? AND profit_score IS NOT NULL
            ''', (category.value,))
            
            total_articles, avg_profit_score = cursor.fetchone()
            
            return {
                "category": category.value,
                "trends": trend_data,
                "total_articles": total_articles or 0,
                "avg_profit_score": avg_profit_score or 0
            }
    
    def _row_to_article(self, row) -> NewsArticle:
        """Convert database row to NewsArticle object"""
        return NewsArticle(
            id=row[0],
            title=row[1],
            content=row[2],
            source=row[3],
            url=row[4],
            category=NewsCategory(row[5]),
            sentiment=SentimentScore(row[6]) if row[6] else None,
            profit_score=row[7],
            keywords=row[8].split(',') if row[8] else [],
            market_impact=row[9],
            investment_type=row[10],
            potential_return=row[11],
            risk_level=row[12],
            time_horizon=row[13],
            related_companies=row[14].split(',') if row[14] else [],
            market_cap_impact=row[15],
            regulatory_impact=row[16],
            created_at=datetime.fromisoformat(row[17]) if row[17] else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row[18]) if row[18] else datetime.utcnow()
        )
    
    def get_database_path(self) -> str:
        """Get the path to the database file"""
        return os.path.abspath(self.db_path)

# Create persistent database instance
persistent_db = PersistentDatabase() 