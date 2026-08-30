# News Scraper Profit Scoring - Critical Issues & Redesign Plan

## Executive Summary

The current profit scoring system uses **additive keyword matching** which creates a "hype score" rather than a true profit signal. This document outlines 7 critical issues and provides a concrete redesign to fix them.

---

## 🚨 Critical Issues with Current Implementation

### 1. **Additive Keyword Matching Without Context**

**Problem**: Scores accumulate based on keyword presence regardless of actual sentiment or context.

**Example Failure**:
- ✅ "BlackRock ETF sees record institutional adoption" → Score: 9.5
- ✅ "BlackRock ETF outflows hit record as institutions flee" → Score: 9.5

**Why it fails**: Both contain `blackrock`, `etf`, `institutional`, `record` but represent opposite scenarios. The current system gives them identical scores.

**Impact**: False positives lead to recommending articles about negative events as "profit opportunities."

---

### 2. **No Negation or Context Handling**

**Problem**: High-value keywords in negative contexts still add points.

**Example Failures**:
- "Ethereum partnership falls through" → High score from `ethereum` + `partnership`
- "SEC rejects Bitcoin ETF" → High score from `sec`, `bitcoin`, `etf`
- "Hack drains DeFi protocol" → High score from `defi`, `protocol`
- "Coinbase denies rumors of insider trading investigation" → High score from `coinbase`

**Current mitigation**: Negative keyword list exists but gets drowned out by positive keyword accumulation.

**Missing**: Proximity-based negation detection (e.g., "not," "denies," "rejects," "fails" within 5 words of keywords).

---

### 3. **No Source Credibility Weighting**

**Problem**: All sources treated equally regardless of reliability.

**Current State**:
- CoinDesk (established, fact-checked) = Same weight
- The Block (reputable, insider sources) = Same weight  
- Random scraped blog = Same weight
- Reddit post = Same weight

**Impact**: Rumors and unverified claims score as high as confirmed reports from Bloomberg or Reuters.

**Missing**: Source credibility tier system (0.7-1.3 multiplier based on track record).

---

### 4. **No Cross-Source Deduplication/Corroboration**

**Problem**: Same event reported by 5 sources = 5 separate "opportunities" instead of 1 highly-corroborated event.

**Example**:
- Bitcoin ETF approval breaks
- CoinDesk reports it → Stored as opportunity #1
- Cointelegraph reports it → Stored as opportunity #2
- The Block reports it → Stored as opportunity #3
- Bloomberg reports it → Stored as opportunity #4
- Decrypt reports it → Stored as opportunity #5

**What should happen**: Cluster these into **one opportunity with 5x corroboration strength** (which is a much stronger signal than a single-source scoop).

**Missing**: 
- Entity + event clustering (6-12h window)
- Title similarity detection (cosine similarity / fuzzy matching)
- Corroboration multiplier

---

### 5. **No Backtesting Loop**

**Problem**: Zero validation that high scores actually correlate with profit opportunities.

**Current Reality**: 
- A 9/10 score means "contains many hype keywords"
- NO data on whether 9/10 articles preceded actual price movements
- NO feedback mechanism to validate or tune weights

**What's missing**:
- Post-article price tracking (1h / 24h / 7d after publication)
- Correlation analysis: Did high-scored articles actually signal profitable moves?
- Automatic weight calibration based on real outcomes

**Why it matters**: Without backtesting, you're flying blind—just guessing which keywords matter instead of learning from reality.

---

### 6. **Static Keyword Weights Will Decay Fast**

**Problem**: Crypto narrative cycles rotate every 3-6 months. Hardcoded weights become stale.

**Narrative Rotation Examples**:
- 2021: "NFT", "metaverse", "play-to-earn" were hot
- 2022: "DeFi", "yield farming" dominated  
- 2023: "Layer 2", "zk-rollups", "scaling" took over
- 2024: "AI agents", "RWA tokenization", "restaking"
- 2025: "DePIN", "intent-based protocols", "modular chains"

**Current System**: Hardcoded weights from today won't reflect tomorrow's narratives.

**Solutions needed**:
1. Periodic re-weighting based on backtested performance
2. Supplement with LLM semantic scoring (contextual understanding vs. keyword matching)
3. Track trending keywords dynamically (7-day / 30-day windows)

---

