"""One-shot backtest backfill over article history.

Usage (from news-scraper-backend/):

    poetry run python -m news_scraper.backfill --days 35 --chunk-hours 24

Sweeps [now - days, now - min-age) in chunk-sized windows, oldest first, calling
the normal batch backtester (idempotent per (article, asset) — safe to re-run).
Articles younger than ``--min-age-hours`` are skipped: their +24h/+7d outcomes
don't exist yet. Progress and totals log to stdout; results land in
``backtest_results`` and are read via GET /backtest/accuracy.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from news_scraper.backtester import backtester


async def backfill(days: int, chunk_hours: int, min_age_hours: int) -> dict:
    total_articles = 0
    total_stored = 0
    chunks = 0

    hours_ago = min_age_hours
    end_hours = days * 24
    while hours_ago < end_hours:
        window = min(chunk_hours, end_hours - hours_ago)
        # Window end is `hours_ago` before now; sweep proceeds into the past.
        result = await backtester.backtest_batch(
            hours_ago=hours_ago, window_hours=window, skip_existing=True
        )
        total_articles += result["articles"]
        total_stored += result["results_stored"]
        chunks += 1
        logging.info(
            "backfill progress chunk=%s hours_ago=%s window=%s articles=%s stored=%s totals=%s/%s",
            chunks, hours_ago, window, result["articles"], result["results_stored"],
            total_articles, total_stored,
        )
        hours_ago += window

    summary = {"chunks": chunks, "articles": total_articles, "results_stored": total_stored, "days": days}
    logging.info("backfill complete %s", summary)
    return summary


def main() -> int:
    # Windows consoles default to cp1252; the backtester logs '✓' glyphs which
    # would otherwise raise UnicodeEncodeError inside the logging machinery.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        force=True,
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("news_scraper").setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description="Backfill backtest results over article history")
    parser.add_argument("--days", type=int, default=35, help="How far back to sweep")
    parser.add_argument("--chunk-hours", type=int, default=24, help="Window width per batch")
    parser.add_argument(
        "--min-age-hours", type=int, default=24,
        help=(
            "Skip articles younger than this. 24 (default) captures 1h/24h outcomes "
            "immediately; the daily 7d scheduled job re-stores each row once its 7d "
            "outcome exists, so partial rows self-complete. Use 168 to only store "
            "rows that are already 7d-complete."
        ),
    )
    args = parser.parse_args()

    if args.days * 24 <= args.min_age_hours:
        logging.error(
            "nothing to do: --days %s (%sh) is entirely inside --min-age-hours %s — "
            "raise --days or lower --min-age-hours",
            args.days, args.days * 24, args.min_age_hours,
        )
        return 1

    summary = asyncio.run(backfill(args.days, args.chunk_hours, args.min_age_hours))
    return 0 if summary["chunks"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
