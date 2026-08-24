"""Notification persistence.

Tracks which donor got an SMS for which request. The UNIQUE constraint on
``(request_id, donor_id, channel)`` prevents a donor being notified twice
for the same request — that's the built-in deduplication.
"""

import sqlite3
from typing import List, Optional

from .database import get_db_connection

CHANNEL_SMS = "sms"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_EMAIL = "email"
CHANNEL_CONSOLE = "console"


def save_notification(
    request_id: int,
    donor_id: int,
    delivery_status: str,
    provider_message_id: Optional[str] = None,
    channel: str = CHANNEL_SMS,
) -> int:
    """Insert a notification record.

    Returns the new notification id. If a notification already exists for
    this (request, donor, channel) the INSERT fails on the UNIQUE
    constraint and the function returns -1 (existing row left untouched).
    """
    connection = get_db_connection()
    try:
        cursor = connection.execute(
            """
            INSERT INTO notifications (
                request_id,
                donor_id,
                channel,
                delivery_status,
                provider_message_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, donor_id, channel, delivery_status, provider_message_id),
        )
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        return -1
    finally:
        connection.close()


def donor_already_notified(
    request_id: int,
    donor_id: int,
    channel: Optional[str] = None,
) -> bool:
    """True if this donor was already alerted for this request.

    Pass ``channel`` to check one channel in particular. With no
    channel, any previous alert counts.
    """
    connection = get_db_connection()
    try:
        if channel is None:
            row = connection.execute(
                """
                SELECT id
                FROM notifications
                WHERE request_id = ?
                  AND donor_id = ?
                """,
                (request_id, donor_id),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT id
                FROM notifications
                WHERE request_id = ?
                  AND donor_id = ?
                  AND channel = ?
                """,
                (request_id, donor_id, channel),
            ).fetchone()
        return row is not None
    finally:
        connection.close()


def get_notifications_for_request(request_id: int) -> List[sqlite3.Row]:
    connection = get_db_connection()
    try:
        return connection.execute(
            """
            SELECT *
            FROM notifications
            WHERE request_id = ?
            ORDER BY sent_at ASC
            """,
            (request_id,),
        ).fetchall()
    finally:
        connection.close()
