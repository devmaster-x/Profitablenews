# News Scraper Scoring Redesign - Implementation Plan

## 📋 Executive Summary

**Goal**: Transform the current keyword-based "hype score" into a validated, sentiment-aware profit signal.

**Total Estimated Time**: 12-15 days (full-time) or 3-4 weeks (part-time)

**Team Size**: 1-2 developers

**Risk Level**: Medium (significant refactoring, but with rollback strategy)

---

## 🧰 Implementation Notes & Corrections (v1.1)

This section overrides/corrects the original plan. It was reviewed against the actual codebase (`app/`) and the live `news_scraper.db` on 2026-08-04.

### File target corrections
- **`app/database.py` is a 4-line re-export** of `app/persistent_database.py`. Every "modify `app/database.py`" below means adding methods to the `PersistentDatabase` class in `app/persistent_database.py` (reaching it via `from app.database import db`).
- The web-scraping method is **`scrape_source()`**, not `scrape_website()`. Credibility weight applies in `scrape_rss_feed()`, `scrape_hacker_news_api()`, and `scrape_source()`.

### Verified bugs in original snippets (fixed in this revision)
1. **`schedule.every().month.at("03:00")` crashes** — the `schedule` library (1.2.x) has no `.month` unit. Use an APScheduler `cron` job or a day-of-month guard inside a daily job (see Task 4.4).
2. **`json_each(a.keywords)` crashes on existing data** — keywords are stored comma-joined (`"ethereum,bitcoin"`), not as a JSON array; `json_each` raises "malformed JSON". Store keywords with `json.dumps()` and update analytics queries accordingly (Task 3.6).
3. **`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` is unsupported by SQLite.** Migrations must check `PRAGMA table_info(articles)` and issue a plain `ALTER TABLE` (Task 1.4).
4. **Negation detection must cover contractions** (`wasn't`, `isn't`, `won't`, ...) **and phrases** (`on hold`, `falls through`, `turned down`). The live DB's top-scored article (10.0) is literally a "wasn't a sale" negation case (Task 1.2).
5. **Clustering dedup must store every duplicate as its own row** sharing `article_cluster_id`; `corroboration_count` = `COUNT(*)` per cluster. The original "update first row + skip duplicates" logic crashed with `StopIteration` on the 2nd duplicate and made `/clusters/{cluster_id}` return exactly 1 row (Task 2.3).
6. **Source-credibility map must key on the actual source names** (`coindesk`, `coindesk_rss`, `cointelegraph`, `cointelegraph_rss`, `decrypt`, `decrypt_rss`, `the_block`, `theblock_rss`, `defiant`, `bitcoin_magazine`, `ethereum_foundation`, `web3_news`, `nft_now`, `blockworks`, `bankless`, `hacker_news`, `hacker_news_api`, `techcrunch`, `venturebeat`). `bloomberg`/`reuters`/`wsj`/`financial_times` are not scraped — remove (Task 1.3).
7. **Rate-limit math is off by ~3x.** CoinGecko free tier → ~18 s/article (3 assets × 4 price points × 1.5 s delay) → ~30 min for 100 articles, not "<10 min". Update the Phase 3 perf target and backtest schedule accordingly.
8. **Compute sentiment once per article** and pass it into `calculate_profit_score()`; do not re-run `analyze_sentiment()` inside scoring.
9. **All state-mutating endpoints** (`/optimize/apply`, `/optimize/rollback`) require API-key auth before shipping (Security section).

### Methodological corrections
10. **Excess return, not raw price change.** Price moves are dominated by market beta (BTC). The Phase 3 schema must store `btc_*` reference prices and compute `excess_pct_change_Nh = pct_change_Nh - btc_pct_change_Nh`; all correlation/validation uses excess returns.
11. **Spearman (rank) correlation** (plus score buckets), never `abs(correlation)` as "accuracy" (Task 3.6).
12. **Walk-forward validation** for Phase 4: fit weights on period N-1, evaluate correlation on period N. Never fit and evaluate on the same samples.

### Testing infrastructure (prerequisite for all phases)
13. `tests/` is currently empty and `pyproject.toml` has no dev dependencies. Add `pytest` + `pytest-cov` to dev deps in Phase 1 (Task 1.0) before writing tests.

### Implementation deviations (v1.2, Phase 3)
14. **Plain `requests` instead of `pycoingecko` + `requests-cache`.** One less dependency, direct control over errors; CoinGecko free tier needs no key. The 5-min response cache added little (per-article timestamps are unique).
15. **Series-based price fetching, not 4 point-in-time calls.** One market-chart series per asset covering publish→7d (hourly granularity on the free tier), plus ONE shared BTC reference series per batch. Cuts CoinGecko calls ~4x: a 100-article batch ≈ N×A + 1 calls (~5 min at 1.5s pacing).
16. **Idempotent backtests:** `UNIQUE (article_id, asset_symbol)` + `INSERT OR REPLACE` on `backtest_results`, so re-running jobs never duplicates rows.
17. **Ambiguous tickers excluded from asset extraction** ('link', 'near', 'dot', 'atom', 'uni', 'apt', 'op', 'fil') — they collide with common English words; the project name is matched instead ('chainlink', 'near protocol', ...).

---

## 🎯 Success Metrics

### Before (Current System)
- Manual validation needed for every high-score article
- ~40-50% false positive rate (negative news scoring high)
- No quantitative validation of accuracy
- Static scoring that degrades over time

### After (Target State)
- False positive rate < 10%
- Automated validation via backtesting
- Correlation coefficient > 0.6 between score and 24h price movement
- Self-improving system via feedback loop

---

## 📅 Implementation Phases


### Phase 1: Foundation & Quick Wins (Days 1-3)
**Goal**: Immediate improvement with minimal risk  
**Estimated Time**: 2-3 days  
**Dependencies**: None  
**Risk**: Low

### Phase 2: Deduplication & Clustering (Days 4-6)
**Goal**: Eliminate duplicate opportunities, reward corroboration  
**Estimated Time**: 2-3 days  
**Dependencies**: Phase 1 complete  
**Risk**: Medium (new database schema)

