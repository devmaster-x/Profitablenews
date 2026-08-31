"""Asset-extractor coverage tests — especially the Track B long-tail tokens
(trading-system DEX collector pairs) added 2026-08-31 so the news-uplift join
can fire on them, and the ambiguity policy that keeps bare English words from
producing false tags."""

from news_scraper.asset_extractor import asset_extractor


class TestTrackBTokenCoverage:
    def test_long_tail_dex_tokens_extracted(self):
        found = asset_extractor.extract_assets(
            "Aerodrome flips Uniswap on Base as PENDLE and GMX rally", "", [], limit=5
        )
        symbols = {a["symbol"] for a in found}
        assert {"AERO", "PENDLE", "GMX"} <= symbols

    def test_qualified_keywords_match(self):
        found = asset_extractor.extract_assets(
            "Based Brett and the Degen token surge on Virtuals Protocol news", "", [], limit=5
        )
        symbols = {a["symbol"] for a in found}
        assert {"BRETT", "DEGEN", "VIRTUAL"} <= symbols

    def test_ambiguous_bare_words_do_not_match(self):
        found = asset_extractor.extract_assets(
            "A degen trader made magic with virtual reality and his friend Brett", "", []
        )
        symbols = {a["symbol"] for a in found}
        assert symbols.isdisjoint({"DEGEN", "MAGIC", "VIRTUAL", "BRETT"})

    def test_coingecko_ids_present_for_new_tokens(self):
        for keyword, expected_id in [
            ("aerodrome", "aerodrome-finance"),
            ("toshi", "toshi"),
            ("pendle", "pendle"),
            ("dydx", "dydx-chain"),
        ]:
            asset = asset_extractor.asset_mapping[keyword]
            assert asset["coingecko_id"] == expected_id
            assert asset["type"] == "crypto"