### 7. **Recency Filter May Miss Important Slow-Building Stories**

**Problem**: 24-48h hard cutoff misses regulatory shifts, macro trends, and multi-week developments.

**Examples of what gets missed**:
- SEC regulatory framework evolving over 3 weeks → Ignored after day 2
- ETF approval process with multiple hearings → Only first 48h captured
- Country-level crypto adoption legislative process → Loses relevance after initial report

**What's needed**: 
- **Trending decay score**: Let important stories persist and re-surface when related events occur
- **Event chain tracking**: Link related articles across time (e.g., "ETF filing" → "SEC comment period" → "Approval decision")

---

## ✅ Proposed Redesign: Sentiment-Weighted Multi-Factor Scoring

### New Formula

```python
final_score = (base_category_score + keyword_score) \
              × sentiment_multiplier \
              × corroboration_multiplier \
              × source_credibility_weight \
              × recency_decay_factor
```

---

### 1. **Sentiment Multiplier** (Replaces Flat Addition)

**Current**: Sentiment calculated separately, doesn't affect profit score  
**New**: Sentiment gates the entire score

```python
sentiment_multipliers = {
    SentimentScore.VERY_POSITIVE: 1.3,
    SentimentScore.POSITIVE: 1.1,
    SentimentScore.NEUTRAL: 1.0,
    SentimentScore.NEGATIVE: 0.5,
    SentimentScore.VERY_NEGATIVE: 0.2
}
```

**Effect**: 
- "Hack drains protocol" contains high-value keywords but gets crushed by `×0.2`
- "Institutional adoption surge" gets boosted by `×1.3`

**Before vs After**:
```
Article: "SEC rejects Bitcoin ETF application"
Keywords: sec (1.0) + bitcoin (2.0) + etf (2.0) + base (6.0) = 11.0 → capped at 10.0 ✅

OLD: Score = 10.0 (HIGH PROFIT!) ❌
NEW: Score = 11.0 × 0.2 (NEGATIVE) = 2.2 (LOW PROFIT) ✅
```

---

### 2. **Corroboration Multiplier**

**Goal**: Recognize when multiple sources report the same event → stronger signal.

**Implementation**:

```python
# Cluster articles by entity + event within 6-12h window
# Use title similarity (cosine similarity on embeddings or fuzzy match)

corroboration_multipliers = {
    1: 1.0,    # Single source (treat normally)
    2-3: 1.15, # 2-3 sources confirm → modest boost
    4+: 1.3    # 4+ sources → strong signal boost
}
```

**Process**:
1. When storing article, check for similar articles within past 12h
2. Compare title similarity (threshold: 70%+ match on key entities)
3. If cluster found, update cluster score instead of storing duplicate
4. Apply corroboration multiplier

**Example**:
```
Article 1: "Bitcoin ETF approved by SEC" (CoinDesk) → Score: 8.5 × 1.0 = 8.5
Article 2: "SEC approves Bitcoin ETF" (Bloomberg) → Cluster detected → 8.5 × 1.15 = 9.78
Article 3: "Bitcoin spot ETF gets SEC approval" (The Block) → 8.5 × 1.15 = 9.78
Article 4: "SEC greenlights Bitcoin ETF" (Cointelegraph) → 8.5 × 1.3 = 11.05 → cap at 10.0

Result: ONE opportunity with score 10.0 and 4x corroboration badge
```

---

### 3. **Source Credibility Weight**

**Goal**: Trust established sources more than random blogs.

**Implementation**:

```python
source_credibility = {
    # Tier 1: Established financial news (1.2-1.3x)
    "bloomberg": 1.3,
    "reuters": 1.3,
    "financial_times": 1.25,
    "wsj": 1.25,
    
    # Tier 2: Reputable crypto-native (1.1-1.2x)
    "coindesk": 1.2,
    "the_block": 1.2,
    "cointelegraph": 1.15,
    "decrypt": 1.15,
    "blockworks": 1.1,
    
    # Tier 3: Niche but credible (1.0x)
    "bankless": 1.0,
    "defiant": 1.0,
    "thedefiant": 1.0,
    
    # Tier 4: Aggregators and forums (0.8-0.9x)
    "reddit": 0.8,
    "twitter": 0.8,
    "medium": 0.85,
    
    # Default for unknown sources
    "default": 0.9
}
```

