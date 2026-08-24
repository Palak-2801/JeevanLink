"""Admin statistics and reporting queries."""

import sqlite3
from typing import Dict, List

from .database import get_db_connection


def get_donor_count() -> int:
    connection = get_db_connection()
    try:
        return connection.execute("SELECT COUNT(*) FROM donors").fetchone()[0]
    finally:
        connection.close()


def get_available_donor_count() -> int:
    connection = get_db_connection()
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM donors WHERE available = 1"
        ).fetchone()[0]
    finally:
        connection.close()


def get_open_request_count() -> int:
    connection = get_db_connection()
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM blood_requests WHERE status IN ('open', 'alerted')"
        ).fetchone()[0]
    finally:
        connection.close()


def get_fulfilled_request_count() -> int:
    connection = get_db_connection()
    try:
        return connection.execute(
            "SELECT COUNT(*) FROM blood_requests WHERE status = 'fulfilled'"
        ).fetchone()[0]
    finally:
        connection.close()


def get_admin_stats() -> Dict[str, int]:
    """Single call that returns the counts shown on the admin dashboard."""
    connection = get_db_connection()
    try:
        totals = connection.execute(
            "SELECT COUNT(*) FROM donors"
        ).fetchone()[0]
        available = connection.execute(
            "SELECT COUNT(*) FROM donors WHERE available = 1"
        ).fetchone()[0]
        open_requests = connection.execute(
            "SELECT COUNT(*) FROM blood_requests WHERE status IN ('open', 'alerted')"
        ).fetchone()[0]
        fulfilled = connection.execute(
            "SELECT COUNT(*) FROM blood_requests WHERE status = 'fulfilled'"
        ).fetchone()[0]
        return {
            "total_donors": totals,
            "available_donors": available,
            "open_requests": open_requests,
            "fulfilled_requests": fulfilled,
        }
    finally:
        connection.close()


def get_recent_events(limit: int = 20) -> List[sqlite3.Row]:
    """Latest events across all requests, newest first."""
    connection = get_db_connection()
    try:
        return connection.execute(
            """
            SELECT request_events.*, blood_requests.public_token
            FROM request_events
            LEFT JOIN blood_requests
                ON blood_requests.id = request_events.request_id
            ORDER BY request_events.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        connection.close()
