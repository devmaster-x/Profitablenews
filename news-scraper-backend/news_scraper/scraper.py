"""News scraper: thin orchestrator over the analysis modules.

The 1000+ line historical monolith was decomposed into:

- ``news_scraper.sentiment``  → keyword sentiment classification
- ``news_scraper.negation``   → negated-context detection
- ``news_scraper.scoring``    → Web3 profit scoring + keyword extraction
- ``news_scraper.sources``    → source registry, credibility, lazy Selenium

``NewsScraper`` keeps the exact public API (attributes and method names) that
the test-suite and the API layer depend on, and adds constructor injection for
``settings`` / ``db`` / ``clusterer`` so hosts can embed it.

Selenium is deliberately NOT imported at module load — the optional
"webscraping" extra is only pulled in when a web scrape actually runs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

from news_scraper import timeutil
from news_scraper.config import settings as default_settings
from news_scraper.models import NewsArticleCreate, NewsCategory, SentimentScore
from news_scraper.negation import NegationDetector
from news_scraper.scoring import ProfitScorer
from news_scraper.sentiment import SentimentAnalyzer
from news_scraper.sources import SourceRegistry

logger = logging.getLogger(__name__)


class NewsScraper:
    def __init__(
        self,
        settings=None,
        db=None,
        clusterer=None,
        sources: Optional[SourceRegistry] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.db = db
        self.clusterer = clusterer

        self._negation = NegationDetector()
        self._sentiment = SentimentAnalyzer()
        self._scorer = ProfitScorer(sentiment=self._sentiment, negation=self._negation)
        self._registry = sources or SourceRegistry()

        # Minimum profit score threshold (configurable)
        self.min_profit_score = self.settings.scraper_min_profit_score

        # Back-compat attributes (Phase 1 code and tests read these directly)
        self.sentiment_multipliers = self._sentiment.sentiment_multipliers
        self.source_credibility = self._registry.source_credibility
        self.rss_sources = self._registry.rss_sources
        self.news_sources = self._registry.news_sources
        self.negation_patterns_single = self._negation.negation_patterns_single
        self.negation_patterns_multi = self._negation.negation_patterns_multi

    # ------------------------------------------------------------------
    # Dependency resolution (injected instances win; module singletons fall back)
    # ------------------------------------------------------------------

    def _resolve_db(self):
        if self.db is not None:
            return self.db
        from news_scraper.persistent_database import persistent_db

        return persistent_db

    def _resolve_clusterer(self):
        if self.clusterer is not None:
            return self.clusterer
        from news_scraper.clustering import clusterer as default_clusterer

        return default_clusterer

    # ------------------------------------------------------------------
    # Sentiment / negation / scoring (delegated to the analysis modules)
    # ------------------------------------------------------------------

    def analyze_sentiment(self, text: str) -> SentimentScore:
        return self._sentiment.analyze_sentiment(text)

    def get_sentiment_multiplier(self, sentiment: SentimentScore) -> float:
        return self._sentiment.get_sentiment_multiplier(sentiment)

    def check_negation_context(self, text: str, keyword: str, window: int = 6) -> float:
        return self._negation.check_negation_context(text, keyword, window)

    def calculate_profit_score(
        self,
        title: str,
        content: str,
        category: NewsCategory,
        sentiment: Optional[SentimentScore] = None,
    ) -> float:
        return self._scorer.calculate_profit_score(title, content, category, sentiment=sentiment)

    def extract_keywords(self, title: str, content: str) -> List[str]:
        return self._scorer.extract_keywords(title, content)

    # ------------------------------------------------------------------
    # Source credibility (delegated to the registry)
    # ------------------------------------------------------------------

    def get_source_credibility(self, source_name: str) -> float:
        return self._registry.get_source_credibility(source_name)

    def apply_source_credibility(self, profit_score: float, source_name: str) -> float:
        return self._registry.apply_source_credibility(profit_score, source_name)

    def create_driver(self) -> Any:
        """Create a Chrome WebDriver (lazy: requires the "webscraping" extra)."""
        return self._registry.create_driver(self.settings)

    # ------------------------------------------------------------------
    # Article freshness
    # ------------------------------------------------------------------

    def is_recent_article(self, pub_date: Optional[datetime], hours_threshold: int = 48) -> bool:
        """Check if article was published within the last N hours."""
        if not pub_date:
            return True  # Include if we can't determine age
        cutoff = timeutil.utcnow() - timedelta(hours=hours_threshold)
        return pub_date >= cutoff

    # ------------------------------------------------------------------
    # Fetching: RSS + Hacker News API (primary path, no browser needed)
    # ------------------------------------------------------------------

    def scrape_rss_feed(self, source_name: str, source_config: Dict[str, Any]) -> List[NewsArticleCreate]:
        """Scrape articles from RSS feeds."""
        articles: List[NewsArticleCreate] = []

        try:
            logger.info("Fetching RSS feed from %s", source_name)
            response = requests.get(
                source_config["url"],
                headers={"User-Agent": self.settings.user_agent},
                timeout=15,
            )
            response.raise_for_status()

            feed = feedparser.parse(response.content)
            logger.info("Found %d entries in %s RSS feed", len(feed.entries), source_name)

            for entry in feed.entries[:20]:  # Limit to 20 most recent
                try:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    pub_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_date = timeutil.parse_dt(datetime(*entry.published_parsed[:6]))
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        pub_date = timeutil.parse_dt(datetime(*entry.updated_parsed[:6]))

                    if not self.is_recent_article(pub_date, hours_threshold=48):
                        continue

                    content = entry.get("summary", entry.get("description", ""))
                    if not content:
                        content = f"Article from {source_name}: {title}"
                    content = BeautifulSoup(content, "html.parser").get_text(strip=True)

                    url = entry.get("link", "")

                    sentiment = self.analyze_sentiment(f"{title} {content}")
                    profit_score = self.calculate_profit_score(
                        title, content, source_config["category"], sentiment=sentiment
                    )
                    source_weight = self.get_source_credibility(source_name)
                    profit_score = self.apply_source_credibility(profit_score, source_name)

                    if profit_score < self.min_profit_score:
                        logger.debug("Skipping low-profit article (%.1f): %s", profit_score, title[:50])
                        continue

                    articles.append(NewsArticleCreate(
                        title=title,
                        content=content,
                        source=source_name,
                        url=url if url else None,
                        category=source_config["category"],
                        sentiment=sentiment,
                        profit_score=profit_score,
                        keywords=self.extract_keywords(title, content),
                        source_credibility_weight=source_weight,
                        sentiment_multiplier=self.get_sentiment_multiplier(sentiment),
                    ))
                    logger.info("✓ RSS Article (score: %.1f): %s", profit_score, title[:60])
                except Exception as e:
                    logger.error("Error processing RSS entry from %s: %s", source_name, e)
                    continue
        except requests.RequestException as e:
            logger.error("Failed to fetch RSS feed %s: %s", source_name, e)
        except Exception as e:
            logger.error("Unexpected error parsing RSS feed %s: %s", source_name, e)

        logger.info("Scraped %d high-quality articles from %s RSS", len(articles), source_name)
        return articles

    def scrape_hacker_news_api(self) -> List[NewsArticleCreate]:
        """Scrape articles from the Hacker News API."""
        articles: List[NewsArticleCreate] = []

        try:
            logger.info("Fetching from Hacker News API")
            response = requests.get(
                "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=30",
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            for hit in data.get("hits", []):
                try:
                    title = hit.get("title", "").strip()
                    if not title:
                        continue

                    created_at = hit.get("created_at")
                    if created_at:
                        pub_date = timeutil.parse_dt(created_at)
                        if not self.is_recent_article(pub_date, hours_threshold=24):
                            continue

                    url = hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}")
                    content = hit.get("story_text", "")
                    if not content:
                        content = f"Hacker News discussion: {title}"
                    content = BeautifulSoup(content, "html.parser").get_text(strip=True)

                    sentiment = self.analyze_sentiment(f"{title} {content}")
                    profit_score = self.calculate_profit_score(
                        title, content, NewsCategory.SOFTWARE, sentiment=sentiment
                    )
                    source_weight = self.get_source_credibility("hacker_news_api")
                    profit_score = self.apply_source_credibility(profit_score, "hacker_news_api")

                    if profit_score < self.min_profit_score:
                        continue

                    articles.append(NewsArticleCreate(
                        title=title,
                        content=content,
                        source="hacker_news_api",
                        url=url,
                        category=NewsCategory.SOFTWARE,
                        sentiment=sentiment,
                        profit_score=profit_score,
                        keywords=self.extract_keywords(title, content),
                        source_credibility_weight=source_weight,
                        sentiment_multiplier=self.get_sentiment_multiplier(sentiment),
                    ))
                    logger.info("✓ HN Article (score: %.1f): %s", profit_score, title[:60])
                except Exception as e:
                    logger.error("Error processing HN article: %s", e)
                    continue
        except Exception as e:
            logger.error("Failed to fetch Hacker News API: %s", e)

        logger.info("Scraped %d articles from Hacker News", len(articles))
        return articles

    # ------------------------------------------------------------------
    # Web scraping (optional: requires the "webscraping" extra + settings)
    # ------------------------------------------------------------------

    def scrape_source(self, source_name: str, source_config: Dict[str, Any]) -> List[NewsArticleCreate]:
        """Scrape articles from a single JS-rendered source with Selenium."""
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        articles: List[NewsArticleCreate] = []
        driver = None

        try:
            logger.info("Scraping %s from %s", source_name, source_config["url"])
            driver = self.create_driver()
            driver.get(source_config["url"])

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, source_config["selectors"]["articles"]))
            )

            soup = BeautifulSoup(driver.page_source, "html.parser")
            article_elements = soup.select(source_config["selectors"]["articles"])
            logger.info("Found %d articles on %s", len(article_elements), source_name)

            for i, article_elem in enumerate(article_elements[:10]):
                try:
                    title_elem = article_elem.select_one(source_config["selectors"]["title"])
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title:
                        continue

                    link_elem = article_elem.select_one(source_config["selectors"]["link"])
                    url = None
                    if link_elem:
                        href = link_elem.get("href")
                        if href and isinstance(href, str):
                            url = urljoin(source_config["url"], href)

                    content = ""
                    if source_config["selectors"]["content"]:
                        content_elem = article_elem.select_one(source_config["selectors"]["content"])
                        if content_elem:
                            content = content_elem.get_text(strip=True)
                    if not content:
                        content = f"News article from {source_name}: {title}"

                    sentiment = self.analyze_sentiment(f"{title} {content}")
                    profit_score = self.calculate_profit_score(
                        title, content, source_config["category"], sentiment=sentiment
                    )
                    source_weight = self.get_source_credibility(source_name)
                    profit_score = self.apply_source_credibility(profit_score, source_name)

                    if profit_score < self.min_profit_score:
                        logger.debug("Skipping low-profit article (%.1f): %s", profit_score, title[:50])
                        continue

                    articles.append(NewsArticleCreate(
                        title=title,
                        content=content,
                        source=source_name,
                        url=url,
                        category=source_config["category"],
                        sentiment=sentiment,
                        profit_score=profit_score,
                        keywords=self.extract_keywords(title, content),
                        source_credibility_weight=source_weight,
                        sentiment_multiplier=self.get_sentiment_multiplier(sentiment),
                    ))
                    logger.info("Scraped article %d: %s...", i + 1, title[:50])
                except Exception as e:
                    logger.error("Error processing article %d from %s: %s", i + 1, source_name, e)
                    continue
        except TimeoutException:
            logger.error("Timeout waiting for articles to load from %s", source_name)
        except WebDriverException as e:
            logger.error("WebDriver error scraping %s: %s", source_name, e)
        except Exception as e:
            logger.error("Unexpected error scraping %s: %s", source_name, e)
        finally:
            if driver:
                driver.quit()

        logger.info("Successfully scraped %d articles from %s", len(articles), source_name)
        return articles

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def scrape_all_sources(self) -> List[NewsArticleCreate]:
        """Scrape all configured sources (RSS/API always; web sources optionally)."""
        all_articles: List[NewsArticleCreate] = []
        web_sources_scraped: List[str] = []

        for source_name, source_config in self.rss_sources.items():
            try:
                if source_config["type"] == "rss":
                    all_articles.extend(self.scrape_rss_feed(source_name, source_config))
                elif source_config["type"] == "api" and "hacker_news" in source_name:
                    all_articles.extend(self.scrape_hacker_news_api())
                await asyncio.sleep(1)  # be respectful
            except Exception as e:
                logger.error("Failed to scrape %s: %s", source_name, e)
                continue

        if self.settings.web_scraping_enabled:
            for source_name in self._registry.web_scraping_priority_sources:
                if source_name in self.news_sources:
                    try:
                        all_articles.extend(self.scrape_source(source_name, self.news_sources[source_name]))
                        web_sources_scraped.append(source_name)
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.error("Failed to scrape %s: %s", source_name, e)
                        continue

        logger.info("Total high-quality articles scraped: %d", len(all_articles))
        self._last_web_sources = web_sources_scraped
        return all_articles

    async def scrape_and_store(self, trigger: str = "manual") -> Dict[str, Any]:
        """Scrape articles and store them in the database.

        Every run — from the API, the scheduler, or a script — writes one audit
        row to ``scrape_runs`` (success or failure) so unattended operation is
        diagnosable from the database alone.
        """
        started_at = timeutil.utcnow()
        try:
            articles = await self.scrape_all_sources()
            db = self._resolve_db()

            stored_count = 0
            skipped_count = 0
            cluster_assignments = 0

            recent_articles: List[Dict[str, Any]] = []
            if self.settings.clustering_enabled:
                recent_articles = db.get_recent_articles(hours=self.settings.clustering_time_window_hours)

            clusterer = self._resolve_clusterer()

            for article in articles:
                try:
                    if self.settings.clustering_enabled:
                        cluster_id = clusterer.find_cluster(article.title, recent_articles)
                        if cluster_id:
                            cluster_assignments += 1
                            logger.info("📎 Clustered: %s → %s", article.title[:50], cluster_id)
                        else:
                            cluster_id = clusterer.new_cluster_id(article.title)
                        article.article_cluster_id = cluster_id

                    result = db.create_article(article)
                    if result:
                        stored_count += 1
                        recent_articles.append({
                            "id": result.id,
                            "title": article.title,
                            "article_cluster_id": article.article_cluster_id,
                            "profit_score": article.profit_score,
                        })
                    else:
                        skipped_count += 1
                        logger.debug("Skipped duplicate: %s", article.title[:50])
                except Exception as e:
                    logger.error("Failed to store article '%s': %s", article.title, e)

            sources_scraped = list(self.rss_sources.keys())
            if getattr(self, "_last_web_sources", None):
                sources_scraped.extend(self._last_web_sources)

            result = {
                "scraped_count": len(articles),
                "stored_count": stored_count,
                "skipped_duplicates": skipped_count,
                "cluster_assignments": cluster_assignments,
                "clustering_enabled": self.settings.clustering_enabled,
                "sources_scraped": sources_scraped,
                "timestamp": timeutil.utcnow().isoformat(),
                "min_profit_threshold": self.min_profit_score,
            }

            logger.info("Scraping completed: %s", result)
            self._record_run(started_at, trigger, "ok", result=result)
            return result
        except Exception as e:
            logger.error("Error in scrape_and_store: %s", e)
            self._record_run(started_at, trigger, "error", error=str(e))
            raise

    def _record_run(
        self,
        started_at: datetime,
        trigger: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Best-effort audit write; never masks the scrape outcome."""
        finished_at = timeutil.utcnow()
        try:
            self._resolve_db().record_scrape_run({
                "started_at": started_at,
                "finished_at": finished_at,
                "trigger": trigger,
                "status": status,
                "scraped_count": (result or {}).get("scraped_count"),
                "stored_count": (result or {}).get("stored_count"),
                "skipped_duplicates": (result or {}).get("skipped_duplicates"),
                "cluster_assignments": (result or {}).get("cluster_assignments"),
                "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
                "sources_scraped": (result or {}).get("sources_scraped"),
                "error": error[:500] if error else None,
            })
        except Exception as audit_err:  # pragma: no cover - defensive
            logger.error("Failed to record scrape run audit row: %s", audit_err)


scraper = NewsScraper()
