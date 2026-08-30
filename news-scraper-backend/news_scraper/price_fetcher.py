"""CoinGecko price fetching (Phase 3, Task 3.3).

Design notes:
- Uses plain `requests` against the CoinGecko REST API instead of the
  `pycoingecko` wrapper: one less dependency, direct control over error
  handling. Free tier needs no API key.
- Fetches ONE market-chart series per asset covering publish→7d, instead of 4
  separate point-in-time calls. Hourly granularity (free tier, ranges <=90d)
  is sufficient for 1h/24h/7d change windows. This cuts API calls ~4x.
- BTC reference series is fetched once per backtest batch and shared.
"""

import logging
import time
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
BTC_COINGECKO_ID = "bitcoin"

# A price point: (unix_ms, usd_price)
PriceSeries = List[Tuple[int, float]]


class PriceFetcher:
    def __init__(self, rate_limit_delay: float = 6.0, timeout: int = 15, max_429_retries: int = 3):
        # Measured 2026-08-29: 1.5s pacing produced 314 HTTP 429s over a 60-day
        # backfill — the free tier's practical unauthenticated budget is closer
        # to ~10 calls/min. 6s pacing + explicit 429 backoff keeps long sweeps
        # slow but lossless.
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_429_retries = max_429_retries

    def _get(self, path: str, params: dict) -> Optional[dict]:
        try:
            for attempt in range(self.max_429_retries + 1):
                try:
                    response = requests.get(
                        f"{COINGECKO_BASE}{path}", params=params, timeout=self.timeout
                    )
                    if response.status_code == 429 and attempt < self.max_429_retries:
                        retry_after = response.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after else 30.0 * (attempt + 1)
                        logger.warning(
                            f"CoinGecko 429 on {path}; backing off {wait:.0f}s "
                            f"(attempt {attempt + 1}/{self.max_429_retries})"
                        )
                        time.sleep(wait)
                        continue
                    response.raise_for_status()
                    return response.json()
                except requests.RequestException as e:
                    logger.error(f"CoinGecko request failed ({path}): {e}")
                    return None
            return None
        finally:
            time.sleep(self.rate_limit_delay)

    def get_market_chart_range(self, coingecko_id: str, from_ts: int, to_ts: int) -> PriceSeries:
        """[(unix_ms, price)] series for [from_ts, to_ts] (unix seconds); [] on failure."""
        data = self._get(f"/coins/{coingecko_id}/market_chart/range", {
            "vs_currency": "usd",
            "from": from_ts,
            "to": to_ts,
        })
        if not data or "prices" not in data or not data["prices"]:
            logger.warning(f"No price data for {coingecko_id} in range {from_ts}-{to_ts}")
            return []
        return data["prices"]

    @staticmethod
    def price_at(series: PriceSeries, timestamp: int) -> Optional[float]:
        """Closest price point to a unix timestamp (seconds)."""
        if not series:
            return None
        closest = min(series, key=lambda point: abs(point[0] / 1000 - timestamp))
        return closest[1]

    @staticmethod
    def pct_change(from_price: Optional[float], to_price: Optional[float]) -> Optional[float]:
        if from_price is None or to_price is None or from_price == 0:
            return None
        return (to_price - from_price) / from_price * 100.0


price_fetcher = PriceFetcher()
