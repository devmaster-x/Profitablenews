"""Timezone-aware UTC helpers and a safe sqlite3 datetime adapter.

The default sqlite3 datetime adapter is deprecated as of Python 3.12 and
emits a warning on every bound ``datetime`` parameter. We register our own
adapter that serializes datetimes to naive-UTC text with microseconds so
that ``[start, end)`` range comparisons keep sub-second ordering; legacy
rows stored without microseconds still parse via ``fromisoformat``.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

_DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def utcnow() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def parse_dt(value: str | datetime | None) -> datetime:
    """Parse a stored/returned value as an aware-UTC datetime.

    Naive values (the legacy sqlite text format) are assumed to be UTC.
    ``None`` maps to now, matching the previous ``datetime.utcnow()``
    fallbacks used by the ORM-mapping layer.
    """
    if value is None:
        return utcnow()
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)


def _adapt_datetime(dt: datetime) -> str:
    """Serialize a datetime to naive-UTC text for sqlite storage."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(_DB_DATETIME_FORMAT)


sqlite3.register_adapter(datetime, _adapt_datetime)
