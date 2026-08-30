"""Trending-asset aggregation for the trading integration (Track C signal).

Pure functions: articles in, ranked assets out. The rank is a recency-weighted
sum of article scores — each article contributes ``profit_score × 0.5^(age_hours
/ half_life_hours)`` to every asset it mentions, so a burst of fresh, high-score
news dominates a trickle of stale mentions. Parameters travel with the response
so consumers can audit the ranking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from news_scraper import timeutil
from news_scraper.asset_extractor import asset_extractor

MAX_ARTICLE_IDS_PER_ASSET = 10


def aggregate_trending(
    articles: List[Dict[str, Any]],
    now: datetime,
    half_life_hours: float,
) -> List[Dict[str, Any]]:
    """Aggregate extracted assets across articles into a ranked list."""
    if half_life_hours <= 0:
        raise ValueError(f"half_life_hours must be > 0, got {half_life_hours}")

    by_symbol: Dict[str, Dict[str, Any]] = {}
    for article in articles:
        assets = asset_extractor.extract_assets(
            article.get("title") or "",
            article.get("content") or "",
            article.get("keywords") or [],
        )
        if not assets:
            continue

        score = float(article.get("profit_score") or 0.0)
        created_at = timeutil.parse_dt(article.get("created_at"))
        age_hours = max(0.0, (timeutil.parse_dt(now) - created_at).total_seconds() / 3600.0)
        weight = score * (0.5 ** (age_hours / half_life_hours))

        for asset in assets:
            entry = by_symbol.get(asset["symbol"])
            if entry is None:
                entry = {
                    "symbol": asset["symbol"],
                    "type": asset["type"],
                    "coingecko_id": asset.get("coingecko_id"),
                    "article_count": 0,
                    "max_score": 0.0,
                    "score_sum": 0.0,
                    "rank_score": 0.0,
                    "latest_article_at": None,
                    "article_ids": [],
                }
                by_symbol[asset["symbol"]] = entry

            entry["article_count"] += 1
            entry["max_score"] = max(entry["max_score"], score)
            entry["score_sum"] += score
            entry["rank_score"] += weight
            iso = created_at.isoformat()
            if entry["latest_article_at"] is None or iso > entry["latest_article_at"]:
                entry["latest_article_at"] = iso
            if article.get("id") is not None and len(entry["article_ids"]) < MAX_ARTICLE_IDS_PER_ASSET:
                entry["article_ids"].append(article["id"])

    ranked = []
    for entry in by_symbol.values():
        entry["avg_score"] = round(entry["score_sum"] / entry["article_count"], 3)
        entry["rank_score"] = round(entry["rank_score"], 4)
        entry["max_score"] = round(entry["max_score"], 3)
        del entry["score_sum"]
        ranked.append(entry)

    ranked.sort(key=lambda e: (-e["rank_score"], -e["article_count"], e["symbol"]))
    return ranked
