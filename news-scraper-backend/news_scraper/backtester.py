"""Backtesting engine (Phase 3, Task 3.4): validate predicted scores against
actual price movements after publication.

For each article, extracts tradeable assets, fetches one price series per
asset (publish→7d), and stores pct changes at +1h/+24h/+7d alongside the BTC
reference changes so validation can use excess returns.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Dict, Optional

from news_scraper import timeutil
from news_scraper.database import db
from news_scraper.asset_extractor import asset_extractor
from news_scraper.price_fetcher import price_fetcher, PriceFetcher, PriceSeries, BTC_COINGECKO_ID

logger = logging.getLogger(__name__)


class Backtester:
    def __init__(self, fetcher: Optional[PriceFetcher] = None):
        self.windows_hours = [1, 24, 168]  # 1h, 24h, 7d
        # Injectable for tests; production uses the module-level singleton
        self.fetcher = fetcher or price_fetcher

    async def backtest_article(self, article: Dict, btc_series: Optional[PriceSeries] = None) -> int:
        """Backtest one article against its assets. Returns results stored."""
        if not article.get("created_at"):
            logger.warning(f"Article {article.get('id')} has no created_at; skipping")
            return 0

        assets = asset_extractor.extract_assets(
            article["title"], article.get("content") or "", article.get("keywords") or []
        )
        if not assets:
            logger.debug(f"No tradeable assets in article {article['id']}")
            return 0

        # parse_dt: DB rows come back as naive-UTC datetimes; calling .timestamp()
        # on those interprets them in SERVER LOCAL time and skews every price
        # lookup by the UTC offset. Normalize to aware-UTC first.
        publish_ts = int(timeutil.parse_dt(article["created_at"]).timestamp())
        from_ts = publish_ts - 3600
        to_ts = publish_ts + 7 * 24 * 3600 + 3600

        stored = 0
        for asset in assets:
            if asset["type"] != "crypto":
                continue  # crypto only for now; stocks need a different API

            series = self.fetcher.get_market_chart_range(asset["coingecko_id"], from_ts, to_ts)
            price_at_publish = self.fetcher.price_at(series, publish_ts)
            if price_at_publish is None:
                logger.warning(f"No publish-time price for {asset['coingecko_id']} (article {article['id']})")
                continue

            prices = {
                hours: self.fetcher.price_at(series, publish_ts + hours * 3600)
                for hours in self.windows_hours
            }
            btc_changes = self._btc_changes(btc_series, publish_ts)

            db.store_backtest_result({
                "article_id": article["id"],
                "asset_symbol": asset["symbol"],
                "asset_type": asset["type"],
                "predicted_score": article.get("profit_score") or 0.0,
                "price_at_publish": price_at_publish,
                "price_1h": prices[1],
                "price_24h": prices[24],
                "price_7d": prices[168],
                "pct_change_1h": self.fetcher.pct_change(price_at_publish, prices[1]),
                "pct_change_24h": self.fetcher.pct_change(price_at_publish, prices[24]),
                "pct_change_7d": self.fetcher.pct_change(price_at_publish, prices[168]),
                "btc_pct_change_1h": btc_changes[1],
                "btc_pct_change_24h": btc_changes[24],
                "btc_pct_change_7d": btc_changes[168],
                "backtested_at": timeutil.utcnow(),
                "data_source": "coingecko",
            })
            stored += 1
            pct_24h = self.fetcher.pct_change(price_at_publish, prices[24])
            pct_str = f"{pct_24h:+.2f}%" if pct_24h is not None else "n/a"
            logger.info(f"✓ Backtested article {article['id']} | {asset['symbol']} 24h: {pct_str}")

        return stored

    def _btc_changes(self, btc_series: Optional[PriceSeries], publish_ts: int) -> Dict[int, Optional[float]]:
        if not btc_series:
            return {hours: None for hours in self.windows_hours}
        btc_at_publish = self.fetcher.price_at(btc_series, publish_ts)
        return {
            hours: self.fetcher.pct_change(
                btc_at_publish, self.fetcher.price_at(btc_series, publish_ts + hours * 3600)
            )
            for hours in self.windows_hours
        }

    async def backtest_batch(
        self, hours_ago: int = 24, window_hours: int = 1, skip_existing: bool = False
    ) -> Dict:
        """Backtest articles published in [now-hours_ago-window, now-hours_ago).

        The scheduled jobs keep the historical 1h window; manual/backfill runs
        widen ``window_hours`` to sweep longer ranges. ``skip_existing`` makes
        re-runs cheap: articles that already have any backtest result are not
        re-fetched (results are idempotent per (article, asset) anyway).
        """
        now = timeutil.utcnow()
        cutoff_end = now - timedelta(hours=hours_ago)
        cutoff_start = cutoff_end - timedelta(hours=window_hours)

        articles = db.get_articles_in_timerange(cutoff_start, cutoff_end)
        skipped_existing = 0
        if skip_existing:
            fresh = [a for a in articles if not db.has_backtest_results(a["id"])]
            skipped_existing = len(articles) - len(fresh)
            articles = fresh
        logger.info(
            f"Backtesting {len(articles)} articles from window "
            f"[{cutoff_start.isoformat()}, {cutoff_end.isoformat()}) "
            f"(skipped {skipped_existing} already-backtested)"
        )

        # BTC reference series fetched ONCE per batch and shared across articles
        btc_series: PriceSeries = []
        if articles:
            earliest = min(
                timeutil.parse_dt(a["created_at"]) for a in articles if a["created_at"]
            )
            from_ts = int(earliest.timestamp()) - 3600
            to_ts = int(now.timestamp()) + 3600
            btc_series = self.fetcher.get_market_chart_range(BTC_COINGECKO_ID, from_ts, to_ts)

        stored = 0
        for article in articles:
            try:
                stored += await self.backtest_article(article, btc_series)
            except Exception as e:
                logger.error(f"Backtest failed for article {article.get('id')}: {e}")
            await asyncio.sleep(0.1)  # gentle pacing between articles

        result = {
            "articles": len(articles),
            "results_stored": stored,
            "skipped_existing": skipped_existing,
            "hours_ago": hours_ago,
            "window_hours": window_hours,
        }
        logger.info(f"Backtest batch completed: {result}")
        return result


backtester = Backtester()