### Phase 3: Backtesting Infrastructure (Days 7-10)
**Goal**: Validate scores against real market outcomes  
**Estimated Time**: 3-4 days  
**Dependencies**: Phase 1 complete  
**Risk**: Low (separate system, doesn't affect production)

### Phase 4: Adaptive Scoring (Days 11-14)
**Goal**: Self-improving system based on validation data  
**Estimated Time**: 3-4 days  
**Dependencies**: Phase 3 data collection (2+ weeks)  
**Risk**: Medium (requires sufficient backtest data)

### Phase 5: Advanced Features (Days 15+)
**Goal**: Event tracking, LLM integration, advanced analytics  
**Estimated Time**: Ongoing  
**Dependencies**: All previous phases  
**Risk**: Low (optional enhancements)

---

## 🔧 Phase 1: Foundation & Quick Wins (Days 1-3)

### Overview
Implement sentiment-weighted scoring, negation detection, and source credibility. These changes provide immediate improvement with minimal code changes.

---

### Task 1.1: Add Sentiment Multiplier to Scoring
**Time**: 2-3 hours  
**Priority**: CRITICAL

**Files to Modify**:
- `app/scraper.py` - Update `calculate_profit_score()` function

**Code Changes**:
```python
# In scraper.py, calculate_profit_score() function

def calculate_profit_score(self, title: str, content: str, category: NewsCategory) -> float:
    # ... existing keyword scoring logic ...
    
    # NEW: Calculate base score first
    base_score = min(score, 10.0)
    
    # NEW: Get sentiment and apply multiplier
    sentiment = self.analyze_sentiment(f"{title} {content}")
    sentiment_multipliers = {
        SentimentScore.VERY_POSITIVE: 1.3,
        SentimentScore.POSITIVE: 1.1,
        SentimentScore.NEUTRAL: 1.0,
        SentimentScore.NEGATIVE: 0.5,
        SentimentScore.VERY_NEGATIVE: 0.2
    }
    
    multiplier = sentiment_multipliers.get(sentiment, 1.0)
    final_score = base_score * multiplier
    
    return min(final_score, 10.0)
```

**Testing**:
- Create test cases with positive/negative articles
- Verify "ETF rejected" scores lower than "ETF approved"
- Check edge cases (neutral sentiment)


---

### Task 1.2: Implement Negation Detection
**Time**: 3-4 hours  
**Priority**: HIGH

**Files to Modify**:
- `app/scraper.py` - Add new helper function

**Code Changes**:
```python
# Add new method to NewsScraper class

def check_negation_context(self, text: str, keyword: str, window: int = 5) -> float:
    """
    Returns 0.0 if keyword is negated, 1.0 if normal.
    Checks if negation words appear within 'window' words of keyword.
    """
    negation_patterns = [
        # Simple negators
        'not', 'no', 'never', 'nor', 'neither',
        # Contractions (critical - the live DB's top article is "wasn't a sale")
        "wasn't", "isn't", "aren't", "weren't", "won't", "wouldn't",
        "can't", "couldn't", "don't", "doesn't", "didn't", "haven't", "hasn't", "ain't",
        # Denial / rejection
        'deny', 'denies', 'denied', 'denial', 'reject', 'rejects', 'rejected', 'rejection', 'rejecting',
        'refuse', 'refuses', 'refused', 'refusal', 'rejections',
        # Failure
        'fail', 'fails', 'failed', 'failure', 'falls through', 'fell through', 'scrapped', 'scraps',
        # Delay / postponement
        'postpone', 'postpones', 'postponed', 'postponement', 'delay', 'delays', 'delayed',
        'defer', 'defers', 'deferred', 'on hold', 'stall', 'stalls', 'stalled', 'stalled out',
        # Cancellation / suspension
        'cancel', 'cancels', 'canceled', 'cancelled', 'cancellation', 'halt', 'halts', 'halted',
        'suspend', 'suspends', 'suspended', 'suspension', 'pause', 'pauses', 'paused',
        # Withdrawal / reversal
        'withdraw', 'withdraws', 'withdrawn', 'withdrawal', 'reverses', 'reversed', 'reversal',
        'abandons', 'abandoned', 'abandonment', 'block', 'blocks', 'blocked', 'rejects etf',
    ]
    
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    kw_tokens = re.findall(r"[a-z0-9']+", keyword_lower)
    if not kw_tokens:
        return 1.0

    words = re.findall(r"[a-z0-9']+", text_lower)

    # Find token-index occurrences of the keyword (multi-word safe)
    k = len(kw_tokens)
    for i in range(len(words) - k + 1):
        if words[i:i + k] == kw_tokens:
            # Check the +/- window (in WORDS, not characters) for a negation phrase
            lo = max(0, i - window)
            hi = min(len(words), i + k + window)
            neighborhood = ' '.join(words[lo:hi])
            for neg_phrase in negation_patterns:
                if neg_phrase in neighborhood:
                    return 0.0  # Keyword is negated

    return 1.0  # Keyword is valid
```

**Integration into keyword scoring**:
```python
# Modify web3_keywords loop in calculate_profit_score()

for keyword, points in web3_keywords.items():
    if keyword in text:
        negation_factor = self.check_negation_context(text, keyword)
        score += points * negation_factor  # Apply negation factor
```

**Testing**:
- Test: "Ethereum partnership" (should score high)
- Test: "Ethereum partnership falls through" (should score low)
- Test: "Bitcoin ETF approved" vs "Bitcoin ETF rejected"


---

### Task 1.3: Add Source Credibility Weighting
**Time**: 2 hours  
**Priority**: HIGH

**Files to Modify**:
- `app/scraper.py` - Add credibility mapping and apply weight
- `app/config.py` - Add source credibility config (optional)

**Code Changes**:
```python
# Add to NewsScraper.__init__() method

self.source_credibility = {
    # Tier 1: Established crypto-native newsrooms
    "coindesk": 1.2,
    "coindesk_rss": 1.2,
    "web3_news": 1.2,          # CoinDesk tech section
    "nft_now": 1.15,           # CoinDesk NFT section
    "the_block": 1.2,
    "theblock_rss": 1.2,
    "ethereum_foundation": 1.15,  # Official protocol blog

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
    "default": 0.9
}

def get_source_credibility(self, source_name: str) -> float:
    """Get credibility weight for a source."""
    return self.source_credibility.get(source_name, self.source_credibility["default"])
```

**Apply in scraping functions**:
```python
# In scrape_rss_feed(), scrape_hacker_news_api(), and scrape_source()

# After calculating profit_score:
source_weight = self.get_source_credibility(source_name)
profit_score = profit_score * source_weight
profit_score = min(profit_score, 10.0)  # Cap at 10

article = NewsArticleCreate(
    ...
    profit_score=profit_score,
    ...
)
```

**Testing**:
- Same article from Bloomberg vs. random blog should score differently
- Verify all source names match dictionary keys (case-sensitive!)


---

### Task 1.4: Update Database Schema (Preparation for Phase 2)
**Time**: 1 hour  
**Priority**: MEDIUM

**Files to Modify**:
- `app/models.py` - Add new fields
- `app/persistent_database.py` - Update table creation + idempotent migration (NOT `app/database.py`; that file is a re-export shim)

**Code Changes**:
```python
# In models.py, add to NewsArticleBase class

class NewsArticleBase(BaseModel):
    # ... existing fields ...
    
    # NEW fields for clustering & corroboration
    article_cluster_id: Optional[str] = Field(None, description="ID for grouped duplicate articles")
    corroboration_count: Optional[int] = Field(default=1, description="Number of sources reporting same event")
    source_credibility_weight: Optional[float] = Field(None, description="Applied credibility weight")
    sentiment_multiplier: Optional[float] = Field(None, description="Applied sentiment multiplier")
```

**Migration Strategy**:
- Add fields as optional (nullable) to avoid breaking existing data
- Default values allow backward compatibility
- **SQLite does NOT support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.** In `PersistentDatabase._init_database()`, read `PRAGMA table_info(articles)` into a set of existing columns and run a plain `ALTER TABLE articles ADD COLUMN <col> <ddl>` for each missing column. New columns are always appended (they do not reorder existing rows).
- Keep `_row_to_article` / INSERT in sync with the final column order.

**Testing**:
- Verify database still works with existing articles
- Test creating new articles with new fields

---

### Task 1.5: Create Test Suite for Phase 1
**Time**: 2 hours  
**Priority**: MEDIUM

**Files to Create**:
- `tests/test_sentiment_scoring.py`
- `tests/test_negation_detection.py`
- `tests/test_source_credibility.py`

**Test Cases**:
```python
# test_sentiment_scoring.py

def test_positive_news_scores_high():
    """'ETF approved' should score higher than 'ETF rejected'"""
    pass

def test_negative_news_scores_low():
    """'Hack drains protocol' should score low despite keywords"""
    pass

def test_neutral_news_baseline():
    """Neutral sentiment should not boost or penalize"""
    pass
```

**Coverage Target**: 80%+ for new functions


---

### Phase 1 Deliverables
- ✅ Sentiment-gated scoring (negative news scores low)
- ✅ Negation detection (context-aware keyword scoring)
- ✅ Source credibility weighting (trust established sources)
- ✅ Updated database schema (ready for clustering)
- ✅ Comprehensive test suite
- ✅ Documentation updates

### Phase 1 Success Criteria
- [ ] All tests pass (80%+ coverage)
- [ ] False positive rate visibly reduced (manual spot-check of 50 articles)
- [ ] No regression in scraping speed (<10% slowdown acceptable)
- [ ] Database migration successful with zero data loss

---

## 🔗 Phase 2: Deduplication & Clustering (Days 4-6)

### Overview
Detect when multiple sources report the same event and group them into a single opportunity with a corroboration score.

---

### Task 2.1: Install Text Similarity Dependencies
**Time**: 30 minutes  
**Priority**: CRITICAL

**Files to Modify**:
- `pyproject.toml` - Add new dependencies

**Dependencies to Add**:
```toml
[tool.poetry.dependencies]
sentence-transformers = "^2.2.0"  # For text embeddings
scikit-learn = "^1.3.0"           # For cosine similarity
rapidfuzz = "^3.5.0"              # For fuzzy string matching
```

**Commands**:
```bash
poetry add sentence-transformers scikit-learn rapidfuzz
```


---

### Task 2.2: Implement Article Clustering Logic
**Time**: 4-5 hours  
**Priority**: HIGH

**Files to Create**:
- `app/clustering.py` - New module for article similarity

**Code Structure**:
```python
# app/clustering.py

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from rapidfuzz import fuzz
from typing import List, Optional
import numpy as np

class ArticleClusterer:
    def __init__(self):
        # Load lightweight model for speed
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        # CORRECTED: 0.6, not 0.75 — calibrated 2026-08-04 against all-MiniLM-L6-v2.
        # Same-event title pairs scored 0.56-0.84; different events scored <= 0.23.
        # 0.75 only catches near-identical wording (which exact-dup already handles);
        # 0.6 catches real paraphrases with a >2x safety margin.
        self.similarity_threshold = 0.6
        
    def compute_similarity(self, title1: str, title2: str) -> float:
        """
        Compute similarity between two titles using embeddings.
        Returns 0.0-1.0 score.
        """
        embeddings = self.model.encode([title1, title2])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        return float(similarity)
    
    def fuzzy_match(self, title1: str, title2: str) -> float:
        """Fallback to fuzzy string matching (faster, less accurate)."""
        return fuzz.ratio(title1.lower(), title2.lower()) / 100.0
    
    def find_cluster(self, new_article_title: str, 
                    existing_articles: List[dict], 
                    time_window_hours: int = 12) -> Optional[str]:
        """
        Find if new article belongs to existing cluster.
        Returns cluster_id if match found, None otherwise.
        
        Args:
            new_article_title: Title of new article
            existing_articles: List of recent articles within time window
            time_window_hours: How far back to check for clusters
        """
        for article in existing_articles:
            similarity = self.compute_similarity(
                new_article_title, 
                article['title']
            )
            
            if similarity >= self.similarity_threshold:
                return article.get('article_cluster_id') or article['id']
        
        return None  # No cluster found, new cluster

clusterer = ArticleClusterer()
```


---

### Task 2.3: Integrate Clustering into Scraper
**Time**: 3-4 hours  
**Priority**: HIGH

**Files to Modify**:
- `app/scraper.py` - Update scraping functions
- `app/database.py` - Add cluster lookup/update methods

**Database Methods**:
```python
# In app/persistent_database.py, add to PersistentDatabase class
# (reachable via `from app.database import db`). NOTE: there is no get_connection();
# the class opens sqlite3.connect(self.db_path) directly.

def get_recent_articles(self, hours: int = 12) -> List[dict]:
    """Get articles from last N hours for clustering."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, title, article_cluster_id, profit_score
            FROM articles 
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,)).fetchall()
        return [dict(row) for row in rows]

def get_cluster_articles(self, cluster_id: str) -> List[dict]:
    """All articles in a cluster + corroboration count + boosted score."""
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, title, source, url, profit_score, created_at
            FROM articles WHERE article_cluster_id = ?
            ORDER BY created_at
        """, (cluster_id,)).fetchall()
        return [dict(row) for row in rows]

def get_clusters(self, min_corroboration: int = 2, limit: int = 20) -> List[dict]:
    """Grouped clusters with corroboration count; score is derived, not stored."""
    corroboration_multipliers = {1: 1.0, 2: 1.15, 3: 1.15, 4: 1.3}
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT article_cluster_id,
                   COUNT(*)                                  AS corroboration_count,
                   MAX(profit_score)                         AS cluster_score
            FROM articles
            WHERE article_cluster_id IS NOT NULL
            GROUP BY article_cluster_id
            -- NB: use COUNT(*), NOT the alias: the table has a real column named
            -- 'corroboration_count' (Phase 1), and SQLite resolves the bare name
            -- to the column (always 1) over the aggregate alias.
            HAVING COUNT(*) >= ?
            ORDER BY corroboration_count DESC, cluster_score DESC
            LIMIT ?
        """, (min_corroboration, limit)).fetchall()
        clusters = []
        for row in rows:
            multiplier = corroboration_multipliers.get(row['corroboration_count'], 1.3)
            clusters.append({
                'cluster_id': row['article_cluster_id'],
                'corroboration_count': row['corroboration_count'],
                'cluster_score': min(10.0, (row['cluster_score'] or 0.0) * multiplier),
            })
        return clusters
```

**Scraper Integration**:
```python
# In app/scraper.py, before storing each article

from app.clustering import clusterer

# After calculating profit_score, before creating article:

# Check for existing cluster
recent_articles = db.get_recent_articles(hours=12)
cluster_id = clusterer.find_cluster(title, recent_articles)

if cluster_id:
    # CORRECTED: store EVERY duplicate as its own row sharing article_cluster_id.
    # corroboration_count = COUNT(*) per cluster (computed in SQL, never a stored counter).
    # This fixes the v1 bug where duplicates were skipped with `continue`, which
    # made /clusters/{cluster_id} return exactly one row.
    article = NewsArticleCreate(
        ...
        article_cluster_id=cluster_id,
        corroboration_count=1,  # per-row placeholder; real count comes from the cluster query
        ...
    )
    db.create_article(article)

    # Corroboration bonus is derived in the /clusters query, not stored on rows:
    #   SELECT COUNT(*) AS corroboration_count, MAX(profit_score) AS cluster_score
    #   FROM articles WHERE article_cluster_id = ? GROUP BY article_cluster_id
    #   -- score boost: min(10.0, cluster_score * {1.0,1.15,1.15,1.3}[corroboration_count])

else:
    # New cluster - create article normally
    article_cluster_id = hashlib.md5(title.encode()).hexdigest()[:12]
    
    article = NewsArticleCreate(
        ...
        article_cluster_id=article_cluster_id,
        corroboration_count=1,
        ...
    )
```


---

### Task 2.4: Add Cluster Visualization to API
**Time**: 2 hours  
**Priority**: MEDIUM

**Files to Modify**:
- `app/main.py` - Add new endpoint

**New Endpoints**:
```python
# In app/main.py

@app.get("/clusters")
async def get_article_clusters(
    min_corroboration: int = Query(2, ge=1, description="Minimum sources"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get article clusters with multiple source corroboration."""
    try:
        clusters = db.get_clusters(min_corroboration, limit)
        return {
            "clusters": clusters,
            "count": len(clusters)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/clusters/{cluster_id}")
async def get_cluster_details(cluster_id: str):
    """Get all articles in a specific cluster."""
    try:
        articles = db.get_cluster_articles(cluster_id)
        if not articles:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return {
            "cluster_id": cluster_id,
            "articles": articles,
            "corroboration_count": len(articles)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

### Task 2.5: Performance Optimization
**Time**: 2-3 hours  
**Priority**: MEDIUM

**Optimizations**:

1. **Cache embeddings** (avoid recomputing for same titles):
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_embedding(title: str) -> np.ndarray:
    return clusterer.model.encode(title)
```

2. **Limit clustering window** (only check last 12h, not entire DB)

3. **Early exit on fuzzy match** (if <50% string similarity, skip embedding)

4. **Batch processing** (compute embeddings for multiple articles at once)

**Performance Target**: 
- Clustering adds <200ms per article
- Total scraping time increase <20%


---

### Phase 2 Deliverables
- ✅ Article clustering using sentence embeddings
- ✅ Corroboration multiplier (1.0x → 1.3x for 4+ sources)
- ✅ Deduplication (same event = one opportunity, not five)
- ✅ Cluster visualization API endpoints
- ✅ Performance optimizations (caching, batching)

### Phase 2 Success Criteria
- [ ] Duplicate articles reduced by 60-80%
- [ ] Multi-source stories correctly clustered
- [ ] API returns cluster info with corroboration counts
- [ ] Scraping performance impact <20%

---

## 📊 Phase 3: Backtesting Infrastructure (Days 7-10)

### Overview
Build system to validate profit scores against actual market outcomes. This is the foundation for continuous improvement.

---

### Task 3.1: Create Backtest Database Schema
**Time**: 1-2 hours  
**Priority**: CRITICAL

**Files to Modify**:
- `app/models.py` - Add backtest models
- `app/database.py` - Create backtest tables

**New Models**:
```python
# In app/models.py

from enum import Enum

class AssetType(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    INDEX = "index"

class BacktestResult(BaseModel):
    id: int
    article_id: int
    asset_symbol: str  # e.g., "BTC", "ETH", "COIN"
    asset_type: AssetType
    predicted_score: float
    
    # Prices
    price_at_publish: Optional[float]
    price_1h: Optional[float]
    price_24h: Optional[float]
    price_7d: Optional[float]
    
    # Percentage changes
    pct_change_1h: Optional[float]
    pct_change_24h: Optional[float]
    pct_change_7d: Optional[float]
    
    # Market reference (BTC) prices & changes for EXCESS-RETURN validation.
    # Raw price change is dominated by market beta; validation uses:
    #   excess_pct_change_Nh = pct_change_Nh - btc_pct_change_Nh
    btc_pct_change_1h: Optional[float]
    btc_pct_change_24h: Optional[float]
    btc_pct_change_7d: Optional[float]
    
    # Metadata
    created_at: datetime
    backtested_at: datetime
    data_source: str  # "coingecko", "yahoo_finance", etc.
    
    class Config:
        from_attributes = True
```

**Database Table**:
```sql
CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    asset_symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    predicted_score REAL NOT NULL,
    
    price_at_publish REAL,
    price_1h REAL,
    price_24h REAL,
    price_7d REAL,
    
    pct_change_1h REAL,
    pct_change_24h REAL,
    pct_change_7d REAL,
    
    btc_pct_change_1h REAL,
    btc_pct_change_24h REAL,
    btc_pct_change_7d REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    backtested_at TIMESTAMP,
    data_source TEXT,
    
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX idx_backtest_article ON backtest_results(article_id);
CREATE INDEX idx_backtest_symbol ON backtest_results(asset_symbol);
```


---

### Task 3.2: Implement Asset Extraction from Articles
**Time**: 2-3 hours  
**Priority**: HIGH

**Files to Create**:
- `app/asset_extractor.py` - New module

**Code Structure**:
```python
# app/asset_extractor.py

from typing import List, Dict
import re

class AssetExtractor:
    def __init__(self):
        # Map keywords to tradeable assets
        self.asset_mapping = {
            # Cryptocurrencies
            'bitcoin': {'symbol': 'bitcoin', 'type': 'crypto', 'coingecko_id': 'bitcoin'},
            'btc': {'symbol': 'bitcoin', 'type': 'crypto', 'coingecko_id': 'bitcoin'},
            'ethereum': {'symbol': 'ethereum', 'type': 'crypto', 'coingecko_id': 'ethereum'},
            'eth': {'symbol': 'ethereum', 'type': 'crypto', 'coingecko_id': 'ethereum'},
            'solana': {'symbol': 'solana', 'type': 'crypto', 'coingecko_id': 'solana'},
            'sol': {'symbol': 'solana', 'type': 'crypto', 'coingecko_id': 'solana'},
            'cardano': {'symbol': 'cardano', 'type': 'crypto', 'coingecko_id': 'cardano'},
            'ada': {'symbol': 'cardano', 'type': 'crypto', 'coingecko_id': 'cardano'},
            # ... add top 50-100 cryptos
            
            # Stocks (companies mentioned in crypto space)
            'coinbase': {'symbol': 'COIN', 'type': 'stock', 'yahoo_symbol': 'COIN'},
            'microstrategy': {'symbol': 'MSTR', 'type': 'stock', 'yahoo_symbol': 'MSTR'},
            'nvidia': {'symbol': 'NVDA', 'type': 'stock', 'yahoo_symbol': 'NVDA'},
            'tesla': {'symbol': 'TSLA', 'type': 'stock', 'yahoo_symbol': 'TSLA'},
            # ... add major tech stocks
        }
    
    def extract_assets(self, title: str, content: str, keywords: List[str]) -> List[Dict]:
        """
        Extract tradeable assets mentioned in article.
        Returns list of asset dicts with symbol, type, and API identifier.
        """
        text = f"{title} {content}".lower()
        found_assets = []
        
        # Check keywords first (already extracted)
        for keyword in keywords:
            if keyword.lower() in self.asset_mapping:
                asset = self.asset_mapping[keyword.lower()]
                if asset not in found_assets:
                    found_assets.append(asset)
        
        # Also scan full text for asset names
        for asset_name, asset_info in self.asset_mapping.items():
            if re.search(r'\b' + asset_name + r'\b', text):
                if asset_info not in found_assets:
                    found_assets.append(asset_info)
        
        # Limit to top 3 most relevant assets per article
        return found_assets[:3]

asset_extractor = AssetExtractor()
```


---

### Task 3.3: Implement Price Fetching (CoinGecko API)
**Time**: 3-4 hours  
**Priority**: HIGH

**Files to Create**:
- `app/price_fetcher.py` - New module

**Dependencies**:
```bash
poetry add pycoingecko requests-cache
```

**Code Structure**:
```python
# app/price_fetcher.py

from pycoingecko import CoinGeckoAPI
from datetime import datetime, timedelta
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)

class PriceFetcher:
    def __init__(self):
        self.cg = CoinGeckoAPI()
        self.rate_limit_delay = 1.5  # CoinGecko free tier: ~50 calls/min
        
    def get_price_at_time(self, 
                         coingecko_id: str, 
                         timestamp: datetime) -> Optional[float]:
        """
        Fetch historical price for asset at specific timestamp.
        CoinGecko only provides 5-min granularity for free tier.
        """
        try:
            # Convert to Unix timestamp
            unix_time = int(timestamp.timestamp())
            
            # Get historical data (need date range)
            from_timestamp = unix_time - 3600  # 1h before
            to_timestamp = unix_time + 3600    # 1h after
            
            data = self.cg.get_coin_market_chart_range_by_id(
                id=coingecko_id,
                vs_currency='usd',
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp
            )
            
            if not data or 'prices' not in data or not data['prices']:
                logger.warning(f"No price data for {coingecko_id} at {timestamp}")
                return None
            
            # Find closest price to target timestamp
            prices = data['prices']
            closest_price = min(prices, key=lambda x: abs(x[0]/1000 - unix_time))
            
            time.sleep(self.rate_limit_delay)  # Rate limiting
            return closest_price[1]
            
        except Exception as e:
            logger.error(f"Failed to fetch price for {coingecko_id}: {e}")
            return None
    
    def get_current_price(self, coingecko_id: str) -> Optional[float]:
        """Get current price (simpler, faster)."""
        try:
            data = self.cg.get_price(ids=coingecko_id, vs_currencies='usd')
            return data.get(coingecko_id, {}).get('usd')
        except Exception as e:
            logger.error(f"Failed to fetch current price for {coingecko_id}: {e}")
            return None

price_fetcher = PriceFetcher()
```

**Alternative: Use local caching to reduce API calls**:
```python
import requests_cache

# Cache responses for 5 minutes
requests_cache.install_cache('coingecko_cache', expire_after=300)
```


---

### Task 3.4: Create Backtesting Job Scheduler
**Time**: 3-4 hours  
**Priority**: HIGH

**Files to Create**:
- `app/backtester.py` - New module

**Code Structure**:
```python
# app/backtester.py

from datetime import datetime, timedelta
from typing import List
import asyncio
import logging

from app.database import db
from app.asset_extractor import asset_extractor
from app.price_fetcher import price_fetcher
from app.models import BacktestResult, AssetType

logger = logging.getLogger(__name__)

class Backtester:
    def __init__(self):
        self.backtest_windows = [1, 24, 168]  # 1h, 24h, 7d in hours
        
    async def backtest_article(self, article_id: int):
        """
        Backtest a single article against price movements.
        Should be called 24h-7d after article publication.
        """
        try:
            article = db.get_article(article_id)
            if not article:
                logger.warning(f"Article {article_id} not found")
                return
            
            # Extract assets from article
            assets = asset_extractor.extract_assets(
                article.title,
                article.content,
                article.keywords or []
            )
            
            if not assets:
                logger.info(f"No tradeable assets found in article {article_id}")
                return
            
            # For each asset, fetch prices and calculate changes
            for asset in assets:
                if asset['type'] != 'crypto':
                    continue  # Start with crypto only, add stocks later
                
                coingecko_id = asset['coingecko_id']
                
                # Get price at publish time
                price_at_publish = price_fetcher.get_price_at_time(
                    coingecko_id,
                    article.created_at
                )
                
                if not price_at_publish:
                    continue
                
                # Get prices at intervals
                price_1h = price_fetcher.get_price_at_time(
                    coingecko_id,
                    article.created_at + timedelta(hours=1)
                )
                
                price_24h = price_fetcher.get_price_at_time(
                    coingecko_id,
                    article.created_at + timedelta(hours=24)
                )
                
                price_7d = price_fetcher.get_price_at_time(
                    coingecko_id,
                    article.created_at + timedelta(days=7)
                )
                
                # Calculate percentage changes
                pct_1h = ((price_1h - price_at_publish) / price_at_publish * 100) if price_1h else None
                pct_24h = ((price_24h - price_at_publish) / price_at_publish * 100) if price_24h else None
                pct_7d = ((price_7d - price_at_publish) / price_at_publish * 100) if price_7d else None
                
                # CORRECTED: fetch BTC reference once per batch and compute
                # btc_pct_change_* so validation can use EXCESS returns.
                #   excess_pct_change_24h = pct_24h - btc_pct_change_24h
                btc_pct_1h, btc_pct_24h, btc_pct_7d = self.get_btc_reference_changes(
                    article.created_at, article.created_at, article.created_at
                )
                
                # Store backtest result
                db.store_backtest_result({
                    'article_id': article_id,
                    'asset_symbol': asset['symbol'],
                    'asset_type': asset['type'],
                    'predicted_score': article.profit_score,
                    'price_at_publish': price_at_publish,
                    'price_1h': price_1h,
                    'price_24h': price_24h,
                    'price_7d': price_7d,
                    'pct_change_1h': pct_1h,
                    'pct_change_24h': pct_24h,
                    'pct_change_7d': pct_7d,
                    'btc_pct_change_1h': btc_pct_1h,
                    'btc_pct_change_24h': btc_pct_24h,
                    'btc_pct_change_7d': btc_pct_7d,
                    'backtested_at': datetime.utcnow(),
                    'data_source': 'coingecko'
                })
                
                logger.info(
                    f"✓ Backtested {article.title[:40]} | "
                    f"{asset['symbol']}: {pct_24h:+.2f}% (24h)"
                )
                
        except Exception as e:
            logger.error(f"Backtest failed for article {article_id}: {e}")
    
    async def backtest_batch(self, hours_ago: int = 24):
        """
        Backtest all articles from N hours ago.
        Run this job daily.
        """
        cutoff_start = datetime.utcnow() - timedelta(hours=hours_ago + 1)
        cutoff_end = datetime.utcnow() - timedelta(hours=hours_ago)
        
        articles = db.get_articles_in_timerange(cutoff_start, cutoff_end)
        
        logger.info(f"Backtesting {len(articles)} articles from {hours_ago}h ago")
        
        for article in articles:
            await self.backtest_article(article['id'])
            await asyncio.sleep(2)  # Rate limiting

backtester = Backtester()
```


---

### Task 3.5: Add Backtesting to Scheduler
**Time**: 1-2 hours  
**Priority**: HIGH

**Files to Modify**:
- `app/scheduler.py` - Add backtest jobs

**Code Changes**:
```python
# In app/scheduler.py

from app.backtester import backtester

class NewsScrapingScheduler:
    def __init__(self):
        # ... existing code ...
        
        # NEW: Backtest configuration
        self.backtest_enabled = True
        self.backtest_times = ["02:00", "14:00"]  # Run twice daily
    
    def schedule_daily_scraping(self):
        """Schedule scraper and backtester"""
        schedule.clear()
        
        # Existing scraping job
        schedule.every().day.at(settings.default_scraping_time).do(
            self._run_scraping_job
        )
        
        # NEW: Backtest jobs
        if self.backtest_enabled:
            # Backtest articles from 24h ago
            schedule.every().day.at(self.backtest_times[0]).do(
                self._run_backtest_job, hours_ago=24
            )
            
            # Backtest articles from 7d ago
            schedule.every().day.at(self.backtest_times[1]).do(
                self._run_backtest_job, hours_ago=168
            )
        
        logger.info("Scheduled scraping and backtesting jobs")
    
    def _run_backtest_job(self, hours_ago: int):
        """Execute backtesting job"""
        logger.info(f"Starting backtest job for articles from {hours_ago}h ago")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(backtester.backtest_batch(hours_ago))
            
            logger.info("Backtest job completed successfully")
            
        except Exception as e:
            logger.error(f"Backtest job failed: {e}")
        finally:
            loop.close()
```


---

### Task 3.6: Create Analytics Dashboard API
**Time**: 3-4 hours  
**Priority**: MEDIUM

**Files to Modify**:
- `app/main.py` - Add backtest analytics endpoints
- `app/database.py` - Add analytics queries

**New Endpoints**:
```python
# In app/main.py

@app.get("/backtest/accuracy")
async def get_backtest_accuracy(
    time_window: str = Query("24h", description="1h, 24h, or 7d"),
    min_samples: int = Query(10, description="Minimum samples required")
):
    """
    Get correlation between profit scores and actual price movements.
    Returns accuracy metrics for the scoring system.
    """
    try:
        stats = db.get_backtest_accuracy(time_window, min_samples)
        return {
            "time_window": time_window,
            "correlation": stats.get('correlation'),
            "p_value": stats.get('p_value'),
            "total_samples": stats.get('total_samples'),
            "avg_predicted_score": stats.get('avg_predicted'),
            "avg_excess_movement": stats.get('avg_actual'),
            "score_buckets": stats.get('score_buckets')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/backtest/keywords")
async def get_keyword_performance(
    limit: int = Query(50, description="Top N keywords")
):
    """
    Get keyword performance based on backtest data.
    Shows which keywords correlate with actual price movements.
    """
    try:
        keywords = db.get_keyword_performance(limit)
        return {
            "keywords": keywords,
            "count": len(keywords)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/backtest/sources")
async def get_source_accuracy():
    """
    Get accuracy metrics per source.
    Helps validate source credibility weights.
    """
    try:
        sources = db.get_source_accuracy()
        return {
            "sources": sources,
            "count": len(sources)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Database Analytics Methods**:
```python
# In app/database.py

def get_backtest_accuracy(self, time_window: str, min_samples: int) -> dict:
    """Correlation between predicted scores and EXCESS returns (rank-based)."""

    # CORRECTED: validation uses excess return vs market (BTC), and Spearman
    # rank correlation. Raw pct_change is dominated by market beta, and
    # abs(correlation) as "accuracy" is not a valid metric.
    window_map = {
        '1h': ('pct_change_1h', 'btc_pct_change_1h'),
        '24h': ('pct_change_24h', 'btc_pct_change_24h'),
        '7d': ('pct_change_7d', 'btc_pct_change_7d'),
    }
    col, btc_col = window_map.get(time_window, ('pct_change_24h', 'btc_pct_change_24h'))

    with self.get_connection() as conn:
        cursor = conn.execute(f"""
            SELECT 
                predicted_score,
                ({col} - {btc_col}) as excess_movement
            FROM backtest_results
            WHERE {col} IS NOT NULL AND {btc_col} IS NOT NULL
        """)

        data = cursor.fetchall()

        if len(data) < min_samples:
            return {'error': 'Insufficient data', 'total_samples': len(data)}

        import numpy as np
        from scipy.stats import spearmanr

        predicted = [row[0] for row in data]
        actual = [row[1] for row in data]

        # CORRECTED: Spearman (rank) — robust to the skewed 4-10 score distribution
        correlation, p_value = spearmanr(predicted, actual)

        buckets = self._calculate_score_buckets(predicted, actual)

        return {
            'correlation': float(correlation),
            'p_value': float(p_value),
            'total_samples': len(data),
            'avg_predicted': float(np.mean(predicted)),
            'avg_actual': float(np.mean(actual)),
            'score_buckets': buckets
        }

def _calculate_score_buckets(self, predicted: list, actual: list) -> dict:
    """Group scores into buckets and calculate average outcome per bucket."""
    import numpy as np
    
    buckets = {
        '0-2': [], '2-4': [], '4-6': [], '6-8': [], '8-10': []
    }
    
    for pred, act in zip(predicted, actual):
        if pred < 2:
            buckets['0-2'].append(act)
        elif pred < 4:
            buckets['2-4'].append(act)
        elif pred < 6:
            buckets['4-6'].append(act)
        elif pred < 8:
            buckets['6-8'].append(act)
        else:
            buckets['8-10'].append(act)
    
    return {
        bucket: {
            'avg_movement': float(np.mean(movements)) if movements else 0,
            'count': len(movements)
        }
        for bucket, movements in buckets.items()
    }

def get_keyword_performance(self, limit: int) -> list:
    """Get keywords ranked by backtest performance."""
    
    with self.get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                keyword,
                COUNT(*) as appearances,
                AVG(br.pct_change_24h - br.btc_pct_change_24h) as avg_24h_excess_movement,
                AVG(a.profit_score) as avg_score
            FROM articles a
            JOIN backtest_results br ON a.id = br.article_id
            CROSS JOIN json_each(a.keywords) AS keyword
            WHERE br.pct_change_24h IS NOT NULL AND br.btc_pct_change_24h IS NOT NULL
            GROUP BY keyword
            HAVING COUNT(*) >= 5
            ORDER BY avg_24h_excess_movement DESC
            LIMIT ?
        """, (limit,))
        
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def get_source_accuracy(self) -> list:
    """Get accuracy metrics per source."""
    
    with self.get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                a.source,
                COUNT(*) as total_articles,
                AVG(a.profit_score) as avg_predicted_score,
                AVG(br.pct_change_24h - br.btc_pct_change_24h) as avg_24h_excess_movement,
                AVG(CASE 
                    WHEN (a.profit_score > 7 AND (br.pct_change_24h - br.btc_pct_change_24h) > 5) OR
                         (a.profit_score < 4 AND (br.pct_change_24h - br.btc_pct_change_24h) < 0)
                    THEN 1.0 ELSE 0.0 
                END) as accuracy_rate
            FROM articles a
            JOIN backtest_results br ON a.id = br.article_id
            WHERE br.pct_change_24h IS NOT NULL AND br.btc_pct_change_24h IS NOT NULL
            GROUP BY a.source
            HAVING COUNT(*) >= 5
            ORDER BY accuracy_rate DESC
        """)
        
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```


---

### Phase 3 Deliverables
- ✅ Backtest database schema with price tracking
- ✅ Asset extraction from article keywords
- ✅ CoinGecko API integration for price data
- ✅ Automated backtesting jobs (24h/7d schedules)
- ✅ Analytics API endpoints (accuracy, keywords, sources)
- ✅ Foundation for data-driven improvements

### Phase 3 Success Criteria
- [ ] Backtesting runs automatically daily
- [ ] Price data successfully fetched for 80%+ of articles with crypto mentions
- [ ] Analytics dashboard shows correlation metrics
- [ ] At least 100 backtested articles before Phase 4
- [ ] API returns meaningful accuracy statistics

### Phase 3 Data Collection Period
**IMPORTANT**: Phase 4 requires 2-4 weeks of backtest data collection before proceeding.

During this period:
- Monitor backtest job execution (check logs)
- Verify price data quality (check for nulls/errors)
- Review preliminary correlation metrics
- Fix any API rate limiting issues
- Expand asset mapping as needed

---

## 🤖 Phase 4: Adaptive Scoring (Days 11-14)

### Overview
Use backtest data to automatically tune keyword weights and scoring parameters. This phase transforms the system from static to self-improving.

**Prerequisites**: 
- ✅ Phase 3 complete
- ✅ 100+ articles backtested (minimum)
- ✅ 2+ weeks of data collection

---

### Task 4.1: Build Weight Optimization Engine
**Time**: 4-5 hours  
**Priority**: HIGH

**Files to Create**:
- `app/optimizer.py` - New module for weight tuning

**Code Structure**:
```python
# app/optimizer.py

