"""Tests for source credibility weighting (Phase 1, Task 1.3/1.5)."""

import pytest

from news_scraper.scraper import NewsScraper


@pytest.fixture(scope="module")
def scraper():
    return NewsScraper()


class TestSourceCredibility:
    def test_tier1_crypto_newsrooms(self, scraper):
        assert scraper.get_source_credibility("coindesk_rss") == 1.2
        assert scraper.get_source_credibility("the_block") == 1.2
        assert scraper.get_source_credibility("theblock_rss") == 1.2

    def test_official_and_magazine_sources(self, scraper):
        assert scraper.get_source_credibility("ethereum_foundation") == 1.15
        assert scraper.get_source_credibility("bitcoin_magazine") == 1.05

    def test_all_configured_sources_are_mapped(self, scraper):
        """Every source the scraper actually scrapes must have an explicit weight."""
        configured = set(scraper.rss_sources.keys()) | set(scraper.news_sources.keys())
        for source in configured:
            weight = scraper.get_source_credibility(source)
            assert source in scraper.source_credibility, f"{source} falls through to default"
            assert 0.9 <= weight <= 1.2

    def test_unknown_source_uses_default(self, scraper):
        assert scraper.get_source_credibility("random_blog_xyz") == scraper.source_credibility["default"]

    def test_credibility_changes_score(self, scraper):
        """Same base score from Bloomberg-tier vs community source differs."""
        coindesk = scraper.apply_source_credibility(8.0, "coindesk_rss")
        hackernews = scraper.apply_source_credibility(8.0, "hacker_news")
        assert coindesk == pytest.approx(9.6)
        assert hackernews == pytest.approx(7.2)
        assert coindesk > hackernews

    def test_credibility_capped_at_ten(self, scraper):
        assert scraper.apply_source_credibility(9.5, "coindesk_rss") == 10.0

    def test_credibility_does_not_inflate_low_scores_above_threshold(self, scraper):
        """A 1.2x weight on a 3.0 score must stay below the 4.0 filter."""
        assert scraper.apply_source_credibility(3.0, "coindesk_rss") == pytest.approx(3.6)
