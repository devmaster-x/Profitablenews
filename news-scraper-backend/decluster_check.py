"""De-clustered Gate-C check: collapse articles that share one market outcome.

Rows with the same (asset, excess-return) are one market event covered by many
articles; treating each article as independent inflates N and shrinks p.
Collapse each cluster to its mean predicted score, then re-run Spearman.
"""
import sqlite3

import numpy as np
from scipy.stats import spearmanr

conn = sqlite3.connect("news_scraper.db")
for w in ("1h", "24h", "7d"):
    col, btc = f"pct_change_{w}", f"btc_pct_change_{w}"
    rows = conn.execute(
        f"SELECT predicted_score, asset_symbol, ROUND({col}-{btc},3) "
        f"FROM backtest_results WHERE {col} IS NOT NULL AND {btc} IS NOT NULL"
    ).fetchall()
    clusters: dict = {}
    for score, sym, ex in rows:
        clusters.setdefault((sym, ex), []).append(score)
    xs = [float(np.mean(v)) for v in clusters.values()]
    ys = [k[1] for k in clusters.keys()]
    c, p = spearmanr(xs, ys)
    print(f"{w}: raw_n={len(rows)} clusters={len(clusters)} rho={c:.4f} p={p:.4f}", flush=True)