**Effect**:
```
Same article content:
- Bloomberg reports: Score × 1.3 = 11.7 → 10.0 ✅
- Random blog: Score × 0.85 = 7.65 ✅

Bloomberg article surfaces higher in opportunities list.
```

**Future Enhancement**: Track source accuracy over time via backtesting and auto-adjust weights.

---

### 4. **Negation Handling** (Cheap Fix, Big Impact)

**Goal**: Detect when keywords appear in negative contexts.

**Implementation**:

```python
negation_patterns = [
    r'\b(not|no|never|deny|denies|denied|reject|rejects|rejected)\b',
    r'\b(fail|fails|failed|failure|falls through|postpone|postponed|delay|delayed)\b',
    r'\b(cancel|canceled|cancelled|cancellation|halt|halted|suspend|suspended)\b',
    r'\b(withdraw|withdrawn|reverses|reversed|abandons|abandoned)\b'
]

def check_negation_context(text, keyword, window=5):
    """
    Check if keyword appears within 'window' words of a negation term.
    If yes, return 0 (zero out keyword score) or negative multiplier.
    """
    # Find keyword position
    # Look ±window words around it
    # Check for negation patterns
    # Return adjustment factor (0.0 if negated, 1.0 if normal)
```

**Example**:
```
Text: "Ethereum partnership falls through"
Keyword: "partnership" → normally +1.0

Check context: "partnership" appears within 2 words of "falls through"
→ Negation detected → keyword_score = 0.0 (or ×0.0)

Result: Score drops significantly instead of adding points.
```

**Low-effort implementation**: Regex pass before keyword scoring. No need for full NLP parsing initially.

---

### 5. **Backtest Hook** (Critical for Learning)

**Goal**: Validate that high scores actually correlate with profitable signals.

**Implementation**:

```python
# Add to scheduler: Run 24h/7d after article stored

async def backtest_article(article_id):
    """
    1. Get article and mentioned assets (from keywords)
    2. Fetch price at article.created_at
    3. Fetch price at created_at + 1h, +24h, +7d
    4. Calculate % change
    5. Store: article_id, asset, predicted_score, actual_1h_change, actual_24h_change, actual_7d_change
    6. Over time: Correlate scores with outcomes
    """
    
    article = db.get_article(article_id)
    assets = extract_assets_from_keywords(article.keywords)
    
    for asset in assets:
        price_at_publish = get_coingecko_price(asset, article.created_at)
        price_1h = get_coingecko_price(asset, article.created_at + timedelta(hours=1))
        price_24h = get_coingecko_price(asset, article.created_at + timedelta(hours=24))
        price_7d = get_coingecko_price(asset, article.created_at + timedelta(days=7))
        
        pct_change_1h = (price_1h - price_at_publish) / price_at_publish * 100
        pct_change_24h = (price_24h - price_at_publish) / price_at_publish * 100
        pct_change_7d = (price_7d - price_at_publish) / price_at_publish * 100
        
        db.store_backtest_result({
            'article_id': article_id,
            'asset': asset,
            'predicted_score': article.profit_score,
            'actual_1h_pct': pct_change_1h,
            'actual_24h_pct': pct_change_24h,
            'actual_7d_pct': pct_change_7d,
            'timestamp': datetime.utcnow()
        })
```

**Analysis Dashboard**:
```python
# After collecting 1000+ backtested articles:

def analyze_score_accuracy():
    """
    1. Group articles by score buckets (0-2, 2-4, 4-6, 6-8, 8-10)
    2. Calculate average price movement per bucket
    3. Show correlation: Do 8-10 scores actually outperform 0-4 scores?
    4. Flag keywords that appear in high-scored but low-outcome articles → reduce weight
    5. Flag keywords that appear in low-scored but high-outcome articles → increase weight
    """
    pass
```

**Auto-tuning** (Advanced):
```python
# Use simple linear regression to optimize keyword weights

X = keyword_presence_matrix  # [n_articles × n_keywords] binary matrix
y = actual_price_movements   # [n_articles] actual % gains

# Solve: weights = argmin ||X @ weights - y||^2
optimized_weights = linear_regression(X, y)

# Update keyword weights in scoring function
```

**Why this matters**: Converts "hype score" into "validated profit signal" grounded in reality.

---

### 6. **Dynamic Keyword Weighting**

