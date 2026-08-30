"""FastAPI application factory for the News Scraper.

Standalone: ``uvicorn news_scraper.main:app`` (creates the default ``db`` /
``scraper`` / ``scheduler`` singletons once, at import).
Embedded: ``from news_scraper.main import create_app`` and pass explicit
dependencies; the routers resolve them via ``news_scraper.api.deps``.

Routes live at the root paths the frontend calls directly (``/articles``,
``/stats``, ...). Hosts that want a namespace can mount the app under their own
prefix (e.g. ``app.mount("/api/news", create_app(...))``).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from news_scraper.api.routers import (
    analytics,
    articles,
    assets,
    backtest,
    clusters,
    notifications,
    scrape,
    scheduler as scheduler_router,
)
from news_scraper.config import get_settings, settings
from news_scraper.persistent_database import PersistentDatabase
from news_scraper.scraper import NewsScraper
from news_scraper.scheduler import NewsScrapingScheduler

logger = logging.getLogger(__name__)

# Standalone defaults. Host applications should call create_app() with explicit
# dependencies instead of relying on these module-level singletons.
db = PersistentDatabase(settings.database_path)
scraper = NewsScraper(settings=settings, db=db)
scheduler = NewsScrapingScheduler(scraper=scraper)


def create_app(
    settings=None,
    db=None,
    scraper=None,
    scheduler=None,
) -> FastAPI:
    """Build a FastAPI app with injectable services.

    Omitted dependencies fall back to the module-level defaults above. Explicit
    dependencies are exposed through ``app.state`` so the router dependencies
    (``news_scraper.api.deps``) prefer them over the module globals.
    """
    app_settings = settings or get_settings()

    app = FastAPI(
        title="News Scraper API",
        description="API for managing scraped news articles with profit analysis",
        version="2.0.0",
    )

    app.add_middleware(CORSMiddleware, **app_settings.cors_kwargs())

    if db is not None:
        app.state.db = db
    if scraper is not None:
        app.state.scraper = scraper
    if scheduler is not None:
        app.state.scheduler = scheduler

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "message": "News Scraper API is running"}

    app.include_router(articles.router)
    app.include_router(analytics.router)
    app.include_router(assets.router)
    app.include_router(clusters.router)
    app.include_router(scrape.router)
    app.include_router(scheduler_router.router)
    app.include_router(backtest.router)
    app.include_router(notifications.router)

    # Fail loudly at startup, not at first scrape: clustering needs the
    # sentence-transformers stack (torch). find_spec checks availability
    # without paying the multi-second import cost.
    if app_settings.clustering_enabled:
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is None:
            logger.error(
                "code=CONFIG_CLUSTERING_DEPS_MISSING clustering_enabled=true but "
                "sentence-transformers is not installed — scrape runs will fail at the "
                "clustering step. Run `poetry install` or set CLUSTERING_ENABLED=false."
            )

    # Production autostart (env SCHEDULER_AUTOSTART=true): the scheduler thread
    # begins with the server instead of waiting for a manual POST /scheduler/start.
    # Default False keeps tests and embedded hosts inert.
    if app_settings.scheduler_autostart:
        injected_scheduler = scheduler

        def _start_scheduler() -> None:
            sched = injected_scheduler
            if sched is None:
                from news_scraper import main as main_module

                sched = main_module.scheduler
            if not sched.is_running:
                logger.info("scheduler_autostart=true — starting scheduler thread")
                sched.start_scheduler()

        app.add_event_handler("startup", _start_scheduler)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "news_scraper.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
        log_level=settings.log_level.lower(),
    )
