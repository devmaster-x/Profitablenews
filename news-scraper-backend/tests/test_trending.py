"""Tests for trending-asset aggregation (Track C signal for the trading system)."""

from datetime import timedelta

import pytest

from news_scraper import timeutil
from news_scraper.trending import aggregate_trending


NOW = timeutil.utcnow()


def article(id_, title, score, hours_old, content="", keywords=None):
    return {
        "id": id_,
        "title": title,
        "content": content,
        "keywords": keywords or [],
        "profit_score": score,
        "created_at": NOW - timedelta(hours=hours_old),
    }


class TestAggregateTrending:
    def test_extracts_and_ranks_assets(self):
        articles = [
            article(1, "Bitcoin ETF sees record inflows", 8.0, 1),
            article(2, "Bitcoin miners expand capacity", 6.0, 2),
            article(3, "Solana network upgrade ships", 7.0, 1),
        ]
        ranked = aggregate_trending(articles, NOW, half_life_hours=2.0)
        symbols = [r["symbol"] for r in ranked]
        assert "BTC" in symbols and "SOL" in symbols
        btc = next(r for r in ranked if r["symbol"] == "BTC")
        assert btc["article_count"] == 2
        assert btc["max_score"] == 8.0
        assert btc["avg_score"] == 7.0
        assert btc["article_ids"] == [1, 2]
        assert ranked[0]["symbol"] == "BTC"  # two articles outrank one

    def test_recency_weighting_prefers_fresh_news(self):
        articles = [
            article(1, "Solana hits new highs", 8.0, 0.5),   # fresh
            article(2, "Ethereum staking report", 8.0, 12),  # stale, same score
        ]
        ranked = aggregate_trending(articles, NOW, half_life_hours=2.0)
        sol = next(r for r in ranked if r["symbol"] == "SOL")
        eth = next(r for r in ranked if r["symbol"] == "ETH")
        assert sol["rank_score"] > eth["rank_score"]
        # 12h old at 2h half-life = 1/64 weight — fresh news dominates
        assert eth["rank_score"] < sol["rank_score"] / 10

    def test_articles_without_assets_are_ignored(self):
        articles = [article(1, "Generic tech industry roundup", 9.0, 1)]
        assert aggregate_trending(articles, NOW, half_life_hours=2.0) == []

    def test_keywords_priority_matches_extractor(self):
        articles = [article(1, "Layer 1 news roundup", 5.0, 1, keywords=["bitcoin"])]
        ranked = aggregate_trending(articles, NOW, half_life_hours=2.0)
        assert ranked and ranked[0]["symbol"] == "BTC"
        assert ranked[0]["coingecko_id"] == "bitcoin"

    def test_invalid_half_life_rejected(self):
        with pytest.raises(ValueError):
            aggregate_trending([], NOW, half_life_hours=0)

    def test_naive_created_at_treated_as_utc(self):
        # DB rows come back naive-UTC; aggregation must not skew by local offset.
        naive = (NOW - timedelta(hours=1)).replace(tzinfo=None)
        articles = [
            {"id": 1, "title": "Bitcoin update", "content": "", "keywords": [],
             "profit_score": 8.0, "created_at": naive},
        ]
        ranked = aggregate_trending(articles, NOW, half_life_hours=2.0)
        # weight for a 1h-old article at 2h half-life = 8 * 0.5^0.5 ≈ 5.66
        assert ranked[0]["rank_score"] == pytest.approx(8.0 * 0.5 ** 0.5, rel=1e-3)
