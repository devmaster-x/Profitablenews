"""Shared pytest fixtures."""

import os
import tempfile

import pytest


@pytest.fixture()
def tmp_db_path():
    """Temporary SQLite file path; cleaned up after each test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield os.path.join(tmp, "test.db")
