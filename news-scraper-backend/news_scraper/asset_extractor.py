"""Extract tradeable assets mentioned in an article (Phase 3, Task 3.2).

Maps asset names/tickers found in the article to price-API identifiers.
Ambiguous short tickers that collide with common English words are excluded
('link', 'near', 'dot', 'atom', 'uni', 'apt', 'op', 'fil') — the project name
('chainlink', 'near protocol', ...) is matched instead.
"""

import re
from typing import Dict, List


class AssetExtractor:
    def __init__(self):
        # keyword -> {symbol, type, coingecko_id | yahoo_symbol}
        self.asset_mapping: Dict[str, Dict] = {
            # Layer 1 / major crypto
            'bitcoin': {'symbol': 'BTC', 'type': 'crypto', 'coingecko_id': 'bitcoin'},
            'btc': {'symbol': 'BTC', 'type': 'crypto', 'coingecko_id': 'bitcoin'},
            'ethereum': {'symbol': 'ETH', 'type': 'crypto', 'coingecko_id': 'ethereum'},
            'eth': {'symbol': 'ETH', 'type': 'crypto', 'coingecko_id': 'ethereum'},
            'solana': {'symbol': 'SOL', 'type': 'crypto', 'coingecko_id': 'solana'},
            'sol': {'symbol': 'SOL', 'type': 'crypto', 'coingecko_id': 'solana'},
            'cardano': {'symbol': 'ADA', 'type': 'crypto', 'coingecko_id': 'cardano'},
            'ada': {'symbol': 'ADA', 'type': 'crypto', 'coingecko_id': 'cardano'},
            'ripple': {'symbol': 'XRP', 'type': 'crypto', 'coingecko_id': 'ripple'},
            'xrp': {'symbol': 'XRP', 'type': 'crypto', 'coingecko_id': 'ripple'},
            'dogecoin': {'symbol': 'DOGE', 'type': 'crypto', 'coingecko_id': 'dogecoin'},
            'doge': {'symbol': 'DOGE', 'type': 'crypto', 'coingecko_id': 'dogecoin'},
            'polkadot': {'symbol': 'DOT', 'type': 'crypto', 'coingecko_id': 'polkadot'},
            'avalanche': {'symbol': 'AVAX', 'type': 'crypto', 'coingecko_id': 'avalanche-2'},
            'avax': {'symbol': 'AVAX', 'type': 'crypto', 'coingecko_id': 'avalanche-2'},
            'chainlink': {'symbol': 'LINK', 'type': 'crypto', 'coingecko_id': 'chainlink'},
            'polygon': {'symbol': 'MATIC', 'type': 'crypto', 'coingecko_id': 'matic-network'},
            'matic': {'symbol': 'MATIC', 'type': 'crypto', 'coingecko_id': 'matic-network'},
            'litecoin': {'symbol': 'LTC', 'type': 'crypto', 'coingecko_id': 'litecoin'},
            'ltc': {'symbol': 'LTC', 'type': 'crypto', 'coingecko_id': 'litecoin'},
            'cosmos': {'symbol': 'ATOM', 'type': 'crypto', 'coingecko_id': 'cosmos'},
            'near protocol': {'symbol': 'NEAR', 'type': 'crypto', 'coingecko_id': 'near'},
            'binance coin': {'symbol': 'BNB', 'type': 'crypto', 'coingecko_id': 'binancecoin'},
            'bnb': {'symbol': 'BNB', 'type': 'crypto', 'coingecko_id': 'binancecoin'},
            'tron': {'symbol': 'TRX', 'type': 'crypto', 'coingecko_id': 'tron'},
            'shiba inu': {'symbol': 'SHIB', 'type': 'crypto', 'coingecko_id': 'shiba-inu'},
            'shib': {'symbol': 'SHIB', 'type': 'crypto', 'coingecko_id': 'shiba-inu'},
            'aptos': {'symbol': 'APT', 'type': 'crypto', 'coingecko_id': 'aptos'},
            'sui': {'symbol': 'SUI', 'type': 'crypto', 'coingecko_id': 'sui'},
            'pepe': {'symbol': 'PEPE', 'type': 'crypto', 'coingecko_id': 'pepe'},
            'filecoin': {'symbol': 'FIL', 'type': 'crypto', 'coingecko_id': 'filecoin'},
            # Layer 2
            'arbitrum': {'symbol': 'ARB', 'type': 'crypto', 'coingecko_id': 'arbitrum'},
            'arb': {'symbol': 'ARB', 'type': 'crypto', 'coingecko_id': 'arbitrum'},
            'optimism': {'symbol': 'OP', 'type': 'crypto', 'coingecko_id': 'optimism'},
            # DeFi
            'uniswap': {'symbol': 'UNI', 'type': 'crypto', 'coingecko_id': 'uniswap'},
            'aave': {'symbol': 'AAVE', 'type': 'crypto', 'coingecko_id': 'aave'},
            'maker': {'symbol': 'MKR', 'type': 'crypto', 'coingecko_id': 'maker'},
            'makerdao': {'symbol': 'MKR', 'type': 'crypto', 'coingecko_id': 'maker'},
            'lido': {'symbol': 'LDO', 'type': 'crypto', 'coingecko_id': 'lido-dao'},
            'gmx': {'symbol': 'GMX', 'type': 'crypto', 'coingecko_id': 'gmx'},
            'pendle': {'symbol': 'PENDLE', 'type': 'crypto', 'coingecko_id': 'pendle'},
            'dydx': {'symbol': 'DYDX', 'type': 'crypto', 'coingecko_id': 'dydx-chain'},
            # Base/Arbitrum long tail — the tokens the trading system's Track B
            # DEX collector watches; needed so its news-uplift join can fire on
            # them. Ambiguous bare words (degen, brett, magic, virtual, aero)
            # follow the exclusion policy above and use qualified keywords.
            'aerodrome': {'symbol': 'AERO', 'type': 'crypto', 'coingecko_id': 'aerodrome-finance'},
            'degen token': {'symbol': 'DEGEN', 'type': 'crypto', 'coingecko_id': 'degen-base'},
            'degen chain': {'symbol': 'DEGEN', 'type': 'crypto', 'coingecko_id': 'degen-base'},
            'based brett': {'symbol': 'BRETT', 'type': 'crypto', 'coingecko_id': 'based-brett'},
            'brett token': {'symbol': 'BRETT', 'type': 'crypto', 'coingecko_id': 'based-brett'},
            'toshi': {'symbol': 'TOSHI', 'type': 'crypto', 'coingecko_id': 'toshi'},
            'virtuals protocol': {'symbol': 'VIRTUAL', 'type': 'crypto', 'coingecko_id': 'virtual-protocol'},
            'virtual protocol': {'symbol': 'VIRTUAL', 'type': 'crypto', 'coingecko_id': 'virtual-protocol'},
            'virtuals': {'symbol': 'VIRTUAL', 'type': 'crypto', 'coingecko_id': 'virtual-protocol'},
            'treasure dao': {'symbol': 'MAGIC', 'type': 'crypto', 'coingecko_id': 'magic'},
            'magic token': {'symbol': 'MAGIC', 'type': 'crypto', 'coingecko_id': 'magic'},
            # Crypto-adjacent stocks
            'coinbase': {'symbol': 'COIN', 'type': 'stock', 'yahoo_symbol': 'COIN'},
            'microstrategy': {'symbol': 'MSTR', 'type': 'stock', 'yahoo_symbol': 'MSTR'},
            'nvidia': {'symbol': 'NVDA', 'type': 'stock', 'yahoo_symbol': 'NVDA'},
            'tesla': {'symbol': 'TSLA', 'type': 'stock', 'yahoo_symbol': 'TSLA'},
        }
        # Pre-build one regex per keyword (word-boundary, multi-word safe)
        self._patterns = {
            keyword: re.compile(r'\b' + re.escape(keyword) + r'\b')
            for keyword in self.asset_mapping
        }

    def extract_assets(self, title: str, content: str, keywords: List[str], limit: int = 3) -> List[Dict]:
        """Extract up to `limit` unique tradeable assets from an article.

        Article keywords take priority; then the title; then the content.
        """
        found: List[Dict] = []
        seen_symbols = set()

        def add(keyword: str):
            asset = self.asset_mapping.get(keyword.lower())
            if asset and asset['symbol'] not in seen_symbols:
                seen_symbols.add(asset['symbol'])
                found.append(asset)

        text = f"{title} {content}".lower()

        for keyword in keywords or []:
            add(keyword)
        for keyword, pattern in self._patterns.items():
            if len(found) >= limit:
                break
            if pattern.search(title.lower()):
                add(keyword)
        for keyword, pattern in self._patterns.items():
            if len(found) >= limit:
                break
            if pattern.search(text):
                add(keyword)

        return found[:limit]


asset_extractor = AssetExtractor()
