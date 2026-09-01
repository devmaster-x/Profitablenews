"""Tests for backtesting (Phase 3, Tasks 3.2-3.6).

All price data comes from a FakeFetcher — tests never hit the CoinGecko API.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from news_scraper import timeutil
from news_scraper.asset_extractor import AssetExtractor
from news_scraper.backtester import Backtester
from news_scraper.models import NewsArticleCreate, NewsCategory
from news_scraper.persistent_database import PersistentDatabase
from news_scraper.price_fetcher import PriceFetcher


# ------------------------------------------------------------------
# Asset extraction
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def extractor():
    return AssetExtractor()


class TestAssetExtraction:
    def test_extracts_major_assets(self, extractor):
        assets = extractor.extract_assets("Bitcoin ETF approved, Ethereum surges", "", [])
        symbols = {a["symbol"] for a in assets}
        assert "BTC" in symbols
        assert "ETH" in symbols

    def test_dedups_by_symbol(self, extractor):
        assets = extractor.extract_assets("Bitcoin BTC rally continues", "", [])
        assert sum(1 for a in assets if a["symbol"] == "BTC") == 1

    def test_limit_three_assets(self, extractor):
        assets = extractor.extract_assets(
            "Bitcoin ethereum solana cardano dogecoin all rally", "", []
        )
        assert len(assets) <= 3

    def test_common_words_not_matched(self, extractor):
        # 'link', 'near', 'dot', 'atom' must NOT produce false assets
        assets = extractor.extract_assets(
            "Check the link near the dot com era atom", "", []
        )
        assert assets == []

    def test_stock_detection(self, extractor):
        assets = extractor.extract_assets("Coinbase reports earnings, MicroStrategy buys more", "", [])
        symbols = {a["symbol"] for a in assets}
        assert "COIN" in symbols
        assert "MSTR" in symbols
        assert all(a["type"] == "stock" for a in assets)

    def test_keywords_take_priority(self, extractor):
        assets = extractor.extract_assets("Market update", "", ["ethereum"])
        assert assets[0]["symbol"] == "ETH"

    def test_nothing_found(self, extractor):
        assert extractor.extract_assets("Local weather forecast", "", []) == []


# ------------------------------------------------------------------
# Price fetcher pure helpers (no network)
# ------------------------------------------------------------------

class TestPriceHelpers:
    def test_price_at_closest_point(self):
        series = [(1_000_000, 10.0), (4_600_000, 20.0), (8_200_000, 30.0)]
        # timestamps in seconds: 1000, 4600, 8200
        assert PriceFetcher.price_at(series, 1100) == 10.0
        assert PriceFetcher.price_at(series, 5000) == 20.0
        assert PriceFetcher.price_at(series, 99999) == 30.0

    def test_price_at_empty_series(self):
        assert PriceFetcher.price_at([], 12345) is None

    def test_pct_change(self):
        assert PriceFetcher.pct_change(100.0, 110.0) == pytest.approx(10.0)
        assert PriceFetcher.pct_change(100.0, 90.0) == pytest.approx(-10.0)
        assert PriceFetcher.pct_change(None, 100.0) is None
        assert PriceFetcher.pct_change(0.0, 100.0) is None


# ------------------------------------------------------------------
# Backtester with a fake fetcher
# ------------------------------------------------------------------

class FakeFetcher:
    """Deterministic series: starts at 100 at from_ts, +1.0 per hour."""

    def __init__(self):
        self.calls = []

    def get_market_chart_range(self, coingecko_id, from_ts, to_ts):
        self.calls.append(coingecko_id)
        hours = (to_ts - from_ts) // 3600 + 1
        return [((from_ts + h * 3600) * 1000, 100.0 + h) for h in range(hours)]

    @staticmethod
    def price_at(series, timestamp):
        return PriceFetcher.price_at(series, timestamp)

    @staticmethod
    def pct_change(a, b):
        return PriceFetcher.pct_change(a, b)


@pytest.fixture()
def tmp_db(tmp_db_path, monkeypatch):
    """Backtester wired to a temp DB (module-level db reference patched)."""
    db = PersistentDatabase(tmp_db_path)
    monkeypatch.setattr("news_scraper.backtester.db", db)
    return db


def _btc_article(db, url="http://example.com/btc", title="Bitcoin ETF approved by SEC"):
    return db.create_article(NewsArticleCreate(
        title=title,
        content="SEC approves the spot bitcoin ETF",
        source="coindesk_rss",
        url=url,
        category=NewsCategory.CRYPTO,
        profit_score=9.0,
        keywords=["bitcoin", "etf"],
    ))


class TestBacktester:
    def test_backtest_article_stores_result(self, tmp_db):
        article = _btc_article(tmp_db)
        article_dict = tmp_db.get_articles_in_timerange(
            datetime.utcnow() - timedelta(hours=1), datetime.utcnow() + timedelta(hours=1)
        )[0]
        fetcher = FakeFetcher()
        backtester = Backtester(fetcher=fetcher)

        # BTC series must cover the same publish->7d range as the asset series,
        # otherwise price_at clamps far-window lookups to the series end.
        # parse_dt mirrors the backtester: DB rows are naive-UTC, and a bare
        # .timestamp() would skew the range by the server's UTC offset.
        publish_ts = int(timeutil.parse_dt(article_dict["created_at"]).timestamp())
        btc_series = fetcher.get_market_chart_range(
            "bitcoin",
            publish_ts - 3600,
            publish_ts + 7 * 24 * 3600 + 3600,
        )
        fetcher.calls.clear()  # discount the test's own BTC setup fetch
        stored = asyncio.run(backtester.backtest_article(article_dict, btc_series))

        assert stored == 1
        assert fetcher.calls == ["bitcoin"]  # asset series fetched exactly once

        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(tmp_db.db_path)) as conn:
            row = conn.execute(
                "SELECT asset_symbol, predicted_score, price_at_publish, price_1h, price_24h, price_7d,"
                " pct_change_1h, pct_change_24h, pct_change_7d,"
                " btc_pct_change_24h FROM backtest_results WHERE article_id = ?",
                (article.id,),
            ).fetchone()

        assert row[0] == "BTC"
        assert row[1] == 9.0
        # Fake series: publish=101, +1h=102, +24h=125, +7d=269
        assert row[2] == 101.0
        assert row[3] == 102.0
        assert row[4] == 125.0
        assert row[5] == 269.0
        assert row[6] == pytest.approx((102 - 101) / 101 * 100)
        assert row[7] == pytest.approx((125 - 101) / 101 * 100)
        assert row[8] == pytest.approx((269 - 101) / 101 * 100)
        assert row[9] == pytest.approx(row[7])  # btc moves identically in the fake

    def test_backtest_is_idempotent(self, tmp_db):
        article = _btc_article(tmp_db)
        article_dict = tmp_db.get_articles_in_timerange(
            datetime.utcnow() - timedelta(hours=1), datetime.utcnow() + timedelta(hours=1)
        )[0]
        fetcher = FakeFetcher()
        backtester = Backtester(fetcher=fetcher)

        btc_series = fetcher.get_market_chart_range("bitcoin", 0, 1)
        asyncio.run(backtester.backtest_article(article_dict, btc_series))
        asyncio.run(backtester.backtest_article(article_dict, btc_series))

        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(tmp_db.db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM backtest_results WHERE article_id = ?", (article.id,)
            ).fetchone()[0]
        assert count == 1

    def test_article_without_assets_skipped(self, tmp_db):
        tmp_db.create_article(NewsArticleCreate(
            title="Local council meeting notes", content="nothing financial",
            source="coindesk_rss", url="http://example.com/none",
            category=NewsCategory.GENERAL, profit_score=5.0, keywords=[],
        ))
        article_dict = tmp_db.get_articles_in_timerange(
            datetime.utcnow() - timedelta(hours=1), datetime.utcnow() + timedelta(hours=1)
        )[0]
        backtester = Backtester(fetcher=FakeFetcher())
        assert asyncio.run(backtester.backtest_article(article_dict, [])) == 0

    def test_stock_assets_skipped_for_now(self, tmp_db):
        tmp_db.create_article(NewsArticleCreate(
            title="Coinbase reports strong earnings", content="COIN stock rises",
            source="coindesk_rss", url="http://example.com/stock",
            category=NewsCategory.CRYPTO, profit_score=8.0, keywords=["coinbase"],
        ))
        article_dict = tmp_db.get_articles_in_timerange(
            datetime.utcnow() - timedelta(hours=1), datetime.utcnow() + timedelta(hours=1)
        )[0]
        backtester = Backtester(fetcher=FakeFetcher())
        assert asyncio.run(backtester.backtest_article(article_dict, [])) == 0

    def test_batch_shares_one_btc_fetch(self, tmp_db):
        for i in range(3):
            # distinct titles/urls so exact-dup does not reject them
            _btc_article(tmp_db, url=f"http://example.com/btc/{i}", title=f"Bitcoin ETF approved by SEC ({i})")
        fetcher = FakeFetcher()
        backtester = Backtester(fetcher=fetcher)

        result = asyncio.run(backtester.backtest_batch(hours_ago=0))

        assert result["articles"] == 3
        assert result["results_stored"] == 3
        # 1 BTC reference fetch + 1 asset fetch per article
        assert fetcher.calls.count("bitcoin") == 1 + 3

    def test_scheduled_job_sweeps_full_day_window(self, monkeypatch):
        """The daily jobs must pass backtest_window_hours (24) so consecutive
        days tile with no gaps — the 1h default once left 23/24 of each day's
        articles permanently un-backtested, starving the Gate C forward test."""
        from news_scraper import backtester as backtester_module
        from news_scraper.config import settings
        from news_scraper.scheduler import NewsScrapingScheduler

        calls = []

        async def fake_batch(hours_ago, window_hours=1, skip_existing=False):
            calls.append({"hours_ago": hours_ago, "window_hours": window_hours})
            return {"articles": 0, "results_stored": 0}

        monkeypatch.setattr(backtester_module.backtester, "backtest_batch", fake_batch)
        scheduler = NewsScrapingScheduler()
        scheduler._run_backtest_job(hours_ago=24)
        scheduler._run_backtest_job(hours_ago=168)

        assert settings.backtest_window_hours == 24
        assert calls == [
            {"hours_ago": 24, "window_hours": 24},
            {"hours_ago": 168, "window_hours": 24},
        ]


# ------------------------------------------------------------------
# Analytics queries (seeded data)
# ------------------------------------------------------------------

def _seed_accuracy_rows(db, n=12):
    """Monotonic data: predicted i -> excess i (perfect rank correlation)."""
    for i in range(n):
        article = db.create_article(NewsArticleCreate(
            title=f"Seeded article {i}", content="content", source="coindesk_rss",
            url=f"http://example.com/seed/{i}", category=NewsCategory.CRYPTO,
            profit_score=5.0, keywords=["etf"],
        ))
        db.store_backtest_result({
            "article_id": article.id, "asset_symbol": "BTC", "asset_type": "crypto",
            "predicted_score": float(i),
            "price_at_publish": 100, "price_1h": 100, "price_24h": 100 + 2 * i, "price_7d": 100,
            "pct_change_1h": 0.0, "pct_change_24h": float(2 * i), "pct_change_7d": 0.0,
            "btc_pct_change_1h": 0.0, "btc_pct_change_24h": float(i), "btc_pct_change_7d": 0.0,
            "backtested_at": datetime.utcnow(), "data_source": "test",
        })


class TestAnalytics:
    def test_accuracy_min_samples_gate(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        _seed_accuracy_rows(db, n=3)
        stats = db.get_backtest_accuracy("24h", min_samples=10)
        assert stats["error"] == "Insufficient data"
        assert stats["total_samples"] == 3

    def test_accuracy_uses_excess_returns(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        _seed_accuracy_rows(db, n=12)
        stats = db.get_backtest_accuracy("24h", min_samples=10)

        # excess = pct(2i) - btc(i) = i; predicted = i -> perfect correlation
        assert stats["correlation"] == pytest.approx(1.0, abs=1e-9)
        assert stats["avg_actual"] == pytest.approx(5.5)  # mean(0..11)
        assert stats["error"] if "error" in stats else True

    def test_score_buckets_cover_all_ranges(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        _seed_accuracy_rows(db, n=12)
        stats = db.get_backtest_accuracy("24h", min_samples=10)
        buckets = stats["score_buckets"]
        assert buckets["0-2"]["count"] == 2   # scores 0, 1
        assert buckets["8-10"]["count"] == 4  # scores 8, 9, 10, 11
        assert buckets["8-10"]["avg_movement"] > buckets["0-2"]["avg_movement"]

    def test_keyword_performance_uses_json_keywords(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        _seed_accuracy_rows(db, n=6)  # all carry keyword 'etf'
        rows = db.get_keyword_performance(limit=10)

        assert len(rows) == 1
        assert rows[0]["keyword"] == "etf"
        assert rows[0]["appearances"] == 6
        # mean excess for i in 0..5 = mean(i) = 2.5
        assert rows[0]["avg_24h_excess_movement"] == pytest.approx(2.5)

    def test_source_accuracy(self, tmp_db_path):
        db = PersistentDatabase(tmp_db_path)
        _seed_accuracy_rows(db, n=6)
        rows = db.get_source_accuracy()

        assert len(rows) == 1
        assert rows[0]["source"] == "coindesk_rss"
        assert rows[0]["total_articles"] == 6