import numpy as np
from sklearn.linear_model import Ridge, Lasso
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class ScoreOptimizer:
    def __init__(self):
        self.min_samples = 100  # Minimum articles needed for reliable optimization
        self.regularization_alpha = 0.1  # Prevent overfitting
        
    def analyze_keyword_correlations(self) -> Dict[str, float]:
        """
        Analyze which keywords correlate with positive price movements.
        Returns suggested weight adjustments.
        """
        from app.database import db
        
        # Get all backtested articles with keywords
        backtest_data = db.get_backtest_training_data()
        
        if len(backtest_data) < self.min_samples:
            logger.warning(
                f"Insufficient data for optimization: {len(backtest_data)} samples "
                f"(need {self.min_samples})"
            )
            return {}
        
        # Build feature matrix: [n_articles × n_keywords] binary matrix
        all_keywords = set()
        for article in backtest_data:
            all_keywords.update(article['keywords'])
        
        all_keywords = sorted(list(all_keywords))
        keyword_to_idx = {kw: idx for idx, kw in enumerate(all_keywords)}
        
        # Create binary feature matrix
        X = np.zeros((len(backtest_data), len(all_keywords)))
        y = np.array([article['pct_change_24h'] for article in backtest_data])
        
        for i, article in enumerate(backtest_data):
            for keyword in article['keywords']:
                if keyword in keyword_to_idx:
                    X[i, keyword_to_idx[keyword]] = 1
        
        # Fit regularized regression to prevent overfitting
        model = Ridge(alpha=self.regularization_alpha)
        model.fit(X, y)
        
        # Extract keyword coefficients (weights)
        coefficients = model.coef_
        
        # Convert to weight adjustments
        adjustments = {}
        for keyword, idx in keyword_to_idx.items():
            coef = coefficients[idx]
            
            # Only suggest changes if effect is significant
            if abs(coef) > 0.5:  # Threshold for significance
                # Convert coefficient to multiplier adjustment
                # Positive coef → increase weight, negative → decrease
                if coef > 0:
                    adjustments[keyword] = min(1.3, 1.0 + coef * 0.1)
                else:
                    adjustments[keyword] = max(0.7, 1.0 + coef * 0.1)
        
        logger.info(f"Generated {len(adjustments)} weight adjustment suggestions")
        return adjustments
    
    def optimize_sentiment_multipliers(self) -> Dict[str, float]:
        """
        Analyze if sentiment multipliers are calibrated correctly.
        Returns suggested multiplier adjustments.
        """
        from app.database import db
        
        sentiment_performance = db.get_sentiment_performance()
        
        suggestions = {}
        for sentiment, stats in sentiment_performance.items():
            if stats['count'] < 20:  # Need sufficient samples
                continue
            
            avg_movement = stats['avg_movement']
            current_multiplier = stats['current_multiplier']
            
            # Calculate optimal multiplier based on actual outcomes
            # Normalize to neutral (1.0) baseline
            if avg_movement > 5:  # Strong positive average
                suggestions[sentiment] = min(1.5, current_multiplier * 1.1)
            elif avg_movement < -5:  # Strong negative average
                suggestions[sentiment] = max(0.1, current_multiplier * 0.9)
        
        return suggestions
    
    def generate_optimization_report(self) -> dict:
        """
        Generate comprehensive optimization report.
        Shows what should be adjusted and why.
        """
        keyword_adjustments = self.analyze_keyword_correlations()
        sentiment_adjustments = self.optimize_sentiment_multipliers()
        
        from app.database import db
        accuracy_stats = db.get_backtest_accuracy('24h', min_samples=50)
        
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'samples_analyzed': accuracy_stats.get('total_samples', 0),
            'current_correlation': accuracy_stats.get('correlation', 0),
            'keyword_adjustments': keyword_adjustments,
            'sentiment_adjustments': sentiment_adjustments,
            'top_performing_keywords': self._get_top_keywords(keyword_adjustments, n=10),
            'worst_performing_keywords': self._get_bottom_keywords(keyword_adjustments, n=10),
            'recommendations': self._generate_recommendations(
                keyword_adjustments, 
                sentiment_adjustments,
                accuracy_stats
            )
        }
        
        return report
    
    def _get_top_keywords(self, adjustments: dict, n: int) -> list:
        """Get top N keywords by suggested weight increase."""
        sorted_kw = sorted(adjustments.items(), key=lambda x: x[1], reverse=True)
        return [{'keyword': kw, 'multiplier': mult} for kw, mult in sorted_kw[:n]]
    
    def _get_bottom_keywords(self, adjustments: dict, n: int) -> list:
        """Get bottom N keywords by suggested weight decrease."""
        sorted_kw = sorted(adjustments.items(), key=lambda x: x[1])
        return [{'keyword': kw, 'multiplier': mult} for kw, mult in sorted_kw[:n]]
    
    def _generate_recommendations(self, keyword_adj: dict, 
                                  sentiment_adj: dict, 
                                  accuracy: dict) -> list:
        """Generate human-readable recommendations."""
        recommendations = []
        
        correlation = accuracy.get('correlation', 0)
        if correlation < 0.3:
            recommendations.append({
                'priority': 'HIGH',
                'message': f'Low correlation ({correlation:.2f}). Consider manual review of scoring logic.'
            })
        
        if len(keyword_adj) > 50:
            recommendations.append({
                'priority': 'MEDIUM',
                'message': f'{len(keyword_adj)} keywords suggested for adjustment. Review top 20 first.'
            })
        
        if sentiment_adj:
            recommendations.append({
                'priority': 'MEDIUM',
                'message': f'Sentiment multipliers may need recalibration. Review {len(sentiment_adj)} adjustments.'
            })
        
        return recommendations

