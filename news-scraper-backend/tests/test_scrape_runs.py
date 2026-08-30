"""Tests for the scrape_runs audit table (Track C observability)."""

from news_scraper import timeutil
from news_scraper.persistent_database import PersistentDatabase


class TestScrapeRunAudit:
    def test_record_and_read_back(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        started = timeutil.utcnow()
        db.record_scrape_run({
            "started_at": started,
            "finished_at": started,
            "trigger": "scheduled",
            "status": "ok",
            "scraped_count": 12,
            "stored_count": 9,
            "skipped_duplicates": 3,
            "cluster_assignments": 2,
            "duration_ms": 4321,
            "sources_scraped": ["coindesk_rss", "theblock_rss"],
        })
        runs = db.get_scrape_runs()
        assert len(runs) == 1
        run = runs[0]
        assert run["trigger"] == "scheduled"
        assert run["status"] == "ok"
        assert run["stored_count"] == 9
        assert run["sources_scraped"] == ["coindesk_rss", "theblock_rss"]
        assert run["error"] is None

    def test_error_runs_recorded(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        db.record_scrape_run({
            "started_at": timeutil.utcnow(),
            "trigger": "manual",
            "status": "error",
            "error": "boom",
        })
        runs = db.get_scrape_runs()
        assert runs[0]["status"] == "error"
        assert runs[0]["error"] == "boom"

    def test_newest_first_and_limit(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        for i in range(5):
            db.record_scrape_run({
                "started_at": timeutil.utcnow(),
                "trigger": "manual",
                "status": "ok",
                "scraped_count": i,
            })
        runs = db.get_scrape_runs(limit=3)
        assert len(runs) == 3
        assert runs[0]["scraped_count"] == 4  # newest first
