import sqlite3
import json
from contextlib import closing
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from news_scraper import timeutil  # noqa: F401  (registers sqlite datetime adapter)
from news_scraper.models import NewsArticle, NewsArticleCreate, NewsArticleUpdate, NewsCategory, SentimentScore
import threading
import os

# Column order of `SELECT *` on articles. New columns are appended ONLY at the
# end so positional mapping stays stable across the idempotent ALTER migrations.
ARTICLE_COLUMNS = [
    'id', 'title', 'content', 'source', 'url', 'category', 'sentiment',
    'profit_score', 'keywords', 'market_impact', 'investment_type',
    'potential_return', 'risk_level', 'time_horizon', 'related_companies',
    'market_cap_impact', 'regulatory_impact', 'created_at', 'updated_at',
    'article_cluster_id', 'corroboration_count', 'source_credibility_weight',
    'sentiment_multiplier', 'slack_notified',
]

# Columns the /articles endpoint may ORDER BY. Whitelisted so sort keys from
# the API can be interpolated into SQL safely.
SORTABLE_COLUMNS = {"created_at", "profit_score", "title", "source", "category"}


def parse_text_list(raw) -> List[str]:
    """Parse a stored text column into a list, tolerating both the legacy
    comma-joined format and the JSON-array format (Phase 1+)."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    raw = str(raw).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [item.strip() for item in raw.split(',') if item.strip()]

class PersistentDatabase:
    def __init__(self, db_path: str = "news_scraper.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with tables"""
        with closing(sqlite3.connect(self.db_path)) as conn:
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    article_cluster_id TEXT,
                    corroboration_count INTEGER DEFAULT 1,
                    source_credibility_weight REAL,
                    sentiment_multiplier REAL
                )
            ''')
            
            # Idempotent migration for new columns. SQLite does NOT support
            # `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so check PRAGMA and
            # ALTER each missing column. New columns are always appended at the
            # end (they do not reorder existing rows).
            existing_columns = {row[1] for row in cursor.execute('PRAGMA table_info(articles)').fetchall()}
            new_columns = {
                'article_cluster_id': 'TEXT',
                'corroboration_count': 'INTEGER DEFAULT 1',
                'source_credibility_weight': 'REAL',
                'sentiment_multiplier': 'REAL',
                'slack_notified': 'INTEGER DEFAULT 0',
            }
            for column_name, column_ddl in new_columns.items():
                if column_name not in existing_columns:
                    cursor.execute(f'ALTER TABLE articles ADD COLUMN {column_name} {column_ddl}')

            # Phase 3: backtest results table. One row per (article, asset);
            # INSERT OR REPLACE makes re-running a backtest idempotent.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    asset_symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    predicted_score REAL NOT NULL,
                    price_at_publish REAL,
                    price_1h REAL,
                    price_24h REAL,
                    price_7d REAL,
                    pct_change_1h REAL,
                    pct_change_24h REAL,
                    pct_change_7d REAL,
                    btc_pct_change_1h REAL,
                    btc_pct_change_24h REAL,
                    btc_pct_change_7d REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    backtested_at TIMESTAMP,
                    data_source TEXT,
                    FOREIGN KEY (article_id) REFERENCES articles(id),
                    UNIQUE (article_id, asset_symbol)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_article ON backtest_results(article_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_symbol ON backtest_results(asset_symbol)')

            # Track C observability: one audit row per scrape run (any trigger),
            # so unattended operation is diagnosable from the DB alone.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scrape_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    trigger TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scraped_count INTEGER,
                    stored_count INTEGER,
                    skipped_duplicates INTEGER,
                    cluster_assignments INTEGER,
                    duration_ms INTEGER,
                    sources_json TEXT,
                    error TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrape_runs_started ON scrape_runs(started_at)')

            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON articles(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment ON articles(sentiment)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_profit_score ON articles(profit_score)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON articles(source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cluster_id ON articles(article_cluster_id)')

            conn.commit()
    
    def create_article(self, article_data: NewsArticleCreate) -> Optional[NewsArticle]:
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Check for duplicates by title or URL
                if article_data.url:
                    cursor.execute('SELECT id FROM articles WHERE url = ?', (article_data.url,))
                    existing = cursor.fetchone()
                    if existing:
                        return None  # Skip duplicate by URL
                
                # Check for duplicate titles (exact match)
                cursor.execute('SELECT id FROM articles WHERE title = ?', (article_data.title,))
                existing = cursor.fetchone()
                if existing:
                    return None  # Skip duplicate by title
                
                cursor.execute('''
                    INSERT INTO articles (
                        title, content, source, url, category, sentiment, profit_score,
                        keywords, market_impact, investment_type, potential_return,
                        risk_level, time_horizon, related_companies, market_cap_impact,
                        regulatory_impact, created_at, updated_at,
                        article_cluster_id, corroboration_count,
                        source_credibility_weight, sentiment_multiplier
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article_data.title,
                    article_data.content,
                    article_data.source,
                    article_data.url,
                    article_data.category.value,
                    article_data.sentiment.value if article_data.sentiment else None,
                    article_data.profit_score,
                    json.dumps(article_data.keywords) if article_data.keywords else None,
                    article_data.market_impact.value if article_data.market_impact else None,
                    article_data.investment_type.value if article_data.investment_type else None,
                    article_data.potential_return,
                    article_data.risk_level,
                    article_data.time_horizon,
                    ','.join(article_data.related_companies) if article_data.related_companies else None,
                    article_data.market_cap_impact,
                    article_data.regulatory_impact,
                    timeutil.utcnow(),
                    timeutil.utcnow(),
                    article_data.article_cluster_id,
                    article_data.corroboration_count,
                    article_data.source_credibility_weight,
                    article_data.sentiment_multiplier
                ))
                
                article_id = cursor.lastrowid
                conn.commit()
                
                return self.get_article(article_id)
    
    def get_article(self, article_id: int) -> Optional[NewsArticle]:
        with closing(sqlite3.connect(self.db_path)) as conn:
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
        search: Optional[str] = None,
        sort_by: str = "created_at",
        order: str = "desc"
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
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            count_query = query.replace('SELECT *', 'SELECT COUNT(*)')
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            sort_column = sort_by if sort_by in SORTABLE_COLUMNS else "created_at"
            direction = "ASC" if order.lower() == "asc" else "DESC"
            query += f' ORDER BY {sort_column} {direction} LIMIT ? OFFSET ?'
            params.extend([limit, skip])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            articles = [self._row_to_article(row) for row in rows]
            return articles, total
    
    def update_article(self, article_id: int, article_data: NewsArticleUpdate) -> Optional[NewsArticle]:
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
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
                    params.append(json.dumps(article_data.keywords) if article_data.keywords else None)
                
                if update_fields:
                    update_fields.append('updated_at = ?')
                    params.append(timeutil.utcnow())
                    params.append(article_id)
                    
                    query = f'UPDATE articles SET {", ".join(update_fields)} WHERE id = ?'
                    cursor.execute(query, params)
                    conn.commit()
                    
                    return self.get_article(article_id)
                
                return None
    
    def delete_article(self, article_id: int) -> bool:
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM articles WHERE id = ?', (article_id,))
                conn.commit()
                return cursor.rowcount > 0
    
    def get_stats(self) -> Dict[str, Any]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            
            # Get total articles
            cursor.execute('SELECT COUNT(*) FROM articles')
            total = cursor.fetchone()[0]
            
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
            result = cursor.fetchone()
            latest_article = result[0] if result else None
            
            # Get high-profit opportunities
            cursor.execute('SELECT COUNT(*) FROM articles WHERE profit_score >= 7.0')
            high_profit_count = cursor.fetchone()[0]
            
            return {
                "total_articles": total,
                "categories": categories,
                "sentiments": sentiments,
                "avg_profit_score": avg_profit_score,
                "latest_article": latest_article,
                "high_profit_opportunities": high_profit_count,
                "market_trends": []
            }
    
    def get_profit_opportunities(self, min_score: float = 7.0, limit: int = 20) -> List[Dict[str, Any]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn:
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

    def get_unsent_high_profit_articles(self, min_score: float = 5.0) -> List[Dict[str, Any]]:
        """Get high-profit articles that haven't been sent to Slack yet."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, url, profit_score, category, sentiment, source, created_at
                FROM articles 
                WHERE profit_score >= ? AND (slack_notified = 0 OR slack_notified IS NULL)
                ORDER BY profit_score DESC, created_at DESC
            ''', (min_score,))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "url": row[2],
                    "profit_score": row[3],
                    "category": row[4],
                    "sentiment": row[5],
                    "source": row[6],
                    "created_at": row[7]
                }
                for row in rows
            ]

    def mark_articles_as_notified(self, article_ids: List[int]) -> bool:
        """Mark articles as sent to Slack to prevent duplicates."""
        if not article_ids:
            return True
        
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(article_ids))
                cursor.execute(
                    f'UPDATE articles SET slack_notified = 1 WHERE id IN ({placeholders})',
                    article_ids
                )
                conn.commit()
                return cursor.rowcount > 0

    def reset_notification_status(self, article_ids: List[int]) -> bool:
        """Reset notification status for specific articles (for re-sending)."""
        if not article_ids:
            return True
        
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(article_ids))
                cursor.execute(
                    f'UPDATE articles SET slack_notified = 0 WHERE id IN ({placeholders})',
                    article_ids
                )
                conn.commit()
                return cursor.rowcount > 0

    def get_recent_articles(self, hours: int = 12) -> List[Dict[str, Any]]:
        """Articles from the last N hours, used for cluster matching."""
        cutoff = timeutil.utcnow() - timedelta(hours=hours)
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, title, article_cluster_id, profit_score '
                'FROM articles WHERE created_at >= ? ORDER BY created_at DESC',
                (cutoff,),
            )
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "article_cluster_id": row[2],
                    "profit_score": row[3],
                }
                for row in cursor.fetchall()
            ]

    def get_clusters(self, min_corroboration: int = 2, limit: int = 20) -> List[Dict[str, Any]]:
        """Clusters with >= min_corroboration sources.

        Corroboration count is derived via COUNT(*) (never a stored counter);
        the cluster score is the max member score scaled by the corroboration
        multiplier (1.0x → 1.3x for 4+ sources).
        """
        corroboration_multipliers = {1: 1.0, 2: 1.15, 3: 1.15, 4: 1.3}
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT
                    article_cluster_id,
                    COUNT(*) AS corroboration_count,
                    MAX(profit_score) AS cluster_score,
                    (SELECT title FROM articles a2
                     WHERE a2.article_cluster_id = articles.article_cluster_id
                     ORDER BY created_at DESC LIMIT 1) AS title,
                    (SELECT source FROM articles a2
                     WHERE a2.article_cluster_id = articles.article_cluster_id
                     ORDER BY created_at DESC LIMIT 1) AS source,
                    (SELECT url FROM articles a2
                     WHERE a2.article_cluster_id = articles.article_cluster_id
                     ORDER BY created_at DESC LIMIT 1) AS url
                FROM articles
                WHERE article_cluster_id IS NOT NULL
                GROUP BY article_cluster_id
                -- NB: use COUNT(*) here, NOT the alias 'corroboration_count':
                -- the articles table HAS a column of that name (Phase 1), and
                -- SQLite resolves the bare name to the column (always 1), not
                -- the aggregate alias — which silently breaks the filter.
                HAVING COUNT(*) >= ?
                ORDER BY corroboration_count DESC, cluster_score DESC
                LIMIT ?
                ''',
                (min_corroboration, limit),
            )
            clusters = []
            for row in cursor.fetchall():
                multiplier = corroboration_multipliers.get(row[1], 1.3)
                clusters.append({
                    "cluster_id": row[0],
                    "corroboration_count": row[1],
                    "base_score": row[2],
                    "cluster_score": min(10.0, (row[2] or 0.0) * multiplier),
                    "title": row[3],
                    "source": row[4],
                    "url": row[5],
                })
            return clusters

    def get_cluster_articles(self, cluster_id: str) -> List[Dict[str, Any]]:
        """All articles in a cluster, oldest first."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, title, source, url, profit_score, sentiment, created_at '
                'FROM articles WHERE article_cluster_id = ? ORDER BY created_at',
                (cluster_id,),
            )
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "source": row[2],
                    "url": row[3],
                    "profit_score": row[4],
                    "sentiment": row[5],
                    "created_at": row[6],
                }
                for row in cursor.fetchall()
            ]

    # ------------------------------------------------------------------
    # Phase 3: Backtesting
    # ------------------------------------------------------------------

    def get_articles_in_timerange(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Articles published in [start, end), for backtest batch jobs."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, title, content, source, url, category, profit_score, keywords, created_at '
                'FROM articles WHERE created_at >= ? AND created_at < ? ORDER BY created_at',
                (start, end),
            )
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "source": row[3],
                    "url": row[4],
                    "category": row[5],
                    "profit_score": row[6],
                    "keywords": parse_text_list(row[7]),
                    "created_at": datetime.fromisoformat(row[8]) if row[8] else None,
                }
                for row in cursor.fetchall()
            ]

    def has_backtest_results(self, article_id: int) -> bool:
        """True if any backtest result exists for the article (backfill skip check)."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM backtest_results WHERE article_id = ? LIMIT 1', (article_id,))
            return cursor.fetchone() is not None

    def record_scrape_run(self, run: Dict[str, Any]) -> Optional[int]:
        """Persist one scrape-run audit row (any trigger, success or failure)."""
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO scrape_runs (
                        started_at, finished_at, trigger, status, scraped_count,
                        stored_count, skipped_duplicates, cluster_assignments,
                        duration_ms, sources_json, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    run["started_at"],
                    run.get("finished_at"),
                    run.get("trigger", "manual"),
                    run["status"],
                    run.get("scraped_count"),
                    run.get("stored_count"),
                    run.get("skipped_duplicates"),
                    run.get("cluster_assignments"),
                    run.get("duration_ms"),
                    json.dumps(run.get("sources_scraped") or []),
                    run.get("error"),
                ))
                conn.commit()
                return cursor.lastrowid

    def get_scrape_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Most recent scrape runs, newest first."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT started_at, finished_at, trigger, status, scraped_count, stored_count, '
                'skipped_duplicates, cluster_assignments, duration_ms, sources_json, error '
                'FROM scrape_runs ORDER BY id DESC LIMIT ?',
                (limit,),
            )
            return [
                {
                    "started_at": row[0],
                    "finished_at": row[1],
                    "trigger": row[2],
                    "status": row[3],
                    "scraped_count": row[4],
                    "stored_count": row[5],
                    "skipped_duplicates": row[6],
                    "cluster_assignments": row[7],
                    "duration_ms": row[8],
                    "sources_scraped": parse_text_list(row[9]),
                    "error": row[10],
                }
                for row in cursor.fetchall()
            ]

    def store_backtest_result(self, result: Dict[str, Any]) -> Optional[int]:
        """Store (or idempotently re-store) one backtest result."""
        with self._lock:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO backtest_results (
                        article_id, asset_symbol, asset_type, predicted_score,
                        price_at_publish, price_1h, price_24h, price_7d,
                        pct_change_1h, pct_change_24h, pct_change_7d,
                        btc_pct_change_1h, btc_pct_change_24h, btc_pct_change_7d,
                        backtested_at, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result["article_id"],
                    result["asset_symbol"],
                    result["asset_type"],
                    result["predicted_score"],
                    result.get("price_at_publish"),
                    result.get("price_1h"),
                    result.get("price_24h"),
                    result.get("price_7d"),
                    result.get("pct_change_1h"),
                    result.get("pct_change_24h"),
                    result.get("pct_change_7d"),
                    result.get("btc_pct_change_1h"),
                    result.get("btc_pct_change_24h"),
                    result.get("btc_pct_change_7d"),
                    result.get("backtested_at", timeutil.utcnow()),
                    result.get("data_source", "coingecko"),
                ))
                conn.commit()
                return cursor.lastrowid

    def get_backtest_accuracy(self, time_window: str, min_samples: int) -> Dict[str, Any]:
        """Spearman rank correlation between predicted scores and EXCESS returns.

        Validation uses excess return vs market (BTC): raw price change is
        dominated by market beta. Column names are taken from a fixed map —
        never interpolated from user input.
        """
        window_map = {
            "1h": ("pct_change_1h", "btc_pct_change_1h"),
            "24h": ("pct_change_24h", "btc_pct_change_24h"),
            "7d": ("pct_change_7d", "btc_pct_change_7d"),
        }
        col, btc_col = window_map.get(time_window, ("pct_change_24h", "btc_pct_change_24h"))

        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT predicted_score, ({col} - {btc_col}) as excess_movement
                FROM backtest_results
                WHERE {col} IS NOT NULL AND {btc_col} IS NOT NULL
            """)
            data = cursor.fetchall()

        if len(data) < min_samples:
            return {"error": "Insufficient data", "total_samples": len(data)}

        import numpy as np
        from scipy.stats import spearmanr

        predicted = [row[0] for row in data]
        actual = [row[1] for row in data]

        correlation, p_value = spearmanr(predicted, actual)
        buckets = self._calculate_score_buckets(predicted, actual)

        return {
            "correlation": float(correlation),
            "p_value": float(p_value),
            "total_samples": len(data),
            "avg_predicted": float(np.mean(predicted)),
            "avg_actual": float(np.mean(actual)),
            "score_buckets": buckets,
        }

    @staticmethod
    def _calculate_score_buckets(predicted: list, actual: list) -> Dict[str, Any]:
        """Group scores into buckets and average the excess outcome per bucket."""
        import numpy as np

        buckets = {"0-2": [], "2-4": [], "4-6": [], "6-8": [], "8-10": []}
        for pred, act in zip(predicted, actual):
            if pred < 2:
                buckets["0-2"].append(act)
            elif pred < 4:
                buckets["2-4"].append(act)
            elif pred < 6:
                buckets["4-6"].append(act)
            elif pred < 8:
                buckets["6-8"].append(act)
            else:
                buckets["8-10"].append(act)

        return {
            bucket: {
                "avg_movement": float(np.mean(movements)) if movements else 0,
                "count": len(movements),
            }
            for bucket, movements in buckets.items()
        }

    def get_keyword_performance(self, limit: int) -> List[Dict[str, Any]]:
        """Keywords ranked by average 24h EXCESS movement of backtested articles."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    keyword.value as keyword,
                    COUNT(*) as appearances,
                    AVG(br.pct_change_24h - br.btc_pct_change_24h) as avg_24h_excess_movement,
                    AVG(a.profit_score) as avg_score
                FROM articles a
                JOIN backtest_results br ON a.id = br.article_id
                CROSS JOIN json_each(a.keywords) AS keyword
                WHERE br.pct_change_24h IS NOT NULL AND br.btc_pct_change_24h IS NOT NULL
                GROUP BY keyword.value
                HAVING COUNT(*) >= 5
                ORDER BY avg_24h_excess_movement DESC
                LIMIT ?
            """, (limit,))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_source_accuracy(self) -> List[Dict[str, Any]]:
        """Per-source accuracy on 24h EXCESS movement (min 5 backtested articles)."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    a.source,
                    COUNT(*) as total_articles,
                    AVG(a.profit_score) as avg_predicted_score,
                    AVG(br.pct_change_24h - br.btc_pct_change_24h) as avg_24h_excess_movement,
                    AVG(CASE
                        WHEN (a.profit_score > 7 AND (br.pct_change_24h - br.btc_pct_change_24h) > 5) OR
                             (a.profit_score < 4 AND (br.pct_change_24h - br.btc_pct_change_24h) < 0)
                        THEN 1.0 ELSE 0.0
                    END) as accuracy_rate
                FROM articles a
                JOIN backtest_results br ON a.id = br.article_id
                WHERE br.pct_change_24h IS NOT NULL AND br.btc_pct_change_24h IS NOT NULL
                GROUP BY a.source
                HAVING COUNT(*) >= 5
                ORDER BY accuracy_rate DESC
            """)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_category_trends(self, category: NewsCategory) -> Dict[str, Any]:
        with closing(sqlite3.connect(self.db_path)) as conn:
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
        """Convert database row to NewsArticle object.

        Rows are mapped by column name (ARTICLE_COLUMNS), tolerant of both
        legacy comma-joined keyword strings and the new JSON-array format.
        """
        data = dict(zip(ARTICLE_COLUMNS, row))

        return NewsArticle(
            id=data['id'],
            title=data['title'],
            content=data['content'],
            source=data['source'],
            url=data['url'],
            category=NewsCategory(data['category']),
            sentiment=SentimentScore(data['sentiment']) if data['sentiment'] else None,
            profit_score=data['profit_score'],
            keywords=parse_text_list(data['keywords']),
            market_impact=data['market_impact'],
            investment_type=data['investment_type'],
            potential_return=data['potential_return'],
            risk_level=data['risk_level'],
            time_horizon=data['time_horizon'],
            related_companies=parse_text_list(data['related_companies']),
            market_cap_impact=data['market_cap_impact'],
            regulatory_impact=data['regulatory_impact'],
            created_at=datetime.fromisoformat(data['created_at']) if data['created_at'] else timeutil.utcnow(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data['updated_at'] else timeutil.utcnow(),
            article_cluster_id=data['article_cluster_id'],
            corroboration_count=data['corroboration_count'],
            source_credibility_weight=data['source_credibility_weight'],
            sentiment_multiplier=data['sentiment_multiplier'],
        )
    
    def get_database_path(self) -> str:
        """Get the path to the database file"""
        return os.path.abspath(self.db_path)

# Create persistent database instance
persistent_db = PersistentDatabase() 