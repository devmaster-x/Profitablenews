"""API layer for the news scraper.

FastAPI routers grouped by domain, wired together by ``news_scraper.main``.
Dependencies are injected via ``news_scraper.api.deps`` so the same routers
work for the standalone app and an embedded host.
"""
