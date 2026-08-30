"""Keyword-based sentiment analysis with Web3 focus (Phase 1).

Keywords are matched as whole words (word boundaries) to avoid false positives
from substrings ('ai' in 'said', 'drop' in 'airdrop', 'gain' in 'against').
The negative list includes rejection/delay/cancel terms so headlines like
"ETF rejected" classify as NEGATIVE instead of POSITIVE.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from news_scraper.models import SentimentScore

POSITIVE_KEYWORDS = [
    # Performance & financials
    'profit', 'profits', 'profitable', 'profitability', 'growth', 'growing',
    'grow', 'grows', 'increase', 'increases', 'increased', 'rising', 'rise',
    'rises', 'rose', 'gain', 'gains', 'gained', 'surge', 'surges', 'surged',
    'soar', 'soars', 'soared', 'boom', 'booms', 'jump', 'jumps', 'jumped',
    'rally', 'rallies', 'record', 'records', 'all-time high', 'ath',
    'milestone', 'breakout', 'beat', 'beats', 'revenue', 'revenues',
    'earnings', 'upgrade', 'upgrades', 'upgraded',
    # Positive events
    'success', 'successful', 'breakthrough', 'innovation', 'opportunity',
    'opportunities', 'bullish', 'bull run', 'bull market', 'expansion',
    # Capital & deals
    'funding', 'raises', 'raised', 'raise', 'investment', 'invest',
    'invests', 'invested', 'investors', 'acquisition', 'acquires',
    'acquired', 'acquiring', 'ipo', 'public offering', 'listing', 'lists',
    'listed', 'buyback', 'token buyback',
    # Adoption & launches
    'partnership', 'partnerships', 'partners', 'partnered', 'integration',
    'integrates', 'integrated', 'adoption', 'adopts', 'adopted', 'adopting',
    'launch', 'launches', 'launched', 'launching', 'mainnet', 'airdrop',
    'airdrops', 'staking', 'yield', 'yields', 'institutional',
    'institutional adoption', 'regulation clarity', 'regulatory clarity',
    'approval', 'approves', 'approved', 'approving', 'greenlight',
    'greenlit', 'etf approval', 'spot etf', 'halving', 'burn', 'burns',
    'burned', 'inflows', 'inflow', 'clearance', 'cleared', 'win', 'wins',
    'liquidity', 'scaling',
]

NEGATIVE_KEYWORDS = [
    # Losses & declines
    'loss', 'losses', 'losing', 'lost', 'decline', 'declines', 'declined',
    'declining', 'fall', 'falls', 'falling', 'fell', 'drop', 'drops',
    'dropped', 'dropping', 'plunge', 'plunges', 'plunged', 'tank', 'tanks',
    'tanked', 'downtrend', 'correction', 'selloff', 'sell-off',
    # Failures & insolvency
    'failure', 'failures', 'fail', 'fails', 'failed', 'failing',
    'bankruptcy', 'bankrupt', 'insolvency', 'insolvent', 'collapse',
    'collapsed', 'collapses',
    # Crisis & macro
    'recession', 'downturn', 'crisis', 'crash', 'crashes', 'crashed',
    'bearish', 'bear market', 'layoffs', 'layoff', 'downsizing', 'firing',
    'fired',
    # Crime & fraud
    'hack', 'hacked', 'hacking', 'breach', 'breached', 'exploit',
    'exploited', 'vulnerability', 'vulnerabilities', 'attack', 'attacked',
    'attacks', 'rug pull', 'scam', 'scams', 'ponzi', 'fraud', 'phishing',
    'exit scam', 'stolen', 'theft', 'drain', 'drains', 'drained',
    'siphoned', 'insider trading',
    # Regulatory & legal
    'lawsuit', 'lawsuits', 'sued', 'suing', 'fine', 'fines', 'fined',
    'penalty', 'penalties', 'sanction', 'sanctions', 'ban', 'bans',
    'banned', 'crackdown', 'regulation crackdown', 'sec lawsuit',
    'sec sues', 'sec charges', 'delisting', 'delisted', 'restriction',
    'restrictions',
    # Market stress
    'dump', 'dumps', 'dumped', 'dumping', 'liquidation', 'liquidations',
    'outflows', 'depeg', 'depegged', 'shutdown', 'shuts down', 'shut down',
    'network congestion', 'bridge hack', 'consensus failure',
    'impermanent loss', 'centralized', 'ftx collapse', 'smart contract bug',
    'gas fees spike',
    # Negation & rejection (keeps sentiment consistent with negation detection)
    'reject', 'rejects', 'rejected', 'rejection', 'rejecting', 'deny',
    'denies', 'denied', 'denial', 'refuse', 'refuses', 'refused', 'reverses',
    'reversed', 'reversal', 'withdraw', 'withdraws', 'withdrawn',
    'withdrawal', 'abandon', 'abandons', 'abandoned', 'abandonment',
    'postpone', 'postpones', 'postponed', 'delay', 'delays', 'delayed',
    'defer', 'defers', 'deferred', 'stall', 'stalls', 'stalled', 'on hold',
    'cancel', 'cancels', 'canceled', 'cancelled', 'cancellation', 'scrapped',
    'halt', 'halts', 'halted', 'suspend', 'suspends', 'suspended',
    'suspension', 'pause', 'pauses', 'paused', 'block', 'blocks', 'blocked',
]

DEFAULT_SENTIMENT_MULTIPLIERS: Dict[SentimentScore, float] = {
    SentimentScore.VERY_POSITIVE: 1.3,
    SentimentScore.POSITIVE: 1.1,
    SentimentScore.NEUTRAL: 1.0,
    SentimentScore.NEGATIVE: 0.5,
    SentimentScore.VERY_NEGATIVE: 0.2,
}


class SentimentAnalyzer:
    def __init__(
        self,
        multipliers: Optional[Dict[SentimentScore, float]] = None,
    ) -> None:
        self.sentiment_multipliers = multipliers or DEFAULT_SENTIMENT_MULTIPLIERS

    def analyze_sentiment(self, text: str) -> SentimentScore:
        """Classify a headline/body into a five-point sentiment score."""
        text_lower = text.lower()

        def count_matches(keywords) -> int:
            pattern = r'\b(?:' + '|'.join(re.escape(kw) for kw in keywords) + r')\b'
            return len(re.findall(pattern, text_lower))

        positive_count = count_matches(POSITIVE_KEYWORDS)
        negative_count = count_matches(NEGATIVE_KEYWORDS)

        if positive_count > negative_count + 2:
            return SentimentScore.VERY_POSITIVE
        elif positive_count > negative_count:
            return SentimentScore.POSITIVE
        elif negative_count > positive_count + 2:
            return SentimentScore.VERY_NEGATIVE
        elif negative_count > positive_count:
            return SentimentScore.NEGATIVE
        else:
            return SentimentScore.NEUTRAL

    def get_sentiment_multiplier(self, sentiment: SentimentScore) -> float:
        """Return the score multiplier for a given sentiment."""
        return self.sentiment_multipliers.get(sentiment, 1.0)
