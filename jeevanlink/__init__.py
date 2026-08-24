"""JeevanLink — Blood donation & request platform (database layer).

This package implements the SQLite persistence layer for JeevanLink.
It does NOT know about Flask or the frontend — the API layer calls
these functions, and the frontend talks to the API.
"""

__version__ = "0.1.0"

# Load a .env file, if one exists, before any module reads its settings.
from .config import load_env as _load_env  # noqa: E402

_load_env()