**Goal**: Adapt to narrative shifts instead of relying on static weights.

**Approach 1: Periodic Re-weighting via Backtesting** (Data-driven)
```python
# Every 30 days:
# 1. Run backtest analysis on last month's articles
# 2. Identify top-performing keywords (high correlation with positive outcomes)
# 3. Identify underperforming keywords (present in high-scored but low-outcome articles)
# 4. Adjust weights: top_performers += 0.2, underperformers -= 0.2
# 5. Log weight changes for transparency
```

**Approach 2: LLM Semantic Scoring** (Context-aware)
```python
def llm_score_supplement(title, content):
    """
    Call GPT-4 / Claude API with prompt:
    
    'You are a crypto investment analyst. Rate this news article 
    on a 0-10 scale for profit potential. Consider:
    - Positive vs negative sentiment
    - Market impact potential
    - Credibility of claims
    - Timing and relevance
    
    Article: {title} - {content[:500]}
    
    Return: {"score": X.X, "reasoning": "..."}'
    """
    
    llm_score = call_llm_api(prompt)
    
    # Hybrid approach: average keyword score and LLM score
    final_score = (keyword_score + llm_score) / 2
    
    return final_score
```

**Approach 3: Trending Keyword Detection** (Adaptive)
```python
# Track keyword frequency and price correlations over rolling 7-day / 30-day windows

def update_trending_keywords():
    """
    1. Count keyword frequency in last 7 days
    2. Compare to previous 7-day window
    3. If keyword frequency increased 2x+ AND associated assets moved positively → boost weight
    4. If keyword frequency decreased or outcomes were negative → reduce weight
    """
    
    trending_keywords = get_trending_analysis()
    
    for keyword, trend_data in trending_keywords.items():
        if trend_data['frequency_increase'] > 2.0 and trend_data['avg_outcome'] > 5.0:
            keyword_weights[keyword] *= 1.2  # Boost hot narratives
        elif trend_data['avg_outcome'] < 0:
            keyword_weights[keyword] *= 0.8  # Reduce failing narratives
```

---

### 7. **Event Chain Tracking & Trending Decay**

**Goal**: Keep important stories relevant beyond 48h hard cutoff.

**Implementation**:

```python
# Add to article model:
class NewsArticle:
    ...
    related_event_id: Optional[str]  # Link articles about same event
    event_stage: Optional[str]       # "initial", "development", "conclusion"
    trending_score: float            # Separate from recency
    last_related_update: datetime    # When related story last appeared

def calculate_trending_decay(article):
    """
    Instead of hard 48h cutoff, use decay function:
    
    trending_score = base_score × decay_factor
    
    decay_factor = e^(-λ × hours_since_publish) 
                   + boost_if_related_story_appeared
    
    Example:
    - Hour 0: decay = 1.0 (full score)
    - Hour 24: decay = 0.6
    - Hour 48: decay = 0.4
    - Hour 72: decay = 0.2
    
    BUT: If related story appears at hour 70 → decay resets to 0.8
    """
    
    hours_old = (datetime.utcnow() - article.created_at).total_seconds() / 3600
    base_decay = math.exp(-0.02 * hours_old)  # λ = 0.02
    
    # Check if related stories appeared recently
    related_boost = check_related_stories(article.related_event_id)
    
    trending_score = article.profit_score * (base_decay + related_boost)
    
    return trending_score
```

**Event Chain Example**:
```
Day 1: "SEC begins review of Bitcoin ETF application" 
       → stored with related_event_id="btc_etf_2024", stage="initial"

Day 3: Normally would be filtered out by 48h rule
       BUT: trending_score = 8.5 × 0.4 = 3.4 (still visible)

Day 7: "SEC extends Bitcoin ETF review period"
       → related_event_id="btc_etf_2024", stage="development"
       → Original article's trending_score boosted back to 8.5 × 0.7 = 5.95

Day 30: "SEC approves Bitcoin ETF"
        → related_event_id="btc_etf_2024", stage="conclusion"
        → All related articles re-surface in "event timeline" view
```

---

## 📋 Implementation Roadmap

### Phase 1: Quick Wins (1-2 days)
- [ ] **Sentiment multiplier**: Integrate sentiment into score calculation (not separate)
- [ ] **Negation handling**: Add regex-based negation detection
- [ ] **Source credibility**: Add simple tier-based weighting

