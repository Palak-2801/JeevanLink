"""Blood request repository functions."""

import secrets
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .database import get_db_connection

# Statuses used across the platform. Keep the strings in sync with the UI.
OPEN = "open"
ALERTED = "alerted"
ACCEPTED = "accepted"
FULFILLED = "fulfilled"
CANCELLED = "cancelled"
EXPIRED = "expired"

# Statuses a request may be in when a donor is still allowed to accept it.
ACCEPTABLE_STATUSES = (OPEN, ALERTED)

# Urgency -> precedence for ordering open requests (lower = higher priority).
_URGENCY_ORDER = {"critical": 1, "urgent": 2, "normal": 3}


def _generate_public_token() -> str:
    # url-safe, cryptographically random. Hard to guess, good for a public link.
    return secrets.token_urlsafe(24)


def create_blood_request(data: Dict[str, Any]) -> Tuple[int, str]:
    """Create a new request and return ``(request_id, public_token)``."""
    public_token = _generate_public_token()
    connection = get_db_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO blood_requests (
                public_token,
                requester_name,
                requester_phone,
                blood_group,
                blood_component,
                units,
                hospital,
                urgency,
                latitude,
                longitude,
                status,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                public_token,
                data["requester_name"],
                data["requester_phone"],
                data["blood_group"],
                data.get("blood_component"),
                data.get("units", 1),
                data["hospital"],
                data["urgency"],
                data["latitude"],
                data["longitude"],
                OPEN,
                data.get("expires_at"),
            ),
        )
        request_id = cursor.lastrowid
        connection.commit()
        return request_id, public_token
    finally:
        connection.close()


def get_request_by_id(request_id: int) -> Optional[sqlite3.Row]:
    connection = get_db_connection()
    try:
        return connection.execute(
            "SELECT * FROM blood_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    finally:
        connection.close()


def get_request_by_token(public_token: str) -> Optional[sqlite3.Row]:
    connection = get_db_connection()
    try:
        return connection.execute(
            "SELECT * FROM blood_requests WHERE public_token = ?",
            (public_token,),
        ).fetchone()
    finally:
        connection.close()


def update_request_status(request_id: int, status: str) -> None:
    connection = get_db_connection()
    try:
        connection.execute(
            """
            UPDATE blood_requests
            SET status = ?
            WHERE id = ?
            """,
            (status, request_id),
        )
        connection.commit()
    finally:
        connection.close()


def accept_request(request_token: str, donor_id: int) -> bool:
    """Atomically accept a request for a donor.

    Returns True only if this call actually transitioned the request to
    ``accepted``. The ``WHERE status IN ('open','alerted')`` guard means
    that if two donors accept at the same time, only the first UPDATE
    affects a row; the second sees zero rows changed and returns False.
    """
    connection = get_db_connection()
    try:
        cursor = connection.execute(
            """
            UPDATE blood_requests
            SET status = 'accepted',
                accepted_donor_id = ?
            WHERE public_token = ?
              AND status IN ('open', 'alerted')
            """,
            (donor_id, request_token),
        )
        connection.commit()
        accepted = cursor.rowcount == 1
        return accepted
    finally:
        connection.close()


def get_request_with_donor(public_token: str) -> Optional[sqlite3.Row]:
    """Request details joined with the accepted donor (if any).

    Uses LEFT JOIN so an un-accepted request still returns its row with
    NULL donor columns.
    """
    connection = get_db_connection()
    try:
        query = """
            SELECT
                blood_requests.id,
                blood_requests.public_token,
                blood_requests.blood_group,
                blood_requests.hospital,
                blood_requests.status,
                blood_requests.units,
                blood_requests.created_at,

                donors.name AS donor_name,
                donors.phone AS donor_phone,
                donors.latitude AS donor_latitude,
                donors.longitude AS donor_longitude

            FROM blood_requests

            LEFT JOIN donors
                ON donors.id = blood_requests.accepted_donor_id

            WHERE blood_requests.public_token = ?
        """
        return connection.execute(query, (public_token,)).fetchone()
    finally:
        connection.close()


def list_open_requests(include: Tuple[str, ...] = ACCEPTABLE_STATUSES) -> List[sqlite3.Row]:
    """Open/alerted requests, most urgent first, then oldest first."""
    placeholders = ",".join("?" for _ in include)
    connection = get_db_connection()
    try:
        query = f"""
            SELECT *
            FROM blood_requests
            WHERE status IN ({placeholders})
            ORDER BY
                CASE urgency
                    WHEN 'critical' THEN 1
                    WHEN 'urgent' THEN 2
                    WHEN 'normal' THEN 3
                    ELSE 4
                END,
                created_at ASC
        """
        return connection.execute(query, include).fetchall()
    finally:
        connection.close()
