"""One-time data-hygiene fix (DECISIONS.md 2026-09-20 / trading_system repo):
423 of 842 backtested articles predate the 2026-08-29 desaturation fix in
scoring.py and sit at a constant ~9-10 ceiling score, drowning out Track C's
correlation signal. Re-runs the CURRENT ProfitScorer over every pre-fix
article's stored title/content/category (unchanged, no data loss) and updates:

  1. articles.profit_score           - the source of truth, for any future use
  2. backtest_results.predicted_score - what get_backtest_accuracy() actually
                                         reads; this is the value that matters
                                         for today's correlation number

Price/pct_change columns in backtest_results are untouched - only the
predicted_score input is being corrected, not the measured market outcome.

Usage: python rescore_stale_articles.py [--dry-run]
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from statistics import mean, median

from news_scraper.models import NewsCategory
from news_scraper.scoring import ProfitScorer

DB_PATH = "news_scraper.db"
CUTOFF = "2026-08-29"  # same boundary DECISIONS.md 2026-09-20 verified as 423/842


def backup_db() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = f"news_scraper_backup_pre_rescore_{stamp}.db"
    with closing(sqlite3.connect(DB_PATH)) as src, closing(sqlite3.connect(dest)) as dst:
        src.backup(dst)  # consistent hot-backup, no need to stop the live api process
    return dest


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    backup_path = backup_db()
    print(f"Backup written: {backup_path}")

    scorer = ProfitScorer()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 5000")  # wait, don't error, if the live api holds a lock
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, content, category, profit_score FROM articles WHERE created_at < ?",
        (CUTOFF,),
    )
    rows = cursor.fetchall()
    print(f"Pre-fix articles found: {len(rows)}")

    old_scores, new_scores = [], []
    updated_articles = 0
    updated_backtest_rows = 0
    now = datetime.now(timezone.utc).isoformat()

    for article_id, title, content, category_raw, old_score in rows:
        try:
            category = NewsCategory(category_raw)
        except ValueError:
            category = NewsCategory.GENERAL

        new_score = scorer.calculate_profit_score(title or "", content or "", category)
        old_scores.append(old_score if old_score is not None else 0.0)
        new_scores.append(new_score)

        if dry_run:
            continue

        cursor.execute(
            "UPDATE articles SET profit_score = ?, updated_at = ? WHERE id = ?",
            (new_score, now, article_id),
        )
        updated_articles += cursor.rowcount

        cursor.execute(
            "UPDATE backtest_results SET predicted_score = ? WHERE article_id = ?",
            (new_score, article_id),
        )
        updated_backtest_rows += cursor.rowcount

    if dry_run:
        conn.rollback()
        print("DRY RUN -- no writes committed.")
    else:
        conn.commit()
        print(f"Committed: {updated_articles} articles, {updated_backtest_rows} backtest_results rows.")

    conn.close()

    print()
    print(f"profit_score  before -> after   (n={len(old_scores)})")
    print(f"  mean:   {mean(old_scores):.2f} -> {mean(new_scores):.2f}")
    print(f"  median: {median(old_scores):.2f} -> {median(new_scores):.2f}")


if __name__ == "__main__":
    main()
