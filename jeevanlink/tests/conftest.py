"""Test configuration.

The suite always runs against a throwaway SQLite file. Without this the
tests would talk to the real PostgreSQL server whenever DATABASE_URL
happens to be set in the environment.
"""

import pytest

from jeevanlink import database


@pytest.fixture(autouse=True, scope="session")
def _force_sqlite_backend():
    original = database.IS_POSTGRES
    database.IS_POSTGRES = False
    yield
    database.IS_POSTGRES = original