optimizer = ScoreOptimizer()
```


---

### Task 4.2: Create Weight Update System
**Time**: 3-4 hours  
**Priority**: HIGH

**Files to Create**:
- `app/weight_manager.py` - Manage keyword weights dynamically

**Code Structure**:
```python
# app/weight_manager.py

import json
from pathlib import Path
from datetime import datetime
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class WeightManager:
    def __init__(self):
        self.weights_file = Path("data/keyword_weights.json")
        self.history_file = Path("data/weight_history.json")
        self.weights_file.parent.mkdir(exist_ok=True)
        
        # Load current weights or initialize
        self.keyword_weights = self._load_weights()
        self.weight_history = self._load_history()
    
    def _load_weights(self) -> Dict[str, float]:
        """Load current keyword weights from file."""
        if self.weights_file.exists():
            with open(self.weights_file, 'r') as f:
                return json.load(f)
        else:
            # Initialize with empty dict (will use defaults from scraper.py)
            return {}
    
    def _load_history(self) -> list:
        """Load weight adjustment history."""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        else:
            return []
    
    def get_weight(self, keyword: str, default: float = 1.0) -> float:
        """Get current weight for a keyword."""
        return self.keyword_weights.get(keyword, default)
    
    def apply_adjustments(self, adjustments: Dict[str, float], 
                         reason: str = "optimization") -> int:
        """
        Apply weight adjustments and save to file.
        Returns number of weights updated.
        """
        timestamp = datetime.utcnow().isoformat()
        changes_made = 0
        
        for keyword, new_multiplier in adjustments.items():
            old_weight = self.keyword_weights.get(keyword, 1.0)
            new_weight = old_weight * new_multiplier
            
            # Clamp weights to reasonable range
            new_weight = max(0.1, min(3.0, new_weight))
            
            if abs(new_weight - old_weight) > 0.05:  # Only update if meaningful change
                self.keyword_weights[keyword] = new_weight
                changes_made += 1
                
                # Log to history
                self.weight_history.append({
                    'timestamp': timestamp,
                    'keyword': keyword,
                    'old_weight': old_weight,
                    'new_weight': new_weight,
                    'multiplier': new_multiplier,
                    'reason': reason
                })
        
        # Save to disk
        if changes_made > 0:
            self._save_weights()
            self._save_history()
            logger.info(f"Updated {changes_made} keyword weights ({reason})")
        
        return changes_made
    
    def _save_weights(self):
        """Save weights to file."""
        with open(self.weights_file, 'w') as f:
            json.dump(self.keyword_weights, f, indent=2)
    
    def _save_history(self):
        """Save history to file."""
        # Keep only last 1000 entries
        self.weight_history = self.weight_history[-1000:]
        
        with open(self.history_file, 'w') as f:
            json.dump(self.weight_history, f, indent=2)
    
    def rollback_to_timestamp(self, timestamp: str) -> int:
        """Rollback weights to a specific timestamp."""
        # Find all changes after timestamp
        cutoff_idx = next(
            (i for i, entry in enumerate(self.weight_history) 
             if entry['timestamp'] > timestamp),
            len(self.weight_history)
        )
        
        # Revert changes in reverse order
        changes = 0
        for entry in reversed(self.weight_history[cutoff_idx:]):
            keyword = entry['keyword']
            old_weight = entry['old_weight']
            self.keyword_weights[keyword] = old_weight
            changes += 1
        
        # Remove rolled-back entries from history
        self.weight_history = self.weight_history[:cutoff_idx]
        
        self._save_weights()
        self._save_history()
        
        logger.info(f"Rolled back {changes} weight changes to {timestamp}")
        return changes
    
    def get_recent_changes(self, limit: int = 50) -> list:
        """Get recent weight changes."""
        return self.weight_history[-limit:]

