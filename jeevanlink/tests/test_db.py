"""Tests for the JeevanLink database layer.

Run from the project root:
    python -m pytest jeevanlink/tests -q
"""

import sqlite3
from pathlib import Path

import pytest

import jeevanlink.database as database
from jeevanlink import admin, donors, events, matching, notifications, requests
from jeevanlink.database import get_db_connection

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"
SCHEMA = SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Point the database at a throwaway file, freshly initialised."""
    db_file = tmp_path / "test_jeevanlink.db"
    monkeypatch.setattr(database, "DATABASE_NAME", db_file)
    conn = get_db_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return db_file


def _add_donor(**overrides):
    data = {
        "name": "Test Donor",
        "phone": "9000000000",
        "age": 25,
        "blood_group": "O+",
        "available": True,
        "sms_consent": True,
        "latitude": 26.8467,
        "longitude": 80.9462,
    }
    data.update(overrides)
    return donors.create_donor(data)


def _add_request(**overrides):
    data = {
        "requester_name": "Need Blood",
        "requester_phone": "9100000000",
        "blood_group": "O+",
        "units": 1,
        "hospital": "CGH Lucknow",
        "urgency": "critical",
        "latitude": 26.8500,
        "longitude": 80.9500,
    }
    data.update(overrides)
    return requests.create_blood_request(data)


# ---- schema ---------------------------------------------------------------


def test_all_tables_exist(db):
    conn = get_db_connection()
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"donors", "blood_requests", "notifications", "request_events"} <= names


# ---- donors ---------------------------------------------------------------


def test_create_and_get_donor(db):
    donor_id = _add_donor(name="Aarav", phone="9000000001")
    row = donors.get_donor_by_id(donor_id)
    assert row["name"] == "Aarav"
    assert row["available"] == 1
    assert row["verified"] == 0  # always 0 on registration


def test_donor_phone_is_unique(db):
    _add_donor(phone="9000000002")
    with pytest.raises(sqlite3.IntegrityError):
        _add_donor(name="Duplicate", phone="9000000002")


def test_update_availability(db):
    donor_id = _add_donor()
    donors.update_donor_availability(donor_id, False)
    assert donors.get_donor_by_id(donor_id)["available"] == 0


def test_update_location(db):
    donor_id = _add_donor()
    donors.update_donor_location(donor_id, 28.6139, 77.2090)
    row = donors.get_donor_by_id(donor_id)
    assert row["latitude"] == 28.6139
    assert row["longitude"] == 77.2090


def test_candidate_donors_filters(db):
    # Eligible O+ with location + consent.
    _add_donor(phone="9000000010")
    # Right group but not available.
    _add_donor(phone="9000000011", available=False)
    # Right group but no SMS consent.
    _add_donor(phone="9000000012", sms_consent=False)
    # Right group but no location.
    _add_donor(phone="9000000013", latitude=None, longitude=None)
    # Wrong blood group.
    _add_donor(phone="9000000014", blood_group="A+")

    candidates = donors.get_candidate_donors("O+")
    phones = {c["phone"] for c in candidates}
    assert phones == {"9000000010"}


# ---- requests -------------------------------------------------------------


def test_create_and_get_request(db):
    request_id, token = _add_request()
    row = requests.get_request_by_token(token)
    assert row["id"] == request_id
    assert row["status"] == "open"


def test_public_token_is_unique(db):
    _, token = _add_request()
    conn = get_db_connection()
    with pytest.raises(sqlite3.IntegrityError):
        # Second row reusing the same public_token must be rejected.
        conn.execute(
            "INSERT INTO blood_requests (public_token, requester_name, requester_phone,"
            " blood_group, units, hospital, urgency, latitude, longitude, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')",
            (token, "X", "9100000002", "O+", 1, "H", "normal", 26.0, 80.0),
        )
    conn.close()


def test_accept_request_is_atomic(db):
    d1 = _add_donor(phone="9000000020")
    d2 = _add_donor(phone="9000000021")
    _, token = _add_request()

    first = requests.accept_request(token, d1)
    second = requests.accept_request(token, d2)

    assert first is True
    assert second is False

    row = requests.get_request_by_token(token)
    assert row["status"] == "accepted"
    assert row["accepted_donor_id"] == d1


def test_update_request_status(db):
    _, token = _add_request()
    row = requests.get_request_by_token(token)
    requests.update_request_status(row["id"], "fulfilled")
    assert requests.get_request_by_token(token)["status"] == "fulfilled"


def test_request_with_donor_join(db):
    donor_id = _add_donor(phone="9000000030", name="Rahul")
    _, token = _add_request()
    requests.accept_request(token, donor_id)

    row = requests.get_request_with_donor(token)
    assert row["donor_name"] == "Rahul"
    assert row["donor_phone"] == "9000000030"
    assert row["status"] == "accepted"


def test_open_requests_urgency_order(db):
    # normal first created, critical second -> critical should rank first.
    _, token_normal = _add_request(urgency="normal", requester_phone="9100000003")
    _, token_critical = _add_request(urgency="critical", requester_phone="9100000004")

    rows = requests.list_open_requests()
    tokens = [r["public_token"] for r in rows]
    assert tokens.index(token_critical) < tokens.index(token_normal)


# ---- notifications --------------------------------------------------------


def test_notification_created_and_deduplicated(db):
    donor_id = _add_donor()
    request_id, _ = _add_request()

    nid = notifications.save_notification(request_id, donor_id, "delivered", "provider-1")
    assert nid > 0

    # Same (request, donor, 'sms') -> UNIQUE violation -> returns -1, no dup row.
    again = notifications.save_notification(request_id, donor_id, "delivered")
    assert again == -1

    assert notifications.donor_already_notified(request_id, donor_id) is True


# ---- events ---------------------------------------------------------------


def test_events_added_and_read_back(db):
    request_id, _ = _add_request()
    events.add_request_event(request_id, "request_created", actor_type="requester")
    events.add_request_event(request_id, "sms_sent", actor_type="system")

    rows = events.get_request_events(request_id)
    assert [r["event_type"] for r in rows] == ["request_created", "sms_sent"]


# ---- matching -------------------------------------------------------------


def test_haversine_self_distance_zero(db):
    assert matching.haversine_distance(26.85, 80.95, 26.85, 80.95) == 0


def test_rank_puts_nearest_and_never_donated_first(db):
    near = _add_donor(phone="9000000040", latitude=26.8505, longitude=80.9505)   # ~0 km
    far = _add_donor(phone="9000000041", latitude=26.9000, longitude=81.0000)    # far

    request_id, _ = _add_request()  # lat 26.8500, lon 80.9500
    row = requests.get_request_by_id(request_id)

    candidates = donors.get_candidate_donors("O+")
    ranked = matching.score_and_rank_donors(candidates, row["latitude"], row["longitude"])

    assert ranked[0]["rank"] == 1
    assert ranked[0]["donor"]["id"] == near
    assert ranked[0]["distance_km"] <= ranked[-1]["distance_km"]


# ---- admin ----------------------------------------------------------------

def test_admin_stats(db):
    _add_donor(phone="9000000050")
    _add_donor(phone="9000000051", available=False)
    _, _ = _add_request()  # open

    stats = admin.get_admin_stats()
    assert stats["total_donors"] == 2
    assert stats["available_donors"] == 1
    assert stats["open_requests"] == 1
    assert stats["fulfilled_requests"] == 0
