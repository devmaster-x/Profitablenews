# Track C upgrades — trading-system integration (2026-08-29)

Changes made so this service can act as the news-signal layer ("Track C") for the trading system at
`g:\Work\Business\lastest\trading-system` (see its `docs/REQUIREMENTS.md` §2 and `docs/ROADMAP.md` M8).

## Ollama / LLM status — investigated first

**No Ollama (or any LLM) integration exists in this codebase** — no imports, no `localhost:11434`
references, backend or frontend (checked 2026-08-29; the sibling `g:\Work\Business\news-scraper`
folder is empty). Scoring is keyword/regex + sentiment rules end to end, so the 5-minute cadence is
cheap and safe. If an Ollama scoring stage is added later, it plugs in behind the `ProfitScorer`
interface (`scoring.py`) — and `SCRAPE_INTERVAL_MINUTES` must then be re-tuned to the model's
latency. Do not assume an LLM is in the loop today.

## What changed

1. **`GET /assets/trending`** (new; `api/routers/assets.py` + pure logic in `trending.py`):
   assets extracted from recent articles, ranked by recency-weighted score mass
   (`score × 0.5^(age_h/half_life)`). Params (`hours`, `half_life_hours`, `min_score`, `limit`)
   ride along in the response for auditability. This is the endpoint the trading system polls.
2. **Interval scraping + autostart** (`config.py`, `scheduler.py`, `main.py`):
   `SCRAPE_INTERVAL_MINUTES=5` switches from daily-at-midnight to every-5-minutes;
   `SCHEDULER_AUTOSTART=true` starts the scheduler with the server (no manual POST needed).
   Defaults (0 / false) preserve legacy behavior for tests and embedded hosts.
3. **Score de-saturation** (`scoring.py`): the raw keyword sum is now smoothly compressed
   (`10·raw/(raw+8)`) before the sentiment multiplier. Previously ~40% of articles pinned at
   exactly 10.0 (hard cap before the multiplier), destroying top-of-scale ranking; a naive
   "cap after multiplier" would have let keyword-dense NEGATIVE articles reach 10 — the
   compression avoids both failure modes. Score distribution shifts down overall; the 4.0
   storage threshold now demands a bit more substance. **Historical rows keep their old scores** —
   comparisons across the change date must account for that.
4. **Backtester timezone fix** (`backtester.py`): DB rows return naive-UTC datetimes;
   `.timestamp()` on those skews every price lookup by the server's UTC offset. Now normalized
   through `timeutil.parse_dt`. Also `backtest_batch(hours_ago, window_hours)` sweeps arbitrary
   windows (scheduled jobs keep the legacy 1h).
5. **Backfill runner** (`backfill.py`):
   `poetry run python -m news_scraper.backfill --days 60 --chunk-hours 48` populates
   `backtest_results` over history (idempotent; articles younger than `--min-age-hours` are
   skipped since their outcomes don't exist yet). Read results via `GET /backtest/accuracy`.
6. **Scrape-run auditing** (`persistent_database.py`, `scraper.py`, `api/routers/scrape.py`):
   every scrape run — manual, scheduled, or script — writes one row to the new `scrape_runs`
   table (trigger, status, counts, duration, sources, error). `GET /scrape/status` now returns
   the real last run + recent history instead of a hardcoded `null`.
7. **Scheduler fixes**: `reschedule()` no longer silently deletes the backtest jobs;
   `GET /scheduler/status` reports the true schedule (and no longer claims UTC for a
   local-time scheduler).
8. Lint: fixed the pre-existing bare `except` in `slack_notifier.py`. `ruff check news_scraper`
   is clean; 100/100 tests pass.

## Validation results (2026-08-30, full 60-day backfill — Gate C NOT passed)

Backfill v2 swept 755 articles and stored 264 backtest rows with zero lost fetches (the first
attempt lost 314 calls to CoinGecko 429s at 1.5s pacing — real unauthenticated budget is ~10
calls/min; `price_fetcher` now paces at 6s with Retry-After-aware backoff, and `backfill.py`
skips already-backtested articles).

Per-row Spearman (score ↔ excess return over BTC), `GET /backtest/accuracy`, N=264:

| window | per-row ρ (p) | de-clustered ρ (p), N=45 events | read |
|---|---|---|---|
| 1h | 0.032 (0.61) | 0.062 (0.69) | noise |
| 24h | 0.057 (0.36) | −0.052 (0.73) | noise |
| 7d | 0.185 (0.0025) | **0.261 (0.083)** | suggestive, below the p<0.05 bar |

**The de-clustered column is the honest one.** The 264 rows collapse to 45 independent market
events — articles covering the same asset in the same window inherit the *same* excess return, so
per-row p-values are inflated ~6×. `decluster_check.py` (backend root) collapses each
(asset, excess-return) cluster to its mean predicted score before correlating; `check_accuracy.py`
prints the per-row version. The earlier N=20 preliminary "significant 1h" (ρ=0.474, p=0.035)
disappeared entirely at full N — a small-sample mirage, as its own caveat warned.

Structural caveats on this historical test: avg predicted score is 9.14/10 (the old saturated
scale — nearly every article pinned at the ceiling, so the predictor carried almost no ranking
information), and a positive 7d sign may be reverse causality (assets already rising attract
coverage). The **forward test** is the real one: de-saturated scores from 2026-08-29 onward,
5-minute cadence, de-clustered evaluation at the trading system's Gate review #1 (~2026-09-12).

## Production env (VPS) for the trading integration

```
SCRAPE_INTERVAL_MINUTES=5
SCHEDULER_AUTOSTART=true
```

## Consumption contract (for trading-system's news collector)

Poll `GET /assets/trending?hours=6&half_life_hours=2` and store snapshots with `generated_at`.
Symbols are CoinGecko-keyed (`coingecko_id`), max 3 assets per article, no confidence field —
mapping to venue instruments happens on the trading-system side.
