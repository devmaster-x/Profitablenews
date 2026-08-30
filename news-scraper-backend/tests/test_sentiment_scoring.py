"""Tests for sentiment-aware profit scoring (Phase 1, Task 1.1/1.5)."""

import pytest

from news_scraper.scraper import NewsScraper
from news_scraper.models import NewsCategory, SentimentScore


@pytest.fixture(scope="module")
def scraper():
    return NewsScraper()


def score_article(scraper, title: str, content: str, category: NewsCategory) -> float:
    """Score an article the same way the scrape pipeline does."""
    sentiment = scraper.analyze_sentiment(f"{title} {content}")
    return scraper.calculate_profit_score(title, content, category, sentiment=sentiment)


class TestSentimentClassification:
    """analyze_sentiment() must classify positive/negative correctly."""

    def test_approved_is_positive(self, scraper):
        assert scraper.analyze_sentiment("Bitcoin ETF approved by SEC") == SentimentScore.POSITIVE

    def test_rejected_is_negative(self, scraper):
        assert scraper.analyze_sentiment("Bitcoin ETF rejected by SEC") == SentimentScore.NEGATIVE

    def test_on_hold_is_negative(self, scraper):
        # Regression: the live DB's top-scored article (10.0) was this exact case.
        assert scraper.analyze_sentiment("SEC keeps Nasdaq bitcoin options on hold") == SentimentScore.NEGATIVE

    def test_hack_is_negative(self, scraper):
        assert scraper.analyze_sentiment("Hack drains $50M from DeFi protocol") == SentimentScore.NEGATIVE

    def test_neutral_headline(self, scraper):
        assert scraper.analyze_sentiment("Markets quiet this week") == SentimentScore.NEUTRAL

    def test_airdrop_not_misread_as_negative(self, scraper):
        # Regression: substring matching counted 'drop' inside 'airdrop' as negative.
        assert scraper.analyze_sentiment("Major airdrop announced for holders") == SentimentScore.POSITIVE

    def test_against_not_misread_as_positive(self, scraper):
        # Regression: substring matching counted 'gain' inside 'against' as positive.
        assert scraper.analyze_sentiment("Company pushing against regulation") != SentimentScore.POSITIVE


class TestScoreDesaturation:
    """Regression (2026-08-29): the raw keyword sum is smoothly compressed, so
    distinct keyword densities produce distinct scores instead of piling up at
    exactly 10.0 (40% of the live DB before the fix)."""

    def test_denser_positive_article_scores_strictly_higher(self, scraper):
        light = score_article(
            scraper, "Bitcoin ETF approved", "SEC approves the ETF", NewsCategory.CRYPTO
        )
        dense = score_article(
            scraper,
            "Bitcoin ETF approved as institutional adoption surges",
            "SEC approves the spot bitcoin ETF; BlackRock and Fidelity launch with record "
            "volume, mainstream adoption and a breakout above resistance",
            NewsCategory.CRYPTO,
        )
        assert dense > light
        assert dense < 10.0  # smooth compression never pins at the cap

    def test_keyword_dense_negative_cannot_reach_top_scores(self, scraper):
        score = score_article(
            scraper,
            "Bitcoin ETF rejected as institutional adoption stalls",
            "SEC rejects the spot bitcoin ETF; BlackRock and Fidelity applications denied, "
            "listing halted and launch cancelled despite record volume expectations",
            NewsCategory.CRYPTO,
        )
        assert score < 6.0


class TestSentimentGatedScoring:
    """Negative news must score low even when it mentions positive keywords."""

    def test_positive_news_scores_high(self, scraper):
        """'ETF approved' should score higher than 'ETF rejected'."""
        approved = score_article(scraper, "Bitcoin ETF approved", "SEC approves the spot bitcoin ETF", NewsCategory.CRYPTO)
        rejected = score_article(scraper, "Bitcoin ETF rejected", "SEC rejects the bitcoin ETF application", NewsCategory.CRYPTO)
        assert approved > rejected
        # Success criterion from the plan: negative < 50% of equivalent positive news
        assert rejected < approved * 0.5

    def test_negative_news_scores_low(self, scraper):
        """'Hack drains protocol' should score low despite web3 keywords."""
        score = score_article(
            scraper,
            "Hack drains $50M from DeFi protocol",
            "Hackers exploit vulnerability and drain user funds",
            NewsCategory.DEFI,
        )
        assert score < 5.0

    def test_very_negative_article_filtered_by_threshold(self, scraper):
        """A very-negative article should fall below the 4.0 minimum filter."""
        score = score_article(
            scraper,
            "Protocol collapses after exploit, users lose everything",
            "Complete failure, bankruptcy and insolvency confirmed",
            NewsCategory.DEFI,
        )
        assert score < scraper.min_profit_score

    def test_neutral_news_baseline(self, scraper):
        """Neutral sentiment applies a 1.0 multiplier (no boost, no penalty)."""
        assert scraper.get_sentiment_multiplier(SentimentScore.NEUTRAL) == 1.0

    def test_multipliers_are_ordered(self, scraper):
        assert (
            scraper.get_sentiment_multiplier(SentimentScore.VERY_POSITIVE)
            > scraper.get_sentiment_multiplier(SentimentScore.POSITIVE)
            > scraper.get_sentiment_multiplier(SentimentScore.NEUTRAL)
            > scraper.get_sentiment_multiplier(SentimentScore.NEGATIVE)
            > scraper.get_sentiment_multiplier(SentimentScore.VERY_NEGATIVE)
        )

    def test_partnership_vs_falls_through(self, scraper):
        ok = score_article(scraper, "Coinbase partnership announced", "New partnership expands ecosystem", NewsCategory.CRYPTO)
        failed = score_article(scraper, "Coinbase partnership falls through", "The deal was cancelled", NewsCategory.CRYPTO)
        assert failed < ok

    def test_score_capped_at_ten(self, scraper):
        score = score_article(
            scraper,
            "Bitcoin Ethereum ETF approved, institutional adoption surge",
            "Breakthrough approval, funding raised, partnership launch, airdrop",
            NewsCategory.CRYPTO,
        )
        assert score <= 10.0
