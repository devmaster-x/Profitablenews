from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class NewsCategory(str, Enum):
    MARKET = "market"
    SOFTWARE = "software"
    CRYPTO = "crypto"
    STARTUP = "startup"
    TECH_EARNINGS = "tech_earnings"
    GENERAL = "general"
    AI_ML = "ai_ml"  # New category for AI/ML news
    BLOCKCHAIN = "blockchain"  # New category for blockchain tech
    INVESTMENT = "investment"  # New category for investment opportunities

class SentimentScore(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"

class MarketImpact(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class InvestmentType(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    STARTUP = "startup"
    REAL_ESTATE = "real_estate"
    COMMODITIES = "commodities"
    FOREX = "forex"

class NewsArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=1000)
    category: NewsCategory = NewsCategory.GENERAL
    sentiment: Optional[SentimentScore] = None
    profit_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    keywords: Optional[List[str]] = Field(default_factory=list)
    # New enhanced fields for better profit analysis
    market_impact: Optional[MarketImpact] = None
    investment_type: Optional[InvestmentType] = None
    potential_return: Optional[float] = Field(None, ge=0.0, le=1000.0, description="Potential return percentage")
    risk_level: Optional[float] = Field(None, ge=1.0, le=10.0, description="Risk level 1-10")
    time_horizon: Optional[str] = Field(None, description="Short/Medium/Long term opportunity")
    related_companies: Optional[List[str]] = Field(default_factory=list, description="Related company names")
    market_cap_impact: Optional[str] = Field(None, description="Impact on market capitalization")
    regulatory_impact: Optional[str] = Field(None, description="Regulatory implications")

class NewsArticleCreate(NewsArticleBase):
    pass

class NewsArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    source: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=1000)
    category: Optional[NewsCategory] = None
    sentiment: Optional[SentimentScore] = None
    profit_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    keywords: Optional[List[str]] = None
    # New enhanced fields
    market_impact: Optional[MarketImpact] = None
    investment_type: Optional[InvestmentType] = None
    potential_return: Optional[float] = Field(None, ge=0.0, le=1000.0)
    risk_level: Optional[float] = Field(None, ge=1.0, le=10.0)
    time_horizon: Optional[str] = None
    related_companies: Optional[List[str]] = None
    market_cap_impact: Optional[str] = None
    regulatory_impact: Optional[str] = None

class NewsArticle(NewsArticleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NewsArticleResponse(BaseModel):
    articles: List[NewsArticle]
    total: int
    page: int
    per_page: int
    total_pages: int

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

# New models for enhanced analytics
class ProfitOpportunity(BaseModel):
    article_id: int
    title: str
    profit_score: float
    potential_return: float
    risk_level: float
    investment_type: InvestmentType
    time_horizon: str
    created_at: datetime

class MarketTrend(BaseModel):
    category: NewsCategory
    trend_direction: str  # "up", "down", "stable"
    confidence_score: float
    affected_companies: List[str]
    timeframe: str
