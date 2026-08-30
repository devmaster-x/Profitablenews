"""FastAPI dependency providers.

Each provider returns an ``app.state`` override when ``create_app`` was given
explicit dependencies (embedded host), otherwise the live default from the
``news_scraper.main`` module — resolved at request time so tests can swap
``main.db`` and the swap takes effect on the next request.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request


def _state_override(request: Request, name: str) -> Any:
    return getattr(request.app.state, name, None)


def get_db(request: Request):
    override = _state_override(request, "db")
    if override is not None:
        return override
    from news_scraper import main

    return main.db


def get_scraper(request: Request):
    override = _state_override(request, "scraper")
    if override is not None:
        return override
    from news_scraper import main

    return main.scraper


def get_scheduler(request: Request):
    override = _state_override(request, "scheduler")
    if override is not None:
        return override
    from news_scraper import main

    return main.scheduler


def get_backtester(request: Request):
    override = _state_override(request, "backtester")
    if override is not None:
        return override
    from news_scraper.backtester import backtester

    return backtester
