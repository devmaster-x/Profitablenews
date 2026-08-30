"""Source registry: RSS/API/news-web source configuration and credibility.

Credibility weights are keyed on the ACTUAL source names used by the scraper
(e.g. ``coindesk_rss``). Selenium/Chrome is deliberately NOT imported here —
it lives behind a lazy import so the package works without the optional
"webscraping" extra.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from news_scraper.models import NewsCategory

logger = logging.getLogger(__name__)

# Source credibility weighting keyed on ACTUAL source names (Phase 1)
SOURCE_CREDIBILITY: Dict[str, float] = {
    # Tier 1: Established crypto-native newsrooms
    "coindesk": 1.2,
    "coindesk_rss": 1.2,
    "web3_news": 1.2,
    "nft_now": 1.15,
    "the_block": 1.2,
    "theblock_rss": 1.2,
    "ethereum_foundation": 1.15,
    # Tier 2: Reputable crypto media
    "cointelegraph": 1.15,
    "cointelegraph_rss": 1.15,
    "decrypt": 1.1,
    "decrypt_rss": 1.1,
    "blockworks": 1.1,
    "bitcoin_magazine": 1.05,
    # Tier 3: Niche but credible
    "bankless": 1.0,
    "defiant": 1.0,
    # Tier 4: Broader tech/startup coverage
    "techcrunch": 0.95,
    "venturebeat": 0.95,
    # Tier 5: Community-sourced (no editorial credibility)
    "hacker_news": 0.9,
    "hacker_news_api": 0.9,
    # Default
    "default": 0.9,
}

# RSS/API-based sources for fresh, high-quality news (primary path)
RSS_SOURCES: Dict[str, Dict[str, Any]] = {
    "coindesk_rss": {
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "category": NewsCategory.CRYPTO,
        "type": "rss",
    },
    "cointelegraph_rss": {
        "url": "https://cointelegraph.com/rss",
        "category": NewsCategory.CRYPTO,
        "type": "rss",
    },
    "decrypt_rss": {
        "url": "https://decrypt.co/feed",
        "category": NewsCategory.WEB3,
        "type": "rss",
    },
    "theblock_rss": {
        "url": "https://www.theblock.co/rss.xml",
        "category": NewsCategory.BLOCKCHAIN,
        "type": "rss",
    },
    "hacker_news_api": {
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=30",
        "category": NewsCategory.SOFTWARE,
        "type": "api",
    },
}

# HTML/JS-scraped sources (requires the optional "webscraping" extra +
# ``settings.web_scraping_enabled``). Selenium selectors are brittle; kept
# for sources without an RSS feed.
NEWS_SOURCES: Dict[str, Dict[str, Any]] = {
    "coindesk": {
        "url": "https://www.coindesk.com/",
        "category": NewsCategory.CRYPTO,
        "selectors": {
            "articles": "article",
            "title": "h3 a, h2 a",
            "link": "h3 a, h2 a",
            "content": ".at-text",
        },
    },
    "cointelegraph": {
        "url": "https://cointelegraph.com/",
        "category": NewsCategory.CRYPTO,
        "selectors": {
            "articles": "article.post-card",
            "title": "span.post-card-inline__title",
            "link": "a.post-card-inline__title",
            "content": "div.post-card-inline__text",
        },
    },
    "decrypt": {
        "url": "https://decrypt.co/",
        "category": NewsCategory.WEB3,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": "p",
        },
    },
    "the_block": {
        "url": "https://www.theblock.co/latest",
        "category": NewsCategory.BLOCKCHAIN,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": "p",
        },
    },
    "defiant": {
        "url": "https://thedefiant.io/",
        "category": NewsCategory.DEFI,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": ".article-excerpt",
        },
    },
    "bitcoin_magazine": {
        "url": "https://bitcoinmagazine.com/",
        "category": NewsCategory.CRYPTO,
        "selectors": {
            "articles": "article",
            "title": "h3 a, h2 a",
            "link": "h3 a, h2 a",
            "content": "p",
        },
    },
    "ethereum_foundation": {
        "url": "https://blog.ethereum.org/",
        "category": NewsCategory.BLOCKCHAIN,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": "p",
        },
    },
    "web3_news": {
        "url": "https://www.coindesk.com/tech/",
        "category": NewsCategory.WEB3,
        "selectors": {
            "articles": "article",
            "title": "h3 a, h2 a",
            "link": "h3 a, h2 a",
            "content": ".at-text",
        },
    },
    "blockworks": {
        "url": "https://blockworks.co/",
        "category": NewsCategory.CRYPTO,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": "p",
        },
    },
    "nft_now": {
        "url": "https://nft.coindesk.com/",
        "category": NewsCategory.NFT,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": "p",
        },
    },
    "bankless": {
        "url": "https://www.bankless.com/",
        "category": NewsCategory.DEFI,
        "selectors": {
            "articles": "article",
            "title": "h2 a, h3 a",
            "link": "h2 a, h3 a",
            "content": "p",
        },
    },
    "techcrunch": {
        "url": "https://techcrunch.com/category/startups/",
        "category": NewsCategory.STARTUP,
        "selectors": {
            "articles": "article.post-block",
            "title": "h2.post-block__title a",
            "link": "h2.post-block__title a",
            "content": ".post-block__content",
        },
    },
    "hacker_news": {
        "url": "https://news.ycombinator.com/",
        "category": NewsCategory.SOFTWARE,
        "selectors": {
            "articles": "tr.athing",
            "title": "span.titleline a",
            "link": "span.titleline a",
            "content": "",
        },
    },
    "venturebeat": {
        "url": "https://venturebeat.com/",
        "category": NewsCategory.STARTUP,
        "selectors": {
            "articles": "article",
            "title": "h2 a",
            "link": "h2 a",
            "content": "div.ArticleBody-content",
        },
    },
}

# Web sources the scraper actually drives with Selenium (RSS remains primary)
WEB_SCRAPING_PRIORITY_SOURCES = ["techcrunch", "venturebeat"]


class SourceRegistry:
    def __init__(
        self,
        rss_sources: Optional[Dict[str, Dict[str, Any]]] = None,
        news_sources: Optional[Dict[str, Dict[str, Any]]] = None,
        credibility: Optional[Dict[str, float]] = None,
        web_scraping_priority_sources: Optional[List[str]] = None,
    ) -> None:
        self.rss_sources = rss_sources or RSS_SOURCES
        self.news_sources = news_sources or NEWS_SOURCES
        self.source_credibility = credibility or SOURCE_CREDIBILITY
        self.web_scraping_priority_sources = web_scraping_priority_sources or WEB_SCRAPING_PRIORITY_SOURCES

    def get_source_credibility(self, source_name: str) -> float:
        """Get the credibility weight for a source (falls back to default)."""
        return self.source_credibility.get(source_name, self.source_credibility["default"])

    def apply_source_credibility(self, profit_score: float, source_name: str) -> float:
        """Scale a profit score by the source's credibility weight (capped at 10)."""
        return min(profit_score * self.get_source_credibility(source_name), 10.0)

    def create_driver(self, settings) -> Any:
        """Create a Chrome WebDriver (lazy: requires the "webscraping" extra).

        Selenium is imported only when actually used, so the package works
        without Chrome. Raises a descriptive error if Selenium is missing.
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:  # pragma: no cover - depends on extra
            raise RuntimeError(
                "Selenium web scraping is enabled but the 'webscraping' extra "
                "is not installed. Install it with `poetry install -E webscraping` "
                "or disable WEB_SCRAPING_ENABLED."
            ) from exc

        chrome_options = Options()
        chrome_options.add_argument(f"--headless={str(settings.chrome_headless).lower()}")
        chrome_options.add_argument(f"--no-sandbox={str(settings.chrome_no_sandbox).lower()}")
        chrome_options.add_argument(f"--disable-dev-shm-usage={str(settings.chrome_disable_dev_shm).lower()}")
        chrome_options.add_argument(f"--disable-gpu={str(settings.chrome_disable_gpu).lower()}")
        chrome_options.add_argument(f"--window-size={settings.chrome_window_size}")
        chrome_options.add_argument(f"--user-agent={settings.user_agent}")

        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error("Failed to create Chrome driver: %s", e)
            raise
        driver.set_page_load_timeout(settings.scraping_timeout)
        return driver