weight_manager = WeightManager()
```

**Integration into Scraper**:
```python
# In app/scraper.py, modify calculate_profit_score()

from app.weight_manager import weight_manager

# When applying keyword scores:
for keyword, base_points in web3_keywords.items():
    if keyword in text:
        negation_factor = self.check_negation_context(text, keyword)
        
        # NEW: Apply dynamic weight from weight manager
        dynamic_weight = weight_manager.get_weight(keyword, default=1.0)
        adjusted_points = base_points * dynamic_weight
        
        score += adjusted_points * negation_factor
```


---

### Task 4.3: Add Optimization API Endpoints
**Time**: 2-3 hours  
**Priority**: MEDIUM

**Files to Modify**:
- `app/main.py` - Add optimization endpoints

**New Endpoints**:
```python
# In app/main.py

@app.get("/optimize/report")
async def get_optimization_report():
    """
    Generate comprehensive optimization report.
    Shows suggested weight adjustments based on backtest data.
    """
    try:
        from app.optimizer import optimizer
        report = optimizer.generate_optimization_report()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize/apply")
async def apply_optimization(
    auto_apply: bool = Query(False, description="Automatically apply all suggestions"),
    threshold: float = Query(0.1, description="Minimum adjustment threshold")
):
    """
    Apply optimization suggestions to keyword weights.
    
    WARNING: This modifies the scoring system. Use with caution.
    Set auto_apply=false for dry-run (see suggestions without applying).
    """
    try:
        from app.optimizer import optimizer
        from app.weight_manager import weight_manager
        
        report = optimizer.generate_optimization_report()
        
        if not auto_apply:
            return {
                "message": "Dry run - no changes applied",
                "suggestions": report['keyword_adjustments'],
                "total_suggestions": len(report['keyword_adjustments'])
            }
        
        # Filter adjustments by threshold
        significant_adjustments = {
            kw: mult for kw, mult in report['keyword_adjustments'].items()
            if abs(mult - 1.0) >= threshold
        }
        
        # Apply adjustments
        changes = weight_manager.apply_adjustments(
            significant_adjustments,
            reason="auto_optimization"
        )
        
        return {
            "message": f"Applied {changes} weight adjustments",
            "changes": changes,
            "correlation_before": report['current_correlation'],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/optimize/weights")
async def get_current_weights(
    search: Optional[str] = Query(None, description="Search keyword weights")
):
    """Get current keyword weights."""
    try:
        from app.weight_manager import weight_manager
        
        weights = weight_manager.keyword_weights
        
        if search:
            weights = {
                k: v for k, v in weights.items() 
                if search.lower() in k.lower()
            }
        
        return {
            "weights": weights,
            "count": len(weights),
            "last_updated": max(
                (entry['timestamp'] for entry in weight_manager.weight_history),
                default=None
            ) if weight_manager.weight_history else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/optimize/history")
async def get_weight_history(
    limit: int = Query(50, ge=1, le=500)
):
    """Get weight adjustment history."""
    try:
        from app.weight_manager import weight_manager
        return {
            "history": weight_manager.get_recent_changes(limit),
            "count": len(weight_manager.weight_history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize/rollback")
async def rollback_weights(
    timestamp: str = Query(..., description="ISO timestamp to rollback to")
):
    """Rollback weights to a specific timestamp."""
    try:
        from app.weight_manager import weight_manager
        
        changes = weight_manager.rollback_to_timestamp(timestamp)
        
        return {
            "message": f"Rolled back {changes} changes to {timestamp}",
            "changes": changes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```


---

### Task 4.4: Schedule Automated Optimization
**Time**: 2 hours  
**Priority**: MEDIUM

**Files to Modify**:
- `app/scheduler.py` - Add monthly optimization job

**Code Changes**:
```python
# In app/scheduler.py

from app.optimizer import optimizer
from app.weight_manager import weight_manager

class NewsScrapingScheduler:
    def __init__(self):
        # ... existing code ...
        
        # NEW: Optimization configuration
        self.optimization_enabled = True
        self.optimization_day = 1  # First day of month
        self.optimization_auto_apply = False  # Require manual approval by default
    
    def schedule_monthly_optimization(self):
        """Schedule monthly weight optimization."""
        
        if self.optimization_enabled:
            # CORRECTED: `schedule` (1.2.x) has no `.month` unit — schedule a daily
            # 3 AM job and guard on day-of-month (runs on the 1st).
            schedule.every().day.at("03:00").do(
                self._run_optimization_job_if_due
            )
            logger.info("Scheduled daily job with monthly optimization guard")

    def _run_optimization_job_if_due(self):
        """Run optimization only on the 1st of the month."""
        if datetime.utcnow().day != self.optimization_day:
            return None
        return self._run_optimization_job()
    
    def _run_optimization_job(self):
        """Execute monthly optimization analysis."""
        logger.info("Starting monthly optimization analysis...")
        
        try:
            # Generate report
            report = optimizer.generate_optimization_report()
            
            logger.info(
                f"Optimization report generated: "
                f"{len(report['keyword_adjustments'])} suggestions, "
                f"correlation: {report['current_correlation']:.3f}"
            )
            
            # Save report to file for review
            report_path = Path(f"data/optimization_reports/report_{datetime.utcnow().strftime('%Y%m%d')}.json")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Report saved to {report_path}")
            
            # Auto-apply if enabled
            if self.optimization_auto_apply:
                significant_adjustments = {
                    kw: mult for kw, mult in report['keyword_adjustments'].items()
                    if abs(mult - 1.0) >= 0.1  # 10% threshold
                }
                
                changes = weight_manager.apply_adjustments(
                    significant_adjustments,
                    reason="monthly_auto_optimization"
                )
                
                logger.info(f"Auto-applied {changes} weight adjustments")
            else:
                logger.info("Auto-apply disabled. Review report manually at " + str(report_path))
            
            return report
            
        except Exception as e:
            logger.error(f"Optimization job failed: {e}")
            raise
```


---

### Task 4.5: Add Monitoring & Alerts
**Time**: 2-3 hours  
**Priority**: LOW

**Files to Create**:
- `app/monitoring.py` - System health monitoring

**Code Structure**:
```python
# app/monitoring.py

from datetime import datetime, timedelta
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.alert_thresholds = {
            'correlation_min': 0.2,  # Alert if correlation drops below this
            'backtest_success_rate': 0.7,  # Alert if <70% backtests succeed
            'scraping_articles_min': 10,  # Alert if scraping finds <10 articles
        }
    
    def check_system_health(self) -> Dict:
        """Run comprehensive health check."""
        from app.database import db
        
        health = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'alerts': [],
            'warnings': [],
            'metrics': {}
        }
        
        # Check backtest correlation
        try:
            accuracy = db.get_backtest_accuracy('24h', min_samples=50)
            correlation = accuracy.get('correlation', 0)
            
            health['metrics']['correlation'] = correlation
            
            if correlation < self.alert_thresholds['correlation_min']:
                health['alerts'].append({
                    'severity': 'HIGH',
                    'message': f'Low correlation: {correlation:.3f} (threshold: {self.alert_thresholds["correlation_min"]})',
                    'recommendation': 'Review scoring logic or run optimization'
                })
                health['status'] = 'degraded'
        except Exception as e:
            health['warnings'].append(f'Failed to check correlation: {e}')
        
        # Check recent scraping activity
        try:
            stats = db.get_stats()
            articles_last_24h = stats.get('articles_last_24h', 0)
            
            health['metrics']['articles_last_24h'] = articles_last_24h
            
            if articles_last_24h < self.alert_thresholds['scraping_articles_min']:
                health['alerts'].append({
                    'severity': 'MEDIUM',
                    'message': f'Low scraping volume: {articles_last_24h} articles in 24h',
                    'recommendation': 'Check scraper logs and source availability'
                })
                health['status'] = 'degraded'
        except Exception as e:
            health['warnings'].append(f'Failed to check scraping stats: {e}')
        
        # Check backtest job status
        try:
            backtest_stats = db.get_backtest_stats()
            success_rate = backtest_stats.get('success_rate', 0)
            
            health['metrics']['backtest_success_rate'] = success_rate
            
            if success_rate < self.alert_thresholds['backtest_success_rate']:
                health['alerts'].append({
                    'severity': 'MEDIUM',
                    'message': f'Low backtest success rate: {success_rate:.1%}',
                    'recommendation': 'Check CoinGecko API limits and asset mapping'
                })
        except Exception as e:
            health['warnings'].append(f'Failed to check backtest stats: {e}')
        
        # Set overall status
        if health['alerts']:
            high_severity = any(a['severity'] == 'HIGH' for a in health['alerts'])
            health['status'] = 'critical' if high_severity else 'degraded'
        
        return health

system_monitor = SystemMonitor()
```

**Add Health Check Endpoint**:
```python
# In app/main.py

@app.get("/health")
async def health_check():
    """Comprehensive system health check."""
    try:
        from app.monitoring import system_monitor
        return system_monitor.check_system_health()
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }
```


---

### Phase 4 Deliverables
- ✅ Weight optimization engine using regression analysis
- ✅ Dynamic keyword weight management with versioning
- ✅ Optimization API endpoints (report, apply, rollback)
- ✅ Automated monthly optimization jobs
- ✅ System health monitoring and alerts
- ✅ Self-improving scoring system

### Phase 4 Success Criteria
- [ ] Optimization generates actionable suggestions
- [ ] Keyword weights can be adjusted and rolled back
- [ ] Monthly optimization runs automatically
- [ ] System correlation improves over time (tracked quarterly)
- [ ] Health monitoring detects issues proactively

---

## 🚀 Phase 5: Advanced Features (Days 15+)

### Overview
Optional enhancements that add sophistication and value. Can be implemented incrementally based on priorities.

---

### Feature 5.1: Event Chain Tracking
**Time**: 4-6 hours  
**Priority**: LOW

**Goal**: Link related articles across time (e.g., "ETF filing" → "SEC review" → "Approval decision")

**Implementation Outline**:
```python
# Add to models.py
class EventChain(BaseModel):
    event_id: str
    event_type: str  # "regulatory", "partnership", "launch", etc.
    entity: str      # "Bitcoin ETF", "Ethereum Merge", etc.
    articles: List[int]  # Article IDs in chronological order
    start_date: datetime
    last_update: datetime
    stage: str  # "initial", "developing", "resolved"

# Add to database.py
def link_articles_to_event(article_id: int, event_id: str)
def get_event_timeline(event_id: str) -> List[dict]
def detect_related_events(new_article: dict) -> Optional[str]
```

**Benefits**:
- Track story evolution over weeks
- Identify patterns in multi-stage events
- Improve relevance scoring for ongoing stories

---

### Feature 5.2: LLM-Augmented Scoring
**Time**: 6-8 hours  
**Priority**: MEDIUM

**Goal**: Use GPT-4/Claude API for semantic understanding of article context

**Implementation Outline**:
```python
# Add to scraper.py
async def llm_score_article(self, title: str, content: str) -> dict:
    """
    Call LLM API for semantic analysis.
    Returns score, reasoning, and extracted signals.
    """
    prompt = f"""
    Analyze this crypto/web3 news article for profit potential (0-10 scale):
    
    Title: {title}
    Content: {content[:1000]}
    
    Consider:
    - Sentiment (positive/negative/neutral)
    - Market impact potential
    - Credibility of claims
    - Timing (breaking news vs retrospective)
    - Affected assets/companies
    
    Return JSON:
    {{
        "score": <float 0-10>,
        "reasoning": "<why>",
        "sentiment": "<positive/negative/neutral>",
        "key_signals": ["signal1", "signal2"],
        "affected_assets": ["BTC", "ETH"],
        "confidence": <float 0-1>
    }}
    """
    
    response = await call_openai_api(prompt)
    return parse_llm_response(response)

# Hybrid scoring:
keyword_score = calculate_profit_score(...)  # Existing
llm_result = await llm_score_article(...)    # New

# Weighted combination
final_score = (keyword_score * 0.6 + llm_result['score'] * 0.4)
```

**Benefits**:
- Context-aware scoring (understands negation, sarcasm, nuance)
- Better signal extraction
- Continuous improvement as LLMs improve

**Costs**:
- API costs (~$0.002-0.01 per article)
- Latency (500-1500ms per call)
- Rate limits

**Strategy**:
- Use LLM only for high-scoring keyword articles (pre-filter)
- Cache results to avoid duplicate calls
- Fall back to keyword scoring if API fails


---

### Feature 5.3: Social Signal Integration
**Time**: 8-10 hours  
**Priority**: LOW

**Goal**: Incorporate Twitter/Reddit sentiment and engagement metrics

**Implementation Outline**:
```python
# Add to scraper.py
class SocialSignalCollector:
    def __init__(self):
        self.twitter_api = TwitterAPI()
        self.reddit_api = RedditAPI()
    
    def get_twitter_sentiment(self, keywords: List[str], hours: int = 24) -> dict:
        """Analyze Twitter sentiment for keywords in last N hours."""
        tweets = self.twitter_api.search(keywords, since=hours)
        
        return {
            'tweet_count': len(tweets),
            'avg_sentiment': calculate_sentiment_score(tweets),
            'top_influencers': extract_influencers(tweets),
            'engagement_rate': calculate_engagement(tweets)
        }
    
    def get_reddit_activity(self, subreddits: List[str], keywords: List[str]) -> dict:
        """Check Reddit activity for related discussions."""
        posts = self.reddit_api.search(subreddits, keywords)
        
        return {
            'post_count': len(posts),
            'upvote_ratio': calculate_upvote_ratio(posts),
            'comment_count': sum(p['comments'] for p in posts),
            'trending_score': calculate_trending_score(posts)
        }

# Integrate into scoring:
social_signals = get_social_signals(article_keywords)

# Boost score if high social engagement
if social_signals['tweet_count'] > 100:
    score *= 1.1
if social_signals['reddit_trending_score'] > 0.8:
    score *= 1.15
```

**Data Sources**:
- Twitter API (paid, $100-5000/month)
- Reddit API (free, rate limited)
- Alternative: LunarCrush API (crypto social data)

**Benefits**:
- Early signal detection (social often leads news)
- Community sentiment validation
- Viral content identification

---

### Feature 5.4: Portfolio Simulator
**Time**: 6-8 hours  
**Priority**: MEDIUM

**Goal**: Simulate portfolio performance based on article scores

**Implementation Outline**:
```python
# Add to main.py
@app.post("/simulate/portfolio")
async def simulate_portfolio(
    initial_capital: float = 10000,
    min_score: float = 7.0,
    position_size: float = 0.1,  # 10% per trade
    start_date: str = None,
    end_date: str = None
):
    """
    Simulate trading strategy based on article scores.
    
    Strategy:
    - Invest 'position_size' of capital in assets from high-scoring articles
    - Hold for 24h/7d
    - Track P&L
    """
    
    articles = db.get_backtested_articles(
        min_score=min_score,
        start_date=start_date,
        end_date=end_date
    )
    
    portfolio = PortfolioSimulator(initial_capital)
    
    for article in articles:
        for asset in article['assets']:
            # Simulate buying
            position_value = initial_capital * position_size
            entry_price = asset['price_at_publish']
            exit_price = asset['price_24h']
            
            pnl = (exit_price - entry_price) / entry_price * position_value
            portfolio.record_trade(article, asset, pnl)
    
    return {
        'initial_capital': initial_capital,
        'final_capital': portfolio.total_value,
        'total_return': portfolio.total_return_pct,
        'win_rate': portfolio.win_rate,
        'trades': len(portfolio.trades),
        'best_trade': portfolio.best_trade,
        'worst_trade': portfolio.worst_trade,
        'sharpe_ratio': portfolio.sharpe_ratio
    }
```

**Benefits**:
- Quantify system value in dollar terms
- Compare strategies (score thresholds, hold periods)
- Identify optimal parameters
- Pitch to investors ("backtested 23% annual return")

---

### Feature 5.5: Frontend Dashboard
**Time**: 10-15 hours  
**Priority**: HIGH (user-facing)

**Goal**: Build React dashboard for visualization and control

**Features**:
- Real-time article feed with score filters
- Profit opportunity cards (top scoring articles)
- Analytics charts (correlation trends, keyword performance)
- Optimization control panel (review/apply suggestions)
- Backtest explorer (see predictions vs outcomes)
- System health monitoring

**Tech Stack** (already in project):
- React + TypeScript (frontend)
- Chart.js or Recharts (visualization)
- TanStack Query (data fetching)
- shadcn/ui (UI components - already installed)

**API Integration Points**:
- GET /articles?min_profit_score=7.0
- GET /opportunities
- GET /backtest/accuracy
- GET /optimize/report
- GET /health


---

### Phase 5 Priority Ranking

**Tier 1 (High Value, Moderate Effort)**:
1. **Frontend Dashboard** - Makes system usable and impressive
2. **Portfolio Simulator** - Quantifies value, validates system
3. **LLM-Augmented Scoring** - Significant quality improvement

**Tier 2 (Medium Value, Lower Effort)**:
4. **Event Chain Tracking** - Better for regulatory/long-term stories
5. **Social Signal Integration** - Expensive but powerful

**Recommended Order**: Dashboard → Simulator → LLM → Event Tracking → Social

---

## 📊 Testing & Validation Strategy

### Test Infrastructure (Phase 1 prerequisite — Task 1.0)
`tests/` is currently empty and `pyproject.toml` has no dev dependencies. Before writing tests:
```bash
poetry add --group dev pytest pytest-cov
```
Wire a CI step (`poetry run pytest --cov=app`) so the 80% coverage target is enforceable.

### Unit Tests
**Coverage Target**: 80%+

**Priority Test Areas**:
1. Sentiment multiplier calculation
2. Negation detection patterns
3. Article clustering similarity
4. Backtest data calculation
5. Weight optimization logic

**Test Files**:
- `tests/test_sentiment_scoring.py`
- `tests/test_negation.py`
- `tests/test_clustering.py`
- `tests/test_backtesting.py`
- `tests/test_optimization.py`

### Integration Tests

**Scenarios**:
1. End-to-end scraping with new scoring
2. Article clustering across multiple sources
3. Backtest job execution
4. Optimization report generation
5. API endpoint responses

### Performance Tests

**Benchmarks**:
- Scraping speed: Should not increase >20%
- Article clustering: <200ms per article
- Backtest job: Complete 100 articles in <40 min (CoinGecko free tier ~18 s/article at 3 assets × 4 price points × 1.5 s delay; batch BTC reference prices once per job)
- API response times: <500ms (p95)

**Tools**:
- `pytest-benchmark` for profiling
- `locust` for load testing

### Validation Tests

**Manual Validation** (Phase 1):
- Sample 50 high-scoring articles → Verify actually positive
- Sample 50 low-scoring articles → Verify correctly filtered
- Test negation: "ETF rejected" should score low

**Quantitative Validation** (Phase 3+):
- Correlation > 0.3 (acceptable)
- Correlation > 0.5 (good)
- Correlation > 0.7 (excellent)

---

## 🔄 Rollback & Risk Mitigation

### Rollback Strategy

**Phase 1 Rollback**:
- Keep original `calculate_profit_score()` as `calculate_profit_score_v1()`
- Add feature flag: `USE_NEW_SCORING = True/False` in config
- One-line rollback by toggling flag

**Phase 2 Rollback**:
- Clustering is additive (doesn't break existing articles)
- Can disable clustering without data loss
- Original articles still stored

**Phase 3 Rollback**:
- Backtest system is separate (no impact on scraping)
- Can disable jobs without affecting main system

**Phase 4 Rollback**:
- Use `weight_manager.rollback_to_timestamp()`
- All changes tracked in version history
- Can revert to any previous state

### A/B Testing Approach

Run old and new scoring in parallel for 1 week:

```python
# Calculate both scores
old_score = calculate_profit_score_v1(...)
new_score = calculate_profit_score_v2(...)

# Store both
article.profit_score = new_score  # Use new for display
article.profit_score_legacy = old_score  # Track for comparison

# After 1 week: Compare which correlates better with outcomes
```

### Database Migrations

**Safety**:
- Always add columns as nullable
- Never drop columns immediately (deprecate first)
- Backup database before schema changes
- Test migrations on copy first

**Migration Scripts**:
```bash
# Create backup
cp news_scraper.db news_scraper_backup_$(date +%Y%m%d).db

# Run migration
python scripts/migrate_add_clustering_fields.py

# Verify
python scripts/verify_migration.py
```

---

## 📁 Project Structure (After Implementation)

```
news-scraper-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + endpoints
│   ├── config.py            # Settings
│   ├── models.py            # Pydantic models
│   ├── database.py          # SQLite operations
│   ├── scraper.py           # ⚡ UPDATED: New scoring logic
│   ├── scheduler.py         # ⚡ UPDATED: + backtest & optimization jobs
│   ├── clustering.py        # 🆕 Article deduplication
│   ├── asset_extractor.py   # 🆕 Extract tradeable assets
│   ├── price_fetcher.py     # 🆕 CoinGecko API integration
│   ├── backtester.py        # 🆕 Validation system
│   ├── optimizer.py         # 🆕 Weight tuning engine
│   ├── weight_manager.py    # 🆕 Dynamic weights
│   └── monitoring.py        # 🆕 Health checks
│
├── data/
│   ├── keyword_weights.json      # 🆕 Dynamic weights
│   ├── weight_history.json       # 🆕 Change log
│   └── optimization_reports/     # 🆕 Monthly reports
│
├── tests/
│   ├── test_sentiment_scoring.py    # 🆕
│   ├── test_negation.py             # 🆕
│   ├── test_clustering.py           # 🆕
│   ├── test_backtesting.py          # 🆕
│   └── test_optimization.py         # 🆕
│
├── scripts/
│   ├── migrate_database.py          # 🆕 Schema migrations
│   └── verify_backtest_data.py      # 🆕 Data quality checks
│
├── news_scraper.db          # ⚡ UPDATED: New tables
├── pyproject.toml           # ⚡ UPDATED: New dependencies
├── README.md                # ⚡ UPDATED: New documentation
├── SCORING_IMPROVEMENTS.md  # 📄 This doc (analysis)
└── IMPLEMENTATION_PLAN.md   # 📄 This doc (plan)
```


---

## 💰 Resource Requirements

### Development Time
- **Phase 1**: 2-3 days (1 developer)
- **Phase 2**: 2-3 days (1 developer)
- **Phase 3**: 3-4 days (1 developer)
- **Phase 4**: 3-4 days (1 developer) + 2-4 weeks data collection
- **Phase 5**: 10-30 days depending on features selected

**Total Core Implementation**: 10-14 days + data collection period

### Infrastructure Costs

**APIs** (Monthly):
- CoinGecko Free Tier: $0 (50 calls/min, sufficient for backtesting)
- CoinGecko Pro (if needed): $129/month (500 calls/min)
- OpenAI API (if using LLM): ~$50-200/month (depends on volume)
- Twitter API (if using social): $100-5000/month
- **Total**: $0-300/month (core features), $100-5000/month (with all Phase 5)

**Compute**:
- Current setup sufficient (no GPU needed)
- sentence-transformers model: ~80MB disk, ~200MB RAM
- Increased storage: ~500MB for backtest data (first year)

### Team Skills Required

**Phase 1-2** (Foundation):
- Python (intermediate)
- FastAPI basics
- SQL/SQLite
- Basic ML concepts (sentiment analysis)

**Phase 3** (Backtesting):
- API integration (CoinGecko)
- Async Python
- Data analysis basics

**Phase 4** (Optimization):
- Machine learning (regression, sklearn)
- Statistics (correlation, significance)
- Data science mindset

**Phase 5** (Advanced):
- NLP/LLM integration
- Frontend development (React)
- Data visualization

---

## 📈 Expected Business Impact

### Quantitative Improvements

**Accuracy**:
- Current: ~50% "useful" articles (manual validation)
- Phase 1 Target: 70-80% useful (sentiment gating)
- Phase 3+ Target: 80-90% useful (validated scoring)

**Efficiency**:
- Current: Manual review of 100+ articles/day
- Phase 1: Manual review of 30-50 articles/day (70% reduction)
- Phase 2: Manual review of 15-25 unique opportunities/day (clustering)

**Signal Quality**:
- Current: Correlation with price movements unknown
- Phase 3: Measured correlation (target: 0.3-0.5)
- Phase 4: Improved correlation (target: 0.5-0.7)

### Qualitative Benefits

1. **Trust**: Validated system builds user confidence
2. **Automation**: Less manual curation needed
3. **Adaptability**: System learns and improves over time
4. **Transparency**: Clear metrics and explanations
5. **Scalability**: Can handle 10x more sources without quality drop

### ROI Analysis

**Investment**:
- Development: 10-14 days @ $500-1000/day = $5,000-14,000
- Infrastructure: $0-300/month
- Ongoing: 2-4 hours/month maintenance

**Returns** (Estimated):
- Time saved: 5-10 hours/week manual curation = $2,000-4,000/month
- Better signals: Improved trading outcomes (hard to quantify, but 1-5% improvement on $100k portfolio = $1,000-5,000/month)
- User acquisition: Professional system attracts paying users

**Break-even**: 2-4 months  
**12-month ROI**: 300-500%

---

## ✅ Decision Points & Approvals

### Phase 1 - GO/NO-GO Decision

**Review After**: Phase 1 complete (Day 3)

**Metrics to Evaluate**:
- [ ] False positive rate reduced by 40%+ (manual spot check)
- [ ] No significant performance regression (<10% slower)
- [ ] Tests pass with 80%+ coverage
- [ ] No critical bugs in production

**Decision**:
- ✅ GO: Proceed to Phase 2
- ❌ NO-GO: Roll back, revise approach

---

### Phase 2 - GO/NO-GO Decision

**Review After**: Phase 2 complete (Day 6)

**Metrics to Evaluate**:
- [ ] Duplicate articles reduced by 60%+
- [ ] Clustering accuracy >90% (manual validation of 50 samples)
- [ ] Performance acceptable (<20% slowdown)
- [ ] No database corruption or data loss

**Decision**:
- ✅ GO: Proceed to Phase 3
- ❌ NO-GO: Roll back clustering, keep Phase 1 improvements

---

### Phase 3 - GO/NO-GO Decision

**Review After**: 2 weeks of data collection

**Metrics to Evaluate**:
- [ ] Backtesting runs successfully (>70% success rate)
- [ ] Sufficient data collected (>100 articles with price data)
- [ ] API costs acceptable
- [ ] Initial correlation visible (>0.2)

**Decision**:
- ✅ GO: Continue data collection, plan Phase 4
- ⚠️ PAUSE: If correlation <0.2, investigate scoring issues before Phase 4
- ❌ NO-GO: If fundamental issues detected, revise approach

---

### Phase 4 - GO/NO-GO Decision

**Review After**: First optimization run

**Metrics to Evaluate**:
- [ ] Optimization generates sensible suggestions
- [ ] Correlation improves after applying suggestions
- [ ] No system instability
- [ ] Weight rollback works correctly

**Decision**:
- ✅ GO: Enable automated monthly optimization
- ⚠️ MANUAL: Keep optimization manual-approval only
- ❌ NO-GO: Disable optimization, use static weights

---

### Phase 5 - Feature Selection

**Review After**: Phase 1-4 complete and stable

**Priority Matrix**:

| Feature | Value | Effort | Priority | Proceed? |
|---------|-------|--------|----------|----------|
| Frontend Dashboard | HIGH | HIGH | 1 | [ ] |
| Portfolio Simulator | HIGH | MEDIUM | 2 | [ ] |
| LLM Scoring | HIGH | MEDIUM | 3 | [ ] |
| Event Tracking | MEDIUM | MEDIUM | 4 | [ ] |
| Social Signals | MEDIUM | HIGH | 5 | [ ] |

**Budget Check**:
- Development budget available: $______
- Monthly operational budget: $______
- Selected features fit within budget: [ ] YES [ ] NO

---

## 📝 Documentation Updates

### User Documentation (README.md)

**Sections to Add/Update**:
- New scoring methodology explanation
- API endpoints documentation
- How to interpret profit scores
- Backtesting metrics explanation
- Weight optimization guide

### Developer Documentation

**New Docs Needed**:
- `ARCHITECTURE.md` - System design overview
- `API.md` - Complete API reference
- `OPTIMIZATION_GUIDE.md` - How to tune the system
- `DEPLOYMENT.md` - Production setup guide
- `TROUBLESHOOTING.md` - Common issues

### Code Documentation

**Standards**:
- All new functions have docstrings
- Complex algorithms explained with comments
- Type hints for all function signatures
- Example usage in docstrings

---

## 🚨 Risk Assessment

### High Risk Items

1. **Phase 4 Auto-Optimization**
   - Risk: Bad suggestions degrade system
   - Mitigation: Manual approval by default, rollback capability, monitoring

2. **API Rate Limits (CoinGecko)**
   - Risk: Backtest jobs fail due to rate limiting
   - Mitigation: Caching, retry logic, upgrade to paid tier if needed

3. **Database Schema Changes**
   - Risk: Data loss or corruption
   - Mitigation: Always backup, test migrations, nullable columns

### Medium Risk Items

4. **Clustering False Positives**
   - Risk: Unrelated articles grouped together
   - Mitigation: Calibrated similarity threshold (0.6, see Task 2.2), manual review

5. **Sentiment Analysis Edge Cases**
   - Risk: Sarcasm, complex negation not detected
   - Mitigation: Expand negation patterns, consider LLM for edge cases

### Low Risk Items

6. **Performance Degradation**
   - Risk: System becomes too slow
   - Mitigation: Profiling, optimization, caching

7. **Dependency Issues**
   - Risk: New packages cause conflicts
   - Mitigation: Poetry lock file, thorough testing

---

## 🎯 Success Metrics Summary

### Immediate (Phase 1-2)
- ✅ False positive rate < 20% (down from ~50%)
- ✅ Duplicate articles reduced by 60%+
- ✅ All tests pass
- ✅ No production incidents

### Short-term (Phase 3, after 1 month)
- ✅ 500+ articles backtested
- ✅ Correlation > 0.3
- ✅ Backtest success rate > 70%
- ✅ API costs < $100/month

### Medium-term (Phase 4, after 3 months)
- ✅ Correlation > 0.5
- ✅ Optimization improves accuracy by 10%+
- ✅ System operates autonomously
- ✅ Zero manual weight adjustments needed

### Long-term (Phase 5, after 6 months)
- ✅ Correlation > 0.6
- ✅ 5,000+ articles backtested
- ✅ Dashboard deployed and used daily
- ✅ ROI > 300%

---

## 📞 Stakeholder Communication Plan

### Weekly Updates
- Progress against plan
- Blockers and risks
- Metrics dashboard
- Next week's goals

### Phase Completion Reports
- Deliverables checklist
- Metrics achieved
- Lessons learned
- Go/no-go recommendation

### Monthly Business Reviews
- System performance trends
- Cost analysis
- User feedback
- Roadmap adjustments

---

## 🎉 Conclusion

This implementation plan provides a structured, low-risk approach to transforming the news scraper from a keyword-based "hype score" system into a validated, self-improving profit signal detector.

### Key Principles
1. **Incremental**: Each phase adds value independently
2. **Validated**: Backtest against reality, not assumptions
3. **Reversible**: Can roll back any phase if issues arise
4. **Transparent**: All decisions backed by metrics
5. **Adaptive**: System improves continuously

### Next Steps

1. **Review this plan** with stakeholders
2. **Approve budget and timeline**
3. **Assign developer(s)**
4. **Set up project tracking** (Jira, GitHub Projects, etc.)
5. **Begin Phase 1 implementation**

### Questions to Answer Before Starting

- [ ] Do we have 10-14 days of development time available?
- [ ] Can we allocate $0-300/month for API costs?
- [ ] Who will review and approve optimization suggestions?
- [ ] What is our target go-live date?
- [ ] Do we proceed with all phases or select subset?
- [ ] Who are the key stakeholders for weekly updates?

---

**Document Version**: 1.0  
**Created**: 2026-08-04  
**Status**: Ready for Review  
**Next Action**: Stakeholder approval to proceed

## 📦 Dependencies & Setup

### New Dependencies (Phase-by-Phase)

**Phase 1** (add to pyproject.toml):
```toml
# No new dependencies needed
```

**Phase 2**:
```toml
sentence-transformers = "^2.2.0"
scikit-learn = "^1.3.0"
rapidfuzz = "^3.5.0"
```

**Phase 3**:
```toml
pycoingecko = "^3.1.0"
requests-cache = "^1.1.0"
scipy = "^1.11.0"
```

**Phase 4**:
```toml
# Dependencies already covered in Phase 2-3
```

**Installation Commands**:
```bash
# Phase 2
poetry add sentence-transformers scikit-learn rapidfuzz

# Phase 3
poetry add pycoingecko requests-cache scipy
```


---

## 🗓️ Timeline & Resource Allocation

### Detailed Timeline (Full-Time Developer)

**Week 1**:
- Days 1-3: Phase 1 (Foundation & Quick Wins)
  - Monday: Sentiment multiplier + negation detection
  - Tuesday: Source credibility + database schema updates
  - Wednesday: Testing + documentation

**Week 2**:
- Days 4-6: Phase 2 (Deduplication & Clustering)
  - Thursday: Install dependencies + build clustering engine
  - Friday: Integrate clustering into scraper
  - Monday: API endpoints + performance optimization

**Week 2-3**:
- Days 7-10: Phase 3 (Backtesting Infrastructure)
  - Tuesday: Database schema + asset extraction
  - Wednesday: Price fetcher implementation
  - Thursday: Backtesting jobs + scheduler integration
  - Friday: Analytics API endpoints

**Week 3-4** (WAIT PERIOD):
- Days 11-24: Data collection (no coding)
  - Monitor backtest jobs
  - Collect 100+ backtested articles
  - Review preliminary metrics

**Week 4**:
- Days 25-28: Phase 4 (Adaptive Scoring)
  - Monday: Build optimization engine
  - Tuesday: Weight management system
  - Wednesday: API endpoints + scheduler
  - Thursday: Testing + validation


### Alternative Timeline (Part-Time Developer)

**Weeks 1-2**: Phase 1 (6-8 hours)
**Weeks 3-4**: Phase 2 (6-8 hours)
**Weeks 5-6**: Phase 3 (8-10 hours)
**Weeks 7-10**: Data collection + monitoring
**Weeks 11-12**: Phase 4 (8-10 hours)

**Total**: 10-12 weeks part-time

---

## 💰 Cost Estimation

### Development Costs
- **Phase 1-4**: 12-15 developer-days × $500-800/day = **$6,000-12,000**
- **Phase 5** (optional): 5-10 days × $500-800/day = **$2,500-8,000**

### Operational Costs (Monthly)

**APIs**:
- CoinGecko API: **$0** (free tier, 10-50 calls/min)
- OpenAI API (Phase 5, optional): **$50-200/month** (depends on volume)
- Twitter API (Phase 5, optional): **$100-500/month**

**Infrastructure**:
- Hosting: **$20-50/month** (DigitalOcean, AWS EC2)
- Database: **$0** (SQLite) or **$15-30/month** (PostgreSQL)
- Monitoring: **$0** (self-hosted) or **$30-100/month** (DataDog)

**Total Ongoing**: **$20-100/month** (without optional features)


---

## ⚠️ Risks & Mitigation

### Technical Risks

**Risk 1**: Clustering too slow, impacts scraping performance
- **Probability**: Medium
- **Impact**: High
- **Mitigation**: Use fuzzy matching pre-filter; cache embeddings; limit to 12h window
- **Fallback**: Disable clustering, keep simple deduplication

**Risk 2**: CoinGecko API rate limits exceeded
- **Probability**: High
- **Impact**: Medium
- **Mitigation**: Cache responses; add delays; use free tier wisely (10-50 calls/min)
- **Fallback**: Reduce backtest frequency; add manual price entry option

**Risk 3**: Insufficient backtest data for optimization
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**: Wait 4 weeks before Phase 4; start with manual weight tuning
- **Fallback**: Use expert judgment for weights until data accumulates

**Risk 4**: Optimization makes scoring worse
- **Probability**: Low
- **Impact**: High
- **Mitigation**: A/B testing; gradual rollout; rollback capability; manual review
- **Fallback**: Revert to previous weights using timestamp rollback


### Business Risks

**Risk 5**: ROI unclear without validation
- **Probability**: Medium
- **Impact**: High
- **Mitigation**: Implement Phase 3 first to validate system value
- **Success Metric**: Show positive correlation (>0.3) before investing in Phase 4

**Risk 6**: System complexity increases maintenance burden
- **Probability**: High
- **Impact**: Medium
- **Mitigation**: Comprehensive documentation; monitoring/alerting; modular design
- **Success Metric**: All components can be disabled independently

---

## ✅ Acceptance Criteria

### Phase 1 Complete When:
- [ ] Negative news articles score <50% of equivalent positive news
- [ ] Source credibility weights applied to all articles
- [ ] Negation detection catches "rejects", "denies", "fails" patterns
- [ ] All tests pass with 80%+ coverage
- [ ] No performance regression >10%

### Phase 2 Complete When:
- [ ] Duplicate articles from same event clustered together
- [ ] Corroboration multiplier visible in API responses
- [ ] 60-80% reduction in duplicate opportunities
- [ ] Clustering adds <200ms per article
- [ ] API returns cluster details correctly


### Phase 3 Complete When:
- [ ] Backtest jobs run automatically daily
- [ ] Price data fetched for 80%+ of crypto articles
- [ ] Correlation metric calculated correctly
- [ ] Analytics API returns meaningful statistics
- [ ] 100+ articles successfully backtested
- [ ] Correlation > 0.2 (baseline validation)

### Phase 4 Complete When:
- [ ] Optimization generates weight suggestions
- [ ] Weights can be applied and rolled back
- [ ] Monthly optimization runs automatically
- [ ] Health monitoring detects correlation drops
- [ ] System shows improvement trend over 3 months

---

## 📈 Success Metrics (3-Month Goals)

### Quantitative Metrics:
1. **False Positive Rate**: <10% (down from ~45%)
2. **Correlation Coefficient**: >0.5 (24h price movements)
3. **Duplicate Reduction**: 70%+ fewer duplicate opportunities
4. **Backtest Coverage**: 90%+ of articles have price data
5. **System Uptime**: 99%+ (scraping + backtesting)

### Qualitative Metrics:
1. User can trust high-scored articles (manual validation)
2. Negative news correctly filtered out
3. Multi-source stories recognized and prioritized
4. System improves over time (visible in metrics)


---

## 🚦 Go/No-Go Decision Points

### After Phase 1 (Week 1):
**Evaluate**: 
- Does sentiment gating visibly reduce false positives?
- Are negation patterns catching enough edge cases?
- Is performance acceptable?

**Decision**: 
- ✅ GO if improvement visible → Proceed to Phase 2
- ⛔ NO-GO if worse/no change → Revisit scoring logic

### After Phase 3 (Week 3):
**Evaluate**:
- Is correlation >0.2?
- Is backtest data quality good (>70% success rate)?
- Are API costs manageable?

**Decision**:
- ✅ GO if correlation positive → Wait for data, then Phase 4
- ⛔ NO-GO if correlation ≤0 → Scoring fundamentally broken, redesign needed

### After Phase 4 (Month 2):
**Evaluate**:
- Did optimization improve correlation?
- Is system stable with dynamic weights?
- Are costs/complexity justified?

**Decision**:
- ✅ GO to Phase 5 if improvement shown
- ⛔ PAUSE if neutral → Keep monitoring, don't add complexity


---

## 📚 Documentation Requirements

### For Each Phase:

**Code Documentation**:
- Docstrings for all new functions (Google style)
- Inline comments for complex logic
- Type hints for all function signatures

**API Documentation**:
- Update OpenAPI/Swagger docs
- Add request/response examples
- Document rate limits and errors

**User Documentation**:
- Update README.md with new features
- Create CHANGELOG.md tracking versions
- Add configuration guide for new settings

**Developer Documentation**:
- Architecture diagrams (system flow)
- Database schema diagrams
- Deployment guide with rollback procedures

---

## 🔐 Security Considerations

### API Keys & Secrets:
- Store CoinGecko API key in `.env` (if premium tier)
- Never commit API keys to git
- Use environment variables for all secrets

### Data Privacy:
- Article content may be copyrighted (check ToS)
- Price data is public domain
- No PII collected

### Rate Limiting:
- Implement rate limiting on API endpoints
- Prevent abuse of optimization/backtest endpoints
- Add authentication for write operations: all state-mutating endpoints (`POST /scrape`, `POST /scheduler/*`, `POST /optimize/apply`, `POST /optimize/rollback`) must require an `X-API-Key` header validated against a server-side secret from `.env` (FastAPI dependency). Ship the auth dependency in Phase 1 so every later write endpoint reuses it.


---

## 🎯 Recommended Decision

### My Recommendation: **PROCEED with Phased Approach**

**Reasoning**:
1. **Phase 1 is low-risk, high-value** - Quick wins with minimal code changes
2. **Phase 3 validates entire premise** - Before heavy investment, prove correlation exists
3. **Modular design allows stopping anytime** - Each phase adds value independently
4. **Clear success metrics** - Know exactly when to continue vs. stop
5. **Rollback strategy in place** - Can revert any changes that don't work

**Suggested Path**:
1. ✅ **Approve Phase 1** - Start immediately (3 days)
2. 🔍 **Evaluate Phase 1** - Review false positive reduction
3. ✅ **Approve Phase 2** - If Phase 1 successful (3 days)
4. ✅ **Approve Phase 3** - Critical validation phase (4 days)
5. ⏸️ **Wait 3-4 weeks** - Let data accumulate
6. 🔍 **Evaluate correlation** - If >0.2, proceed to Phase 4
7. ✅ **Approve Phase 4** - If correlation positive (4 days)
8. 🤔 **Consider Phase 5** - Based on business needs

**Budget Commitment**:
- Initial: $3,000-5,000 (Phases 1-3)
- If successful: +$3,000-7,000 (Phase 4)
- Optional: +$2,500-8,000 (Phase 5)

**Timeline Commitment**:
- 2 weeks active development
- 3-4 weeks passive monitoring
- Total: 6 weeks to validation


---

## 📞 Next Steps

### Immediate Actions (If Approved):

1. **Day 0**: 
   - [ ] Review and approve this implementation plan
   - [ ] Assign developer resources
   - [ ] Set up project tracking (Jira/GitHub Issues)
   - [ ] Create git branch: `feature/scoring-redesign`

2. **Day 1**:
   - [ ] Create backup of current production database
   - [ ] Set up test environment
   - [ ] Begin Phase 1, Task 1.1 (Sentiment Multiplier)
   - [ ] Create feature flag for gradual rollout

3. **Week 1 End**:
   - [ ] Phase 1 complete
   - [ ] Deploy to staging
   - [ ] Run validation tests
   - [ ] Hold go/no-go meeting for Phase 2

4. **Week 2 End**:
   - [ ] Phase 2 complete
   - [ ] Deploy to production
   - [ ] Monitor for issues
   - [ ] Begin Phase 3

5. **Week 3 End**:
   - [ ] Phase 3 complete
   - [ ] Backtest jobs running
   - [ ] Set calendar reminder for 3 weeks (data collection)

6. **Week 6-7**:
   - [ ] Review backtest data quality
   - [ ] Analyze correlation metrics
   - [ ] Hold go/no-go meeting for Phase 4
   - [ ] If approved, begin Phase 4


### Questions to Answer Before Starting:

1. **Team**: Who will be the primary developer? Do they have Python/ML experience?
2. **Timeline**: Is 6-week timeline acceptable, or do we need faster results?
3. **Budget**: Is $6,000-12,000 development budget approved?
4. **Risk Tolerance**: Are we comfortable with phased rollout, or need everything upfront?
5. **Success Definition**: What correlation coefficient would you consider "success"?
6. **Phase 5**: Which Phase 5 features are must-haves vs. nice-to-haves?
7. **Deployment**: Where will this be deployed? Do we have CI/CD pipeline?

---

## 📝 Appendix

### Glossary

- **Correlation Coefficient**: Statistical measure (-1 to 1) of how well scores predict outcomes
- **Backtest**: Testing predictions against historical data
- **Sentiment Multiplier**: Factor that boosts/penalizes score based on positive/negative tone
- **Corroboration**: Multiple sources reporting same event (increases confidence)
- **Negation Detection**: Identifying when keywords appear in negative contexts
- **Weight Optimization**: Automatically adjusting keyword importance based on performance
- **False Positive**: High-scoring article that doesn't represent profit opportunity

### Reference Links

- **CoinGecko API**: https://www.coingecko.com/en/api
- **Sentence Transformers**: https://www.sbert.net/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLite Best Practices**: https://www.sqlite.org/bestpractice.html


---

## 🏁 Summary

This implementation plan transforms your news scraper from a **keyword-matching hype detector** into a **validated, self-improving profit signal system**.

### Key Improvements:
1. **Sentiment-aware** - Negative news scores low, not high
2. **Context-aware** - Detects negation and nuance
3. **Source-weighted** - Trusts established sources more
4. **Deduplication** - One opportunity per event, not five
5. **Validated** - Backtested against real market outcomes
6. **Self-improving** - Learns from data, adapts to narrative shifts

### Investment:
- **Time**: 12-15 developer-days (2-3 weeks active work)
- **Cost**: $6,000-12,000 development + $20-100/month operational
- **Risk**: Low (phased approach with rollback capability)

### Expected ROI:
- **False positives**: 60-70% reduction
- **Signal quality**: 3-5x improvement
- **Correlation**: From unknown to 0.3-0.7 (validated)
- **User trust**: High (transparent, data-driven)

**Ready to proceed?** Start with Phase 1 and evaluate results in 3 days.

---

**Document Version**: 1.0  
**Created**: 2026-08-04  
**Author**: AI Development Team  
**Status**: Ready for Review & Approval

---

*End of Implementation Plan*
