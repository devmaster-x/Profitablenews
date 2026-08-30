"""Web3 news scraper feature package.

The package is designed to be *embedded* into a larger application:
- ``news_scraper.main.create_app`` builds a FastAPI app (or returns an
  already-built ``app`` to be included into a host app's router tree).
- All services (database, scraper, scheduler, backtester) are resolved
  through dependency-injection providers in ``news_scraper.api.deps`` so a
  host application can swap them (e.g. a Postgres-backed repository) without
  touching the routes.

It can also be run standalone via ``uvicorn news_scraper.main:app``.
"""

__version__ = "2.0.0"
