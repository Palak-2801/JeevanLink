"""Request events — the audit trail for each request's life-cycle."""

import sqlite3
from typing import List, Optional

from .database import get_db_connection


def add_request_event(
    request_id: int,
    event_type: str,
    actor_type: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> None:
    connection = get_db_connection()
    try:
        connection.execute(
            """
            INSERT INTO request_events (
                request_id,
                event_type,
                actor_type,
                actor_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (request_id, event_type, actor_type, actor_id),
        )
        connection.commit()
    finally:
        connection.close()


def get_request_events(request_id: int) -> List[sqlite3.Row]:
    connection = get_db_connection()
    try:
        return connection.execute(
            """
            SELECT *
            FROM request_events
            WHERE request_id = ?
            ORDER BY created_at ASC
            """,
            (request_id,),
        ).fetchall()
    finally:
        connection.close()