### Phase 2: Deduplication (2-3 days)
- [ ] **Title clustering**: Implement fuzzy matching or embedding similarity
- [ ] **Corroboration multiplier**: Detect and reward multi-source stories
- [ ] **Store as clusters**: One opportunity per event, not per article

### Phase 3: Validation (1 week)
- [ ] **Backtest infrastructure**: Add price tracking via CoinGecko API
- [ ] **Asset extraction**: Parse keywords to identify tradeable assets
- [ ] **Data collection**: Start logging predicted vs actual outcomes
- [ ] **Analysis dashboard**: Visualize score accuracy over time

### Phase 4: Adaptive Scoring (2 weeks)
- [ ] **Auto-tuning**: Use regression to optimize keyword weights monthly
- [ ] **Trending keywords**: Track narrative shifts with rolling windows
- [ ] **LLM supplement**: Add semantic scoring for context-aware evaluation

### Phase 5: Advanced Features (ongoing)
- [ ] **Event chain tracking**: Link related articles across time
- [ ] **Trending decay**: Replace hard cutoff with decay function
- [ ] **User feedback loop**: Let users rate article quality → feed into scoring

---

## 🎯 Expected Improvements

### Current System (Keyword Hype Score)
- ✅ Fast and simple
- ❌ High false positive rate (negative news scores high)
- ❌ No validation against reality
- ❌ Static weights decay quickly
- ❌ Duplicate stories clutter results

### Redesigned System (Validated Profit Signal)
- ✅ Sentiment-gated (negative news scores low)
- ✅ Context-aware (negation detection)
- ✅ Source-weighted (trust established sources)
- ✅ Corroboration-rewarded (multi-source = stronger signal)
- ✅ Backtest-validated (learn from actual outcomes)
- ✅ Adaptive weights (adjust to narrative shifts)
- ✅ Event-aware (track related stories over time)

### Estimated Impact
- **False positive reduction**: 60-70% (via sentiment gating + negation)
- **Signal quality**: 3-5x improvement (via corroboration + source weighting)
- **Long-term accuracy**: Continuous improvement via backtesting loop
- **User trust**: Transparent scoring with validation metrics

---

## 💡 Additional Considerations

### Computational Cost
- **Sentiment multiplier**: Negligible (already calculated)
- **Negation detection**: ~10-20ms per article (regex)
- **Clustering**: ~50-100ms per article (embedding similarity)
- **Backtesting**: Runs async, 24h after publish (no realtime impact)
- **LLM scoring**: ~500ms + API cost (use as optional supplement)

### Data Requirements
- **Backtesting**: Needs CoinGecko API (free tier: 10-50 calls/min)
- **Embeddings**: Use sentence-transformers (local, free) or OpenAI API
- **Storage**: Add `backtest_results` table (~1MB per 1000 articles)

### Maintenance
- **Keyword weights**: Review monthly based on backtest data
- **Source credibility**: Update quarterly based on accuracy tracking
- **Negation patterns**: Expand as new edge cases discovered

---

## 📚 References & Resources

### Price Data APIs
- **CoinGecko**: Free tier, historical prices, 10k+ assets
- **CoinMarketCap**: Requires API key, more comprehensive
- **Binance API**: Real-time but only Binance-listed assets

### Text Similarity
- **sentence-transformers**: `all-MiniLM-L6-v2` (fast, local)
- **OpenAI embeddings**: `text-embedding-3-small` (accurate, paid)
- **fuzzywuzzy**: Simple string matching (good starting point)

### Sentiment Analysis
- **Current**: Keyword-based (fast, transparent)
- **Upgrade**: FinBERT (finance-tuned BERT model)
- **Advanced**: GPT-4 API (context-aware, expensive)

### Negation Detection
- **spaCy**: Dependency parsing for precise negation scope
- **Regex**: Fast approximation (5-word window checks)

---

## 🚀 Next Steps

1. **Review this document** with team
2. **Prioritize phases** based on business impact
3. **Start with Phase 1** (quick wins, immediate improvement)
4. **Set up backtesting infrastructure** ASAP (data collection takes time)
5. **Iterate based on validation metrics** (let data guide decisions)

---

**Document Version**: 1.0  
**Last Updated**: 2026-08-03  
**Author**: Senior Full Stack AI Developer Review  
**Status**: Ready for Implementation
