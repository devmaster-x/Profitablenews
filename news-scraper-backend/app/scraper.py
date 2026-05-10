import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import requests

from app.models import NewsArticleCreate, NewsCategory, SentimentScore
from app.database import db
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsScraper:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument(f"--headless={str(settings.chrome_headless).lower()}")
        self.chrome_options.add_argument(f"--no-sandbox={str(settings.chrome_no_sandbox).lower()}")
        self.chrome_options.add_argument(f"--disable-dev-shm-usage={str(settings.chrome_disable_dev_shm).lower()}")
        self.chrome_options.add_argument(f"--disable-gpu={str(settings.chrome_disable_gpu).lower()}")
        self.chrome_options.add_argument(f"--window-size={settings.chrome_window_size}")
        self.chrome_options.add_argument(f"--user-agent={settings.user_agent}")
        
        self.news_sources = {
            "techcrunch": {
                "url": "https://techcrunch.com/category/startups/",
                "category": NewsCategory.STARTUP,
                "selectors": {
                    "articles": "article.post-block",
                    "title": "h2.post-block__title a",
                    "link": "h2.post-block__title a",
                    "content": ".post-block__content"
                }
            },
            "hacker_news": {
                "url": "https://news.ycombinator.com/",
                "category": NewsCategory.SOFTWARE,
                "selectors": {
                    "articles": "tr.athing",
                    "title": "span.titleline a",
                    "link": "span.titleline a",
                    "content": ""
                }
            },
            "coindesk": {
                "url": "https://www.coindesk.com/",
                "category": NewsCategory.CRYPTO,
                "selectors": {
                    "articles": "article",
                    "title": "h3 a, h2 a",
                    "link": "h3 a, h2 a",
                    "content": ".at-text"
                }
            },
            "reuters_tech": {
                "url": "https://www.reuters.com/technology/",
                "category": NewsCategory.MARKET,
                "selectors": {
                    "articles": "[data-testid='MediaStoryCard']",
                    "title": "a[data-testid='Heading']",
                    "link": "a[data-testid='Heading']",
                    "content": "[data-testid='Body']"
                }
            },
            "yahoo_finance": {
                "url": "https://finance.yahoo.com/news/",
                "category": NewsCategory.MARKET,
                "selectors": {
                    "articles": "li.js-stream-content",
                    "title": "h3 a",
                    "link": "h3 a",
                    "content": "p"
                }
            },
            "cnbc_tech": {
                "url": "https://www.cnbc.com/technology/",
                "category": NewsCategory.MARKET,
                "selectors": {
                    "articles": "div.Card",
                    "title": "a.Card-title",
                    "link": "a.Card-title",
                    "content": "div.Card-description"
                }
            },
            "venturebeat": {
                "url": "https://venturebeat.com/",
                "category": NewsCategory.STARTUP,
                "selectors": {
                    "articles": "article",
                    "title": "h2 a",
                    "link": "h2 a",
                    "content": "div.ArticleBody-content"
                }
            },
            "cointelegraph": {
                "url": "https://cointelegraph.com/",
                "category": NewsCategory.CRYPTO,
                "selectors": {
                    "articles": "article.post-card",
                    "title": "span.post-card-inline__title",
                    "link": "a.post-card-inline__title",
                    "content": "div.post-card-inline__text"
                }
            },
            "techradar": {
                "url": "https://www.techradar.com/news",
                "category": NewsCategory.SOFTWARE,
                "selectors": {
                    "articles": "div.listingResult",
                    "title": "h3 a",
                    "link": "h3 a",
                    "content": "p.synopsis"
                }
            },
            "seeking_alpha": {
                "url": "https://seekingalpha.com/news",
                "category": NewsCategory.INVESTMENT,
                "selectors": {
                    "articles": "div[data-test-id='post-list-item']",
                    "title": "a[data-test-id='post-list-item-title']",
                    "link": "a[data-test-id='post-list-item-title']",
                    "content": "div[data-test-id='post-list-item-summary']"
                }
            }
        }
    
    def create_driver(self) -> webdriver.Chrome:
        """Create a new Chrome WebDriver instance"""
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.set_page_load_timeout(settings.scraping_timeout)
            return driver
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {e}")
            raise
    
    def analyze_sentiment(self, text: str) -> SentimentScore:
        """Simple sentiment analysis based on keywords"""
        text_lower = text.lower()
        
        positive_keywords = [
            'profit', 'growth', 'increase', 'rise', 'gain', 'success', 'breakthrough',
            'innovation', 'opportunity', 'bullish', 'surge', 'boom', 'expansion',
            'revenue', 'earnings', 'investment', 'funding', 'acquisition', 'ipo'
        ]
        
        negative_keywords = [
            'loss', 'decline', 'fall', 'drop', 'crash', 'failure', 'bankruptcy',
            'layoffs', 'recession', 'bearish', 'downturn', 'crisis', 'scandal',
            'hack', 'breach', 'lawsuit', 'fine', 'penalty', 'shutdown'
        ]
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in text_lower)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text_lower)
        
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
    
    def calculate_profit_score(self, title: str, content: str, category: NewsCategory) -> float:
        """Calculate profit potential score (0-10) based on enhanced content analysis"""
        score = 0.0
        text = f"{title} {content}".lower()
        
        # Base score from category
        category_scores = {
            NewsCategory.MARKET: 3.0,
            NewsCategory.SOFTWARE: 4.0,
            NewsCategory.CRYPTO: 5.0,
            NewsCategory.STARTUP: 4.5,
            NewsCategory.TECH_EARNINGS: 6.0,
            NewsCategory.GENERAL: 2.0,
            NewsCategory.AI_ML: 5.5,
            NewsCategory.BLOCKCHAIN: 5.0,
            NewsCategory.INVESTMENT: 6.5
        }
        score += category_scores.get(category, 2.0)
        
        # Enhanced profit-related keywords with weighted scoring
        profit_keywords = {
            # High-impact financial terms
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
            
            # Crypto/Blockchain terms
            'bitcoin': 1.0, 'ethereum': 1.0, 'blockchain': 1.0, 'defi': 1.5,
            'nft': 1.0, 'cryptocurrency': 1.0, 'token': 0.5, 'smart contract': 1.0,
            
            # Market movement indicators
            'stock market': 1.0, 'market cap': 1.0, 'dividend': 1.0,
            'earnings call': 1.5, 'quarterly results': 1.5, 'guidance': 1.0,
            'analyst': 0.5, 'upgrade': 1.0, 'downgrade': 0.5, 'target price': 1.0,
            
            # Startup/Investment terms
            'venture capital': 1.5, 'series a': 1.0, 'series b': 1.0, 'unicorn': 1.5,
            'startup': 1.0, 'scale': 1.0, 'exit': 1.5, 'valuation': 1.0,
            
            # Regulatory/Policy impact
            'regulation': 0.5, 'policy': 0.5, 'government': 0.5, 'federal': 0.5,
            'sec': 1.0, 'compliance': 0.5, 'legal': 0.5
        }
        
        for keyword, points in profit_keywords.items():
            if keyword in text:
                score += points
        
        # Company mentions (major tech companies with weighted scoring)
        major_companies = {
            # Tier 1: Major tech giants
            'apple': 1.5, 'google': 1.5, 'microsoft': 1.5, 'amazon': 1.5, 
            'tesla': 1.5, 'meta': 1.0, 'facebook': 1.0, 'netflix': 1.0,
            
            # Tier 2: Semiconductor and hardware
            'nvidia': 1.5, 'amd': 1.0, 'intel': 1.0, 'qualcomm': 1.0,
            
            # Tier 3: Enterprise software
            'oracle': 1.0, 'salesforce': 1.0, 'adobe': 1.0, 'sap': 1.0,
            
            # Tier 4: Fintech and payments
            'paypal': 1.0, 'square': 1.0, 'stripe': 1.0, 'visa': 1.0, 'mastercard': 1.0,
            
            # Tier 5: Emerging tech companies
            'airbnb': 1.0, 'uber': 1.0, 'lyft': 1.0, 'zoom': 1.0, 'slack': 1.0,
            'dropbox': 1.0, 'spotify': 1.0, 'twitter': 1.0, 'linkedin': 1.0,
            
            # Tier 6: AI/ML companies
            'openai': 1.5, 'anthropic': 1.0, 'palantir': 1.0, 'databricks': 1.0,
            
            # Tier 7: Crypto companies
            'coinbase': 1.0, 'binance': 1.0, 'kraken': 1.0, 'robinhood': 1.0
        }
        
        for company, points in major_companies.items():
            if company in text:
                score += points
        
        # Time sensitivity (breaking news gets higher score)
        time_keywords = ['breaking', 'just in', 'exclusive', 'announcement', 'launch', 'live']
        if any(keyword in text for keyword in time_keywords):
            score += 1.5
        
        # Market impact indicators
        impact_keywords = ['market', 'industry', 'sector', 'global', 'worldwide', 'international']
        if any(keyword in text for keyword in impact_keywords):
            score += 0.5
        
        # Sentiment boost (positive news gets higher score)
        positive_indicators = ['positive', 'optimistic', 'strong', 'robust', 'excellent', 'outstanding']
        if any(indicator in text for indicator in positive_indicators):
            score += 0.5
        
        # Volume and activity indicators
        volume_keywords = ['volume', 'trading volume', 'active', 'popular', 'trending']
        if any(keyword in text for keyword in volume_keywords):
            score += 0.5
        
        return min(score, 10.0)
    
    def extract_keywords(self, title: str, content: str) -> List[str]:
        """Extract relevant keywords from title and content"""
        text = f"{title} {content}".lower()
        
        keyword_patterns = [
            r'\b(?:ai|artificial intelligence|machine learning|ml)\b',
            r'\b(?:blockchain|bitcoin|ethereum|cryptocurrency|crypto)\b',
            r'\b(?:ipo|acquisition|merger|funding|investment)\b',
            r'\b(?:startup|fintech|biotech|saas)\b',
            r'\b(?:cloud computing|cybersecurity|data analytics)\b',
            r'\b(?:electric vehicle|renewable energy|clean tech)\b',
            r'\b(?:earnings|revenue|profit|growth|market cap)\b'
        ]
        
        keywords = []
        for pattern in keyword_patterns:
            matches = re.findall(pattern, text)
            keywords.extend(matches)
        
        return list(set(keywords))
    
    def scrape_source(self, source_name: str, source_config: Dict[str, Any]) -> List[NewsArticleCreate]:
        """Scrape articles from a single news source"""
        articles = []
        driver = None
        
        try:
            logger.info(f"Scraping {source_name} from {source_config['url']}")
            driver = self.create_driver()
            driver.get(source_config['url'])
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, source_config['selectors']['articles']))
            )
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            article_elements = soup.select(source_config['selectors']['articles'])
            
            logger.info(f"Found {len(article_elements)} articles on {source_name}")
            
            for i, article_elem in enumerate(article_elements[:10]):  # Limit to 10 articles per source
                try:
                    title_elem = article_elem.select_one(source_config['selectors']['title'])
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if not title:
                        continue
                    
                    link_elem = article_elem.select_one(source_config['selectors']['link'])
                    url = None
                    if link_elem:
                        href = link_elem.get('href')
                        if href and isinstance(href, str):
                            url = urljoin(source_config['url'], href)
                    
                    content = ""
                    if source_config['selectors']['content']:
                        content_elem = article_elem.select_one(source_config['selectors']['content'])
                        if content_elem:
                            content = content_elem.get_text(strip=True)
                    
                    if not content:
                        content = f"News article from {source_name}: {title}"
                    
                    sentiment = self.analyze_sentiment(f"{title} {content}")
                    profit_score = self.calculate_profit_score(title, content, source_config['category'])
                    keywords = self.extract_keywords(title, content)
                    
                    article = NewsArticleCreate(
                        title=title,
                        content=content,
                        source=source_name,
                        url=url,
                        category=source_config['category'],
                        sentiment=sentiment,
                        profit_score=profit_score,
                        keywords=keywords
                    )
                    
                    articles.append(article)
                    logger.info(f"Scraped article {i+1}: {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error processing article {i+1} from {source_name}: {e}")
                    continue
        
        except TimeoutException:
            logger.error(f"Timeout waiting for articles to load from {source_name}")
        except WebDriverException as e:
            logger.error(f"WebDriver error scraping {source_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping {source_name}: {e}")
        finally:
            if driver:
                driver.quit()
        
        logger.info(f"Successfully scraped {len(articles)} articles from {source_name}")
        return articles
    
    async def scrape_all_sources(self) -> List[NewsArticleCreate]:
        """Scrape articles from all configured news sources"""
        all_articles = []
        
        for source_name, source_config in self.news_sources.items():
            try:
                articles = self.scrape_source(source_name, source_config)
                all_articles.extend(articles)
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Failed to scrape {source_name}: {e}")
                continue
        
        logger.info(f"Total articles scraped: {len(all_articles)}")
        return all_articles
    
    async def scrape_and_store(self) -> Dict[str, Any]:
        """Scrape articles and store them in the database"""
        try:
            articles = await self.scrape_all_sources()
            
            stored_count = 0
            for article in articles:
                try:
                    db.create_article(article)
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Failed to store article '{article.title}': {e}")
            
            result = {
                "scraped_count": len(articles),
                "stored_count": stored_count,
                "sources_scraped": list(self.news_sources.keys()),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Scraping completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in scrape_and_store: {e}")
            raise

scraper = NewsScraper()
