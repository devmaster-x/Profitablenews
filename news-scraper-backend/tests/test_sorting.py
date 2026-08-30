"""Tests for the /articles sort_by/order options (server-side sorting)."""

import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

import news_scraper.main as main_module
from news_scraper.main import app
from news_scraper.persistent_database import PersistentDatabase

INSERT_SQL = (
    "INSERT INTO articles (title, content, source, url, category, sentiment, profit_score, created_at, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _seed(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        rows = [
            ("Article 0", 5.0, "2026-08-01 10:00:00"),
            ("Article 1", 9.5, "2026-08-02 10:00:00"),
            ("Article 2", 7.5, "2026-08-03 10:00:00"),
            ("Article 3", 2.0, "2026-08-04 10:00:00"),
        ]
        for i, (title, score, created) in enumerate(rows):
            conn.execute(
                INSERT_SQL,
                (title, "content", "coindesk_rss", f"http://example.com/{i}", "crypto", "neutral", score, created, created),
            )
        conn.commit()


class TestArticleSorting:
    def _db(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        _seed(tmp_db_path)
        return db

    def test_default_sort_is_newest_first(self, tmp_db_path):
        db = self._db(tmp_db_path)
        articles, _ = db.get_articles()
        assert [a.created_at.isoformat() for a in articles] == [
            "2026-08-04T10:00:00",
            "2026-08-03T10:00:00",
            "2026-08-02T10:00:00",
            "2026-08-01T10:00:00",
        ]

    def test_sort_by_profit_score_desc(self, tmp_db_path):
        db = self._db(tmp_db_path)
        articles, _ = db.get_articles(sort_by="profit_score", order="desc")
        assert [a.profit_score for a in articles] == [9.5, 7.5, 5.0, 2.0]

    def test_sort_by_profit_score_asc(self, tmp_db_path):
        db = self._db(tmp_db_path)
        articles, _ = db.get_articles(sort_by="profit_score", order="asc")
        assert [a.profit_score for a in articles] == [2.0, 5.0, 7.5, 9.5]

    def test_sort_by_title_asc(self, tmp_db_path):
        db = self._db(tmp_db_path)
        articles, _ = db.get_articles(sort_by="title", order="asc")
        assert [a.title for a in articles] == ["Article 0", "Article 1", "Article 2", "Article 3"]

    def test_unknown_sort_column_falls_back_to_created_at(self, tmp_db_path):
        db = self._db(tmp_db_path)
        articles, _ = db.get_articles(sort_by="injection_col", order="desc")
        assert [a.title for a in articles] == ["Article 3", "Article 2", "Article 1", "Article 0"]

    def test_unknown_sort_column_cannot_inject_sql(self, tmp_db_path):
        db = self._db(tmp_db_path)
        db.get_articles(sort_by="profit_score; DROP TABLE articles", order="desc")
        with closing(sqlite3.connect(tmp_db_path)) as conn:
            table_exists = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='articles'"
            ).fetchone()[0]
        assert table_exists == 1

    def test_invalid_order_direction_falls_back_to_desc(self, tmp_db_path):
        db = self._db(tmp_db_path)
        articles, _ = db.get_articles(sort_by="profit_score", order="up")
        assert [a.profit_score for a in articles] == [9.5, 7.5, 5.0, 2.0]


@pytest.fixture()
def api_client(tmp_db_path):
    db = PersistentDatabase(tmp_db_path)
    _seed(tmp_db_path)
    original_db = main_module.db
    main_module.db = db
    yield TestClient(app)
    main_module.db = original_db


class TestArticleSortingApi:
    def test_articles_endpoint_sorts_by_score_desc(self, api_client):
        response = api_client.get("/articles", params={"sort_by": "profit_score", "order": "desc"})
        assert response.status_code == 200
        scores = [a["profit_score"] for a in response.json()["articles"]]
        assert scores == [9.5, 7.5, 5.0, 2.0]

    def test_articles_endpoint_defaults_to_newest_first(self, api_client):
        response = api_client.get("/articles")
        assert response.status_code == 200
        titles = [a["title"] for a in response.json()["articles"]]
        assert titles == ["Article 3", "Article 2", "Article 1", "Article 0"]
