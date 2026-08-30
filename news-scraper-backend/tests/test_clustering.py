"""Tests for article clustering (Phase 2, Tasks 2.2/2.3).

Similarity tests load the real all-MiniLM-L6-v2 model once per session
(~80MB download on first ever run, cached afterwards).
"""

import pytest

from news_scraper.clustering import ArticleClusterer
from news_scraper.models import NewsArticleCreate, NewsCategory
from news_scraper.persistent_database import PersistentDatabase


@pytest.fixture(scope="module")
def clusterer():
    return ArticleClusterer(similarity_threshold=0.6)


class TestSimilarity:
    def test_same_event_scores_high(self, clusterer):
        sim = clusterer.compute_similarity("Bitcoin ETF approved by SEC", "SEC approves spot Bitcoin ETF")
        assert sim > 0.7

    def test_different_events_score_low(self, clusterer):
        sim = clusterer.compute_similarity("Bitcoin ETF approved by SEC", "Ethereum developers ship new testnet")
        assert sim < 0.5

    def test_same_event_beats_different_event(self, clusterer):
        same = clusterer.compute_similarity("Coinbase acquires Deribit for $2.9B", "Coinbase buys Deribit in $2.9B deal")
        different = clusterer.compute_similarity("Coinbase acquires Deribit for $2.9B", "Apple unveils new iPhone")
        assert same > different

    def test_fuzzy_match_bounds(self, clusterer):
        assert clusterer.fuzzy_match("Bitcoin ETF approved", "Bitcoin ETF approved") == 1.0
        assert clusterer.fuzzy_match("Bitcoin ETF approved", "Totally unrelated title here") < 0.5


class TestFindCluster:
    EXISTING = [
        {"id": 1, "title": "SEC approves spot Bitcoin ETF", "article_cluster_id": "clusterAAA"},
        {"id": 2, "title": "Ethereum developers ship new testnet", "article_cluster_id": "clusterBBB"},
    ]

    def test_near_duplicate_finds_cluster(self, clusterer):
        assert clusterer.find_cluster("Bitcoin ETF approved by SEC", self.EXISTING) == "clusterAAA"

    def test_different_event_returns_none(self, clusterer):
        # Shares the word 'SEC' with an existing title but is a different event
        assert clusterer.find_cluster("Ripple wins lawsuit against SEC", self.EXISTING) is None

    def test_falls_back_to_row_id_when_no_cluster_id(self, clusterer):
        articles = [{"id": 42, "title": "SEC approves spot Bitcoin ETF", "article_cluster_id": None}]
        assert clusterer.find_cluster("Bitcoin ETF approved by SEC", articles) == "42"

    def test_empty_existing_returns_none(self, clusterer):
        assert clusterer.find_cluster("Any title at all", []) is None

    def test_missing_titles_are_skipped(self, clusterer):
        articles = [{"id": 1, "title": None}, {"id": 2}]
        assert clusterer.find_cluster("Bitcoin ETF approved", articles) is None


class TestNewClusterId:
    def test_deterministic_short_hex(self):
        cid = ArticleClusterer.new_cluster_id("Bitcoin ETF approved")
        assert cid == ArticleClusterer.new_cluster_id("Bitcoin ETF approved")
        assert len(cid) == 12
        int(cid, 16)  # valid hex

    def test_different_titles_produce_different_ids(self):
        assert ArticleClusterer.new_cluster_id("Title A") != ArticleClusterer.new_cluster_id("Title B")


class TestEmbeddingCache:
    def test_encode_caches_results(self, clusterer):
        clusterer.encode("Bitcoin ETF approved")
        assert "Bitcoin ETF approved" in clusterer._embedding_cache


class TestClusterQueries:
    def _create(self, db, title, source, url, cluster_id, score=8.0):
        return db.create_article(NewsArticleCreate(
            title=title,
            content="content",
            source=source,
            url=url,
            category=NewsCategory.CRYPTO,
            profit_score=score,
            article_cluster_id=cluster_id,
        ))

    def test_corroboration_count_and_score_boost(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        for i, source in enumerate(["coindesk_rss", "cointelegraph_rss"]):
            self._create(db, f"Bitcoin ETF approved ({i})", source, f"http://example.com/{i}", "cluster12345")

        clusters = db.get_clusters(min_corroboration=2, limit=20)
        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster["cluster_id"] == "cluster12345"
        assert cluster["corroboration_count"] == 2
        # 8.0 * 1.15 multiplier for 2 sources
        assert cluster["cluster_score"] == pytest.approx(9.2)
        assert cluster["base_score"] == 8.0

    def test_cluster_score_capped_at_ten(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        for i in range(2):
            self._create(db, f"Big event ({i})", f"source_{i}", f"http://example.com/cap/{i}", "clusterCAP99", score=9.5)
        cluster = db.get_clusters(min_corroboration=2, limit=20)[0]
        assert cluster["cluster_score"] == 10.0

    def test_min_corroboration_filters_singletons(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        self._create(db, "Solo article", "coindesk_rss", "http://example.com/solo", "solo123456")

        assert db.get_clusters(min_corroboration=2, limit=20) == []
        assert len(db.get_clusters(min_corroboration=1, limit=20)) == 1

    def test_get_cluster_articles_returns_all_members(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        for i in range(3):
            self._create(db, f"Same event from source {i}", f"source_{i}", f"http://example.com/member/{i}", "cluster99999")

        articles = db.get_cluster_articles("cluster99999")
        assert len(articles) == 3
        assert {a["url"] for a in articles} == {f"http://example.com/member/{i}" for i in range(3)}

    def test_get_cluster_articles_empty_for_unknown(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        assert db.get_cluster_articles("nonexistent") == []

    def test_get_recent_articles_respects_window(self, tmp_db_path):
        import sqlite3
        from contextlib import closing

        db = PersistentDatabase(tmp_db_path)
        self._create(db, "Recent article", "coindesk_rss", "http://example.com/recent", "recent12345")

        # Backdate one article beyond the window
        with closing(sqlite3.connect(tmp_db_path)) as conn:
            conn.execute(
                "INSERT INTO articles (title, content, source, url, category, created_at, updated_at, article_cluster_id) "
                "VALUES ('Old article', 'content', 'coindesk_rss', 'http://example.com/old', 'crypto', "
                "datetime('now', '-2 days'), datetime('now', '-2 days'), 'old12345678')"
            )
            conn.commit()

        recent = db.get_recent_articles(hours=12)
        titles = {a["title"] for a in recent}
        assert "Recent article" in titles
        assert "Old article" not in titles
