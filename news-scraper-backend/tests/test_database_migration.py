"""Tests for the idempotent schema migration and JSON keyword storage (Phase 1, Task 1.4/1.5)."""

import json
import sqlite3
from contextlib import closing

from news_scraper.models import NewsArticleCreate, NewsCategory, SentimentScore
from news_scraper.persistent_database import PersistentDatabase

OLD_SCHEMA_SQL = """
    CREATE TABLE articles (
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
"""

NEW_COLUMNS = (
    "article_cluster_id",
    "corroboration_count",
    "source_credibility_weight",
    "sentiment_multiplier",
)


def _columns(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(articles)")}


class TestMigration:
    def test_fresh_database_has_all_columns(self, tmp_db_path):
        PersistentDatabase(tmp_db_path)
        cols = _columns(tmp_db_path)
        for col in NEW_COLUMNS:
            assert col in cols

    def test_migration_adds_columns_to_old_schema(self, tmp_db_path):
        """An old 19-column database must be migrated in place without data loss."""
        with closing(sqlite3.connect(tmp_db_path)) as conn:
            conn.execute(OLD_SCHEMA_SQL)
            conn.execute(
                "INSERT INTO articles (title, content, source, url, category, profit_score) "
                "VALUES ('Old article', 'content', 'coindesk_rss', 'http://x', 'crypto', 8.0)"
            )
            conn.commit()

        PersistentDatabase(tmp_db_path)

        cols = _columns(tmp_db_path)
        for col in NEW_COLUMNS:
            assert col in cols
        # Existing data survives
        with closing(sqlite3.connect(tmp_db_path)) as conn:
            title = conn.execute("SELECT title FROM articles").fetchone()[0]
        assert title == "Old article"

    def test_migration_is_idempotent(self, tmp_db_path):
        """Running init twice must not raise 'duplicate column name'."""
        PersistentDatabase(tmp_db_path)
        PersistentDatabase(tmp_db_path)  # second init: columns already exist


class TestStorageRoundTrip:
    def _make_db(self, tmp_db_path):
        return PersistentDatabase(tmp_db_path)

    def test_new_fields_round_trip(self, tmp_db_path):
        db = self._make_db(tmp_db_path)
        article = NewsArticleCreate(
            title="Bitcoin ETF approved",
            content="SEC approves the spot bitcoin ETF",
            source="coindesk_rss",
            url="http://example.com/1",
            category=NewsCategory.CRYPTO,
            sentiment=SentimentScore.POSITIVE,
            profit_score=9.6,
            keywords=["ethereum", "bitcoin"],
            article_cluster_id="cluster_abc123",
            corroboration_count=2,
            source_credibility_weight=1.2,
            sentiment_multiplier=1.1,
        )
        created = db.create_article(article)
        fetched = db.get_article(created.id)

        assert fetched.article_cluster_id == "cluster_abc123"
        assert fetched.corroboration_count == 2
        assert fetched.source_credibility_weight == 1.2
        assert fetched.sentiment_multiplier == 1.1
        assert fetched.keywords == ["ethereum", "bitcoin"]

    def test_keywords_stored_as_json_array(self, tmp_db_path):
        """Phase 3 analytics use json_each(), which requires valid JSON (Task 3.6 fix)."""
        db = self._make_db(tmp_db_path)
        created = db.create_article(
            NewsArticleCreate(
                title="Some article",
                content="content",
                source="coindesk_rss",
                category=NewsCategory.CRYPTO,
                keywords=["ethereum", "bitcoin"],
            )
        )
        with closing(sqlite3.connect(tmp_db_path)) as conn:
            raw = conn.execute("SELECT keywords FROM articles WHERE id = ?", (created.id,)).fetchone()[0]
            json_values = conn.execute(
                "SELECT value FROM json_each((SELECT keywords FROM articles WHERE id = ?))", (created.id,)
            ).fetchall()

        assert json.loads(raw) == ["ethereum", "bitcoin"]
        assert {row[0] for row in json_values} == {"ethereum", "bitcoin"}

    def test_legacy_comma_keywords_still_parse(self, tmp_db_path):
        """Rows written before the JSON switch (comma-joined) must still parse."""
        db = self._make_db(tmp_db_path)
        with closing(sqlite3.connect(tmp_db_path)) as conn:
            conn.execute(
                "INSERT INTO articles (title, content, source, url, category, keywords) "
                "VALUES ('Legacy', 'content', 'coindesk_rss', 'http://y', 'crypto', 'ethereum,bitcoin')"
            )
            conn.commit()
            row_id = conn.execute("SELECT id FROM articles WHERE title = 'Legacy'").fetchone()[0]

        fetched = db.get_article(row_id)
        assert fetched.keywords == ["ethereum", "bitcoin"]

    def test_empty_keywords_round_trip(self, tmp_db_path):
        db = self._make_db(tmp_db_path)
        created = db.create_article(
            NewsArticleCreate(title="No keywords", content="content", source="coindesk_rss", category=NewsCategory.GENERAL)
        )
        assert db.get_article(created.id).keywords == []
