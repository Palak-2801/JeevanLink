"""Insert demo data so the app has something to show immediately.

Usage:
    python -m jeevanlink.init_db     # first create the tables
    python -m jeevanlink.seed_data   # then add demo rows

Safe to run more than once: donors use INSERT OR IGNORE keyed on the
UNIQUE phone, so existing rows are left untouched.
"""

import secrets
from datetime import datetime, timedelta, timezone

from .database import get_db_connection

# Sample donors near Lucknow (lat/lon in the city).
#
# The example.com addresses are reserved for documentation and cannot
# receive mail, so seeded donors fall back to the console. Register a
# real donor through /donate to see an actual email or WhatsApp alert.
DEMO_DONORS = [
    # (name, phone, email, age, blood_group, available, verified,
    #  sms_consent, lat, lon)
    ("Aarav", "9000000001", "aarav@example.com", 24, "O+", 1, 1, 1, 26.8467, 80.9462),
    ("Priya", "9000000002", "priya@example.com", 26, "O+", 1, 1, 1, 26.8560, 80.9580),
    ("Rohan", "9000000003", "rohan@example.com", 28, "O+", 1, 0, 1, 26.8650, 80.9700),
    ("Sneha", "9000000004", "sneha@example.com", 30, "A+", 1, 1, 1, 26.8500, 80.9500),
    ("Vikram", "9000000005", "vikram@example.com", 33, "B+", 0, 1, 1, 26.8400, 80.9400),
    ("Kavya", "9000000006", "kavya@example.com", 22, "O-", 1, 1, 1, 26.8600, 80.9650),
]


def seed_donors() -> int:
    connection = get_db_connection()
    try:
        cursor = connection.executemany(
            """
            INSERT OR IGNORE INTO donors (
                name,
                phone,
                email,
                age,
                blood_group,
                available,
                verified,
                sms_consent,
                latitude,
                longitude
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEMO_DONORS,
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def seed_open_request() -> int:
    """Create one demo open request (O+, critical) if none exists."""
    connection = get_db_connection()
    try:
        existing = connection.execute(
            """
            SELECT id
            FROM blood_requests
            WHERE requester_phone = '9100000001'
            """
        ).fetchone()
        if existing is not None:
            return 0

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                secrets.token_urlsafe(24),
                "Demo Requester",
                "9100000001",
                "O+",
                "whole_blood",
                2,
                "CGH Lucknow",
                "critical",
                26.8500,
                80.9500,
                (
                    datetime.now(timezone.utc) + timedelta(days=1)
                ).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        connection.commit()
        return 1
    finally:
        connection.close()


def main() -> None:
    inserted = seed_donors()
    created = seed_open_request()
    print(f"Demo data seeded: {inserted} donor(s) inserted, {created} request(s) created.")


if __name__ == "__main__":
    main()
