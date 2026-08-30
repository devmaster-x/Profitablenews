"""Profit scoring engine (Phase 1, Task 1.1/1.5).

Scores each article 0-10 based on Web3 relevance (keyword weights), time
sensitivity, market impact, source credibility (applied by the scraper) and
sentiment gating (negative news scores low even when it mentions positive
keywords, e.g. "ETF rejected").
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from news_scraper.models import NewsCategory, SentimentScore
from news_scraper.negation import NegationDetector
from news_scraper.sentiment import SentimentAnalyzer

# Half-saturation constant for smooth score compression: base = 10*raw/(raw+K).
# raw == K maps to 5.0; doubling raw always increases the base — no hard ceiling.
_SCORE_COMPRESSION_K = 8.0

CATEGORY_SCORES: Dict[NewsCategory, float] = {
    NewsCategory.CRYPTO: 6.0,
    NewsCategory.BLOCKCHAIN: 6.0,
    NewsCategory.WEB3: 6.5,
    NewsCategory.DEFI: 6.5,
    NewsCategory.NFT: 5.5,
    NewsCategory.DAO: 5.0,
    NewsCategory.MARKET: 3.0,
    NewsCategory.SOFTWARE: 4.0,
    NewsCategory.STARTUP: 4.5,
    NewsCategory.TECH_EARNINGS: 6.0,
    NewsCategory.GENERAL: 2.0,
    NewsCategory.AI_ML: 5.5,
    NewsCategory.INVESTMENT: 6.5,
}

# Web3 & Blockchain specific keywords (highest weight)
WEB3_KEYWORDS: Dict[str, float] = {
    # Layer 1 Blockchains
    'ethereum': 2.0, 'bitcoin': 2.0, 'solana': 1.5, 'cardano': 1.5,
    'polkadot': 1.5, 'avalanche': 1.5, 'cosmos': 1.5, 'algorand': 1.0,
    'near protocol': 1.5, 'polygon': 1.5, 'binance smart chain': 1.5,
    'fantom': 1.0, 'harmony': 1.0, 'tezos': 1.0, 'elrond': 1.0,
    # Layer 2 Solutions
    'arbitrum': 1.5, 'optimism': 1.5, 'zksync': 1.5, 'starknet': 1.5,
    'loopring': 1.0, 'immutable': 1.5, 'polygon zkevm': 1.5,
    'base': 1.5, 'linea': 1.0, 'scroll': 1.0,
    # DeFi Protocols
    'uniswap': 1.5, 'aave': 1.5, 'compound': 1.5, 'maker': 1.5,
    'curve': 1.5, 'lido': 1.5, 'pancakeswap': 1.0, 'sushiswap': 1.0,
    'dydx': 1.5, 'gmx': 1.5, 'synthetix': 1.0, 'balancer': 1.0,
    'yearn': 1.0, 'convex': 1.0, 'rocket pool': 1.5,
    # Web3 Infrastructure
    'chainlink': 1.5, 'the graph': 1.5, 'filecoin': 1.5, 'arweave': 1.5,
    'livepeer': 1.0, 'helium': 1.5, 'render': 1.5, 'akash': 1.0,
    # NFT & Gaming
    'opensea': 1.5, 'blur': 1.5, 'axie infinity': 1.0, 'sandbox': 1.5,
    'decentraland': 1.5, 'gala': 1.0, 'immutable x': 1.5, 'flow': 1.0,
    'enjin': 1.0, 'wax': 1.0, 'sorare': 1.0,
    # Web3 Concepts
    'defi': 1.5, 'dapp': 1.0, 'dao': 1.5, 'nft': 1.5, 'metaverse': 1.5,
    'web3': 2.0, 'gamefi': 1.5, 'play-to-earn': 1.0, 'move-to-earn': 1.0,
    'socialfi': 1.0, 'rwa': 1.5, 'tokenization': 1.5, 'staking': 1.0,
    'yield farming': 1.0, 'liquidity mining': 1.0, 'tvl': 1.5,
    'smart contract': 1.5, 'consensus': 1.0, 'validator': 1.0,
    'gas fees': 0.5, 'bridge': 1.0, 'cross-chain': 1.5, 'interoperability': 1.5,
    # Institutional & Regulatory
    'etf': 2.0, 'institutional adoption': 2.0, 'grayscale': 1.5,
    'blackrock': 2.0, 'fidelity': 2.0, 'coinbase custody': 1.5,
    'regulation': 1.0, 'sec approval': 2.0, 'cftc': 1.0,
    # Technical Advancements
    'scaling solution': 1.5, 'sharding': 1.5, 'proof of stake': 1.5,
    'zero knowledge': 1.5, 'zk-rollup': 1.5, 'optimistic rollup': 1.5,
    'eip': 1.0, 'bip': 1.0, 'upgrade': 1.5, 'hard fork': 1.0,
    'mainnet': 1.5, 'testnet': 0.5, 'audit': 1.0,
    # Market Events
    'halving': 2.0, 'airdrop': 1.5, 'token launch': 1.5, 'ido': 1.5,
    'ico': 1.0, 'ieo': 1.0, 'token burn': 1.0, 'buyback': 1.0,
    'listing': 1.5, 'integration': 1.5, 'partnership': 1.5,
    # Privacy & Identity
    'zero knowledge proof': 1.5, 'privacy coin': 1.0, 'monero': 1.0,
    'zcash': 1.0, 'tornado cash': 0.5, 'did': 1.0, 'soulbound': 1.0,
    # Real World Assets
    'real world asset': 1.5, 'tokenized': 1.5, 'cbdc': 1.5,
    'stablecoin': 1.5, 'usdc': 1.0, 'usdt': 1.0, 'dai': 1.0,
}

# Traditional Finance & Tech (moderate weight)
TRADITIONAL_KEYWORDS: Dict[str, float] = {
    'profit': 1.0, 'revenue': 1.5, 'earnings': 1.5, 'growth': 1.0,
    'investment': 1.0, 'funding': 1.5, 'acquisition': 2.0, 'ipo': 2.5,
    'merger': 1.5, 'partnership': 1.0, 'expansion': 1.0, 'innovation': 0.5,
    'breakthrough': 1.0, 'disruption': 1.0, 'market leader': 1.5,
    'billion': 1.0, 'million': 0.5, 'valuation': 1.0, 'stock price': 1.5,
    'trading': 1.0, 'bullish': 1.0, 'surge': 1.0, 'rally': 1.0,
    # AI/ML specific terms
    'artificial intelligence': 1.5, 'machine learning': 1.5, 'ai': 1.0,
    'neural network': 1.0, 'deep learning': 1.0, 'chatgpt': 1.5,
    'openai': 1.0, 'automation': 1.0, 'algorithm': 0.5,
    # Market movement indicators
    'stock market': 1.0, 'market cap': 1.0, 'dividend': 1.0,
    'earnings call': 1.5, 'quarterly results': 1.5, 'guidance': 1.0,
    'analyst': 0.5, 'upgrade': 1.0, 'downgrade': 0.5, 'target price': 1.0,
    # Startup/Investment terms
    'venture capital': 1.5, 'series a': 1.0, 'series b': 1.0, 'unicorn': 1.5,
    'startup': 1.0, 'scale': 1.0, 'exit': 1.5,
}

# Major Web3 Companies & Exchanges
WEB3_COMPANIES: Dict[str, float] = {
    # Exchanges
    'coinbase': 1.5, 'binance': 1.5, 'kraken': 1.0, 'gemini': 1.0,
    'okx': 1.0, 'bybit': 1.0, 'bitfinex': 1.0, 'kucoin': 1.0,
    'huobi': 1.0, 'ftx': 0.5, 'crypto.com': 1.0,
    # Web3 Companies
    'consensys': 1.5, 'alchemy': 1.5, 'infura': 1.0, 'quicknode': 1.0,
    'metamask': 1.5, 'ledger': 1.0, 'trezor': 1.0, 'trust wallet': 1.0,
    'rainbow': 1.0, 'argent': 1.0, 'safe': 1.0,
    # Venture/Investment
    'andreessen horowitz': 1.5, 'a16z crypto': 2.0, 'paradigm': 1.5,
    'polychain': 1.5, 'pantera': 1.5, 'digital currency group': 1.5,
    'three arrows capital': 0.5, 'alameda research': 0.5,
    # Traditional Tech (lower weight for web3 context)
    'apple': 1.0, 'google': 1.0, 'microsoft': 1.0, 'amazon': 1.0,
    'nvidia': 1.5, 'meta': 1.0, 'tesla': 1.0,
}

TIME_KEYWORDS = ['breaking', 'just in', 'exclusive', 'announcement', 'launch', 'live', 'now']
IMPACT_KEYWORDS = ['market', 'industry', 'sector', 'global', 'worldwide', 'international', 'mainstream']
VOLUME_KEYWORDS = ['volume', 'trading volume', 'active', 'popular', 'trending', 'viral', 'adoption rate']
TECHNICAL_KEYWORDS = ['support', 'resistance', 'breakout', 'all-time high', 'ath', 'price target']

# Regex patterns for keyword extraction
KEYWORD_PATTERNS = [
    # Web3 & Blockchain
    r'\b(?:web3|web 3|web3\.0)\b',
    r'\b(?:blockchain|distributed ledger|dlt)\b',
    r'\b(?:bitcoin|btc|satoshi)\b',
    r'\b(?:ethereum|eth|ether|vitalik)\b',
    r'\b(?:solana|sol|cardano|ada|polkadot|dot|avalanche|avax)\b',
    r'\b(?:layer 2|layer2|l2|scaling solution)\b',
    r'\b(?:arbitrum|optimism|zksync|starknet|polygon)\b',
    # DeFi & Trading
    r'\b(?:defi|decentralized finance)\b',
    r'\b(?:dex|decentralized exchange|amm)\b',
    r'\b(?:uniswap|aave|compound|curve|lido)\b',
    r'\b(?:yield|staking|liquidity|tvl|total value locked)\b',
    r'\b(?:swap|pool|liquidity mining|yield farming)\b',
    # NFT & Gaming
    r'\b(?:nft|non-fungible token|digital collectible)\b',
    r'\b(?:opensea|blur|marketplace)\b',
    r'\b(?:metaverse|virtual world|sandbox|decentraland)\b',
    r'\b(?:gamefi|play-to-earn|p2e|gaming)\b',
    # DAO & Governance
    r'\b(?:dao|decentralized autonomous organization)\b',
    r'\b(?:governance|voting|proposal|snapshot)\b',
    r'\b(?:token holder|community|delegate)\b',
    # Technical
    r'\b(?:smart contract|solidity|vyper|rust)\b',
    r'\b(?:consensus|proof of stake|pos|proof of work|pow)\b',
    r'\b(?:validator|node|miner|mining)\b',
    r'\b(?:gas|gas fees|transaction fee|gwei)\b',
    r'\b(?:bridge|cross-chain|interoperability)\b',
    r'\b(?:zero knowledge|zk|zkp|privacy)\b',
    r'\b(?:eip|ethereum improvement proposal)\b',
    r'\b(?:upgrade|hard fork|soft fork|mainnet)\b',
    # Financial & Investment
    r'\b(?:ipo|initial public offering)\b',
    r'\b(?:acquisition|merger|funding|investment)\b',
    r'\b(?:venture capital|vc|a16z|paradigm)\b',
    r'\b(?:etf|exchange traded fund|spot etf)\b',
    r'\b(?:institutional|adoption|mainstream)\b',
    # Tokens & Assets
    r'\b(?:token|cryptocurrency|crypto|coin)\b',
    r'\b(?:stablecoin|usdc|usdt|dai)\b',
    r'\b(?:altcoin|shitcoin|memecoin)\b',
    r'\b(?:airdrop|token launch|ido|ico)\b',
    r'\b(?:tokenomics|utility token|governance token)\b',
    # Market & Trading
    r'\b(?:bull market|bear market|bullish|bearish)\b',
    r'\b(?:whale|retail|institutional investor)\b',
    r'\b(?:exchange|cex|centralized exchange)\b',
    r'\b(?:coinbase|binance|kraken|gemini)\b',
    r'\b(?:listing|trading pair|volume)\b',
    # AI/ML (still relevant)
    r'\b(?:ai|artificial intelligence|machine learning|ml)\b',
    r'\b(?:chatgpt|gpt|llm|large language model)\b',
    r'\b(?:neural network|deep learning)\b',
    # Regulation & Compliance
    r'\b(?:sec|securities and exchange commission)\b',
    r'\b(?:regulation|regulatory|compliance)\b',
    r'\b(?:lawsuit|legal|court|settlement)\b',
    r'\b(?:ban|restriction|crackdown)\b',
    # Security & Risk
    r'\b(?:hack|exploit|vulnerability|security breach)\b',
    r'\b(?:rug pull|scam|phishing|fraud)\b',
    r'\b(?:audit|security audit|bug bounty)\b',
    # Traditional Tech & Business
    r'\b(?:startup|unicorn|valuation)\b',
    r'\b(?:fintech|biotech|saas|cloud computing)\b',
    r'\b(?:cybersecurity|data analytics|big data)\b',
    r'\b(?:electric vehicle|ev|renewable energy|clean tech)\b',
    r'\b(?:earnings|revenue|profit|growth|market cap)\b',
    # Specific Projects & Protocols
    r'\b(?:chainlink|the graph|filecoin|arweave)\b',
    r'\b(?:maker|mkr|synthetix|balancer)\b',
    r'\b(?:ens|ethereum name service)\b',
    r'\b(?:ipfs|decentralized storage)\b',
]


class ProfitScorer:
    def __init__(
        self,
        sentiment: Optional[SentimentAnalyzer] = None,
        negation: Optional[NegationDetector] = None,
    ) -> None:
        self._sentiment = sentiment or SentimentAnalyzer()
        self._negation = negation or NegationDetector()

    def calculate_profit_score(
        self,
        title: str,
        content: str,
        category: NewsCategory,
        sentiment: Optional[SentimentScore] = None,
    ) -> float:
        """Calculate profit potential score (0-10) with enhanced Web3 focus.

        Sentiment-aware: keyword points are zeroed when the keyword appears in
        a negated context, and the final score is scaled by the sentiment
        multiplier so negative news scores low even when it mentions positive
        keywords (e.g. "ETF rejected").
        """
        score = 0.0
        text = f"{title} {content}".lower()

        # Base score from category (Web3/Crypto get higher base scores)
        score += CATEGORY_SCORES.get(category, 2.0)

        for keyword, points in WEB3_KEYWORDS.items():
            if keyword in text:
                negation_factor = self._negation.check_negation_context(text, keyword)
                score += points * negation_factor

        for keyword, points in TRADITIONAL_KEYWORDS.items():
            if keyword in text:
                negation_factor = self._negation.check_negation_context(text, keyword)
                score += points * negation_factor

        for company, points in WEB3_COMPANIES.items():
            if company in text:
                negation_factor = self._negation.check_negation_context(text, company)
                score += points * negation_factor

        # Time sensitivity & Market impact
        if any(keyword in text for keyword in TIME_KEYWORDS):
            score += 1.5

        if any(keyword in text for keyword in IMPACT_KEYWORDS):
            score += 0.5

        # Volume and activity indicators
        if any(keyword in text for keyword in VOLUME_KEYWORDS):
            score += 0.5

        # Technical analysis indicators
        if any(keyword in text for keyword in TECHNICAL_KEYWORDS):
            score += 0.5

        # De-saturation (2026-08-29): the historical hard cap min(raw, 10) BEFORE
        # the sentiment multiplier pinned ~40% of articles at exactly 10.0 and
        # destroyed ranking resolution at the top. A raw hard cap AFTER the
        # multiplier would be worse (keyword-dense negative articles could reach
        # 10). Instead: compress the unbounded keyword sum smoothly and
        # monotonically into [0, 10) so every raw score maps to a distinct base
        # (raw 8 → 5.0, 16 → 6.7, 32 → 8.0; never reaches 10), then apply the
        # sentiment multiplier, then cap defensively.
        base_score = 10.0 * score / (score + _SCORE_COMPRESSION_K) if score > 0 else 0.0

        if sentiment is None:
            sentiment = self._sentiment.analyze_sentiment(f"{title} {content}")
        multiplier = self._sentiment.get_sentiment_multiplier(sentiment)
        final_score = base_score * multiplier

        return min(final_score, 10.0)

    def extract_keywords(self, title: str, content: str) -> List[str]:
        """Extract relevant keywords with enhanced Web3 focus."""
        text = f"{title} {content}".lower()

        keywords: List[str] = []
        for pattern in KEYWORD_PATTERNS:
            matches = re.findall(pattern, text)
            keywords.extend(matches)

        return list(set(keywords))
