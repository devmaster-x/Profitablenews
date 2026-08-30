"""Tests for negation-context detection (Phase 1, Task 1.2/1.5)."""

import pytest

from news_scraper.scraper import NewsScraper


@pytest.fixture(scope="module")
def scraper():
    return NewsScraper()


class TestNegationDetection:
    """check_negation_context() returns 0.0 when a keyword is negated."""

    def test_ethereum_partnership_is_valid(self, scraper):
        assert scraper.check_negation_context("Ethereum partnership announced today", "partnership") == 1.0

    def test_ethereum_partnership_falls_through(self, scraper):
        assert scraper.check_negation_context("Ethereum partnership falls through", "partnership") == 0.0

    def test_bitcoin_etf_approved(self, scraper):
        assert scraper.check_negation_context("Bitcoin ETF approved by SEC", "etf") == 1.0

    def test_bitcoin_etf_rejected(self, scraper):
        assert scraper.check_negation_context("Bitcoin ETF rejected by SEC", "etf") == 0.0

    def test_negation_reaches_asset_keyword(self, scraper):
        assert scraper.check_negation_context("Bitcoin ETF rejected by SEC", "bitcoin") == 0.0

    def test_contraction_wasnt(self, scraper):
        # Regression: live DB's 10.0 article was "wasn't a sale"
        assert scraper.check_negation_context("The ETF wasn't approved after all", "etf") == 0.0

    def test_contraction_wont(self, scraper):
        assert scraper.check_negation_context("Ethereum won't support the upgrade", "ethereum") == 0.0

    def test_on_hold_phrase(self, scraper):
        assert scraper.check_negation_context("SEC keeps Nasdaq bitcoin options on hold", "bitcoin") == 0.0

    def test_multiword_keyword(self, scraper):
        assert scraper.check_negation_context("The proof of stake upgrade was delayed", "proof of stake") == 0.0

    def test_multiword_keyword_valid(self, scraper):
        assert scraper.check_negation_context("The proof of stake upgrade went live", "proof of stake") == 1.0

    def test_keyword_absent_returns_valid(self, scraper):
        assert scraper.check_negation_context("Nothing relevant here at all", "ethereum") == 1.0

    def test_empty_keyword_returns_valid(self, scraper):
        assert scraper.check_negation_context("Some text", "") == 1.0

    def test_integration_valid_when_positive(self, scraper):
        assert scraper.check_negation_context("Coinbase integration launches next week", "integration") == 1.0

    def test_out_of_window_negation_not_triggered(self, scraper):
        # 'rejected' is more than 6 words away from 'ethereum'
        text = "The proposal was rejected. In totally unrelated news, ethereum developers shipped a new release."
        assert scraper.check_negation_context(text, "ethereum") == 1.0
