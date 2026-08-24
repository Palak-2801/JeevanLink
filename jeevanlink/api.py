"""JeevanLink REST API — requests, matching, notifications, admin.

This module is the missing link that wires the repository modules
together:

    requests.py      -> create / accept / update a blood request
    donors.py        -> find eligible donors
    matching.py      -> rank those donors
    notifications.py -> record SMS alerts, prevent duplicates
    events.py        -> audit trail
    admin.py         -> dashboard counters

All of these modules existed already, but no Flask route ever called
them, so the code never ran.
"""

import math
import os

from flask import Blueprint
from flask import jsonify
from flask import request

from . import admin
from . import alerts
from . import donors as donors_repo
from . import events
from . import matching
from . import notifications
from . import requests as requests_repo


api_blueprint = Blueprint("api", __name__)


VALID_BLOOD_GROUPS = [
    "A+", "A-", "B+", "B-",
    "AB+", "AB-", "O+", "O-"
]

VALID_URGENCY = ["critical", "urgent", "normal"]


# Blood compatibility chart.
# Key = the group the patient needs.
# Value = groups that are allowed to donate to them.
COMPATIBLE_DONORS = {
    "O-":  ["O-"],
    "O+":  ["O-", "O+"],
    "A-":  ["O-", "A-"],
    "A+":  ["O-", "O+", "A-", "A+"],
    "B-":  ["O-", "B-"],
    "B+":  ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": VALID_BLOOD_GROUPS,
}


def _error(message, code=400):
    return jsonify({
        "success": False,
        "message": message
    }), code


def _collect_candidates(blood_group, urgency):
    """Return de-duplicated donors compatible with ``blood_group``."""
    candidates = []
    seen_ids = set()

    for group in COMPATIBLE_DONORS.get(blood_group, [blood_group]):
        for donor in donors_repo.get_candidate_donors(group, urgency):
            if donor["id"] not in seen_ids:
                seen_ids.add(donor["id"])
                candidates.append(donor)

    return candidates


# ===================================================
# CREATE BLOOD REQUEST  ->  MATCH  ->  NOTIFY
# ===================================================

@api_blueprint.route("/api/requests", methods=["POST"])
def create_request():
    data = request.get_json(silent=True)

    if not data:
        return _error("No request data received")

    requester_name = str(data.get("requesterName", "")).strip()
    requester_phone = str(data.get("requesterPhone", "")).strip()
    blood_group = str(data.get("bloodGroup", "")).strip()
    hospital = str(data.get("hospital", "")).strip()
    urgency = str(data.get("urgency", "normal")).strip().lower()

    try:
        latitude = float(data.get("latitude"))
        longitude = float(data.get("longitude"))
        units = int(data.get("units", 1))
    except (TypeError, ValueError):
        return _error("Invalid location or units")

    if len(requester_name) < 3:
        return _error("Enter the requester's full name")

    if len(requester_phone) != 10 or not requester_phone.isdigit():
        return _error("Enter a valid 10-digit phone number")

    if blood_group not in VALID_BLOOD_GROUPS:
        return _error("Invalid blood group")

    if len(hospital) < 3:
        return _error("Enter the hospital name")

    if urgency not in VALID_URGENCY:
        return _error("Urgency must be critical, urgent or normal")

    if units < 1 or units > 10:
        return _error("Units must be between 1 and 10")

    # 1. Persist the request.
    request_id, public_token = requests_repo.create_blood_request({
        "requester_name": requester_name,
        "requester_phone": requester_phone,
        "blood_group": blood_group,
        "blood_component": data.get("bloodComponent", "whole_blood"),
        "units": units,
        "hospital": hospital,
        "urgency": urgency,
        "latitude": latitude,
        "longitude": longitude,
        "expires_at": data.get("expiresAt"),
    })

    events.add_request_event(
        request_id,
        "request_created",
        actor_type="requester"
    )

    # 2. Find compatible donors (not just the exact same group).
    candidates = _collect_candidates(blood_group, urgency)

    # 3. Rank them by distance and donation recency.
    ranked = matching.score_and_rank_donors(
        candidates,
        latitude,
        longitude
    )

    if ranked:
        events.add_request_event(
            request_id,
            "donors_matched",
            actor_type="system"
        )

    # 4. Alert the top three. The UNIQUE constraint on the
    #    notifications table blocks duplicates on its own, but the
    #    explicit check avoids sending a second SMS.
    notified = []

    for entry in ranked[:3]:
        donor = entry["donor"]

        if notifications.donor_already_notified(request_id, donor["id"]):
            continue

        results = alerts.send_donor_alert(
            donor["phone"],
            donor["name"],
            hospital,
            entry["distance_km"],
            blood_group,
            units,
            urgency,
            public_token,
            donor_id=donor["id"],
            email=donor["email"] if "email" in donor.keys() else None,
        )

        # One row per channel, so the audit shows exactly what was tried.
        for channel, delivered, provider_id in results:
            notifications.save_notification(
                request_id,
                donor["id"],
                "sent" if delivered else "failed",
                provider_message_id=provider_id,
                channel=channel,
            )

        notified.append({
            "donorId": donor["id"],
            "name": donor["name"],
            "bloodGroup": donor["blood_group"],
            "distanceKm": entry["distance_km"],
            "score": entry["score"],
            "rank": entry["rank"],
            "channels": [c for c, ok, _ in results if ok],
        })

    if notified:
        events.add_request_event(
            request_id,
            "sms_sent",
            actor_type="system"
        )
        requests_repo.update_request_status(
            request_id,
            requests_repo.ALERTED
        )

    return jsonify({
        "success": True,
        "message": "Blood request created",
        "requestId": request_id,
        "publicToken": public_token,
        "responseUrl": f"/respond/{public_token}",
        "matchesFound": len(ranked),
        "notifiedDonors": notified,
        "alertChannels": alerts.active_channels(),
    }), 201


# ===================================================
# ALERT DELIVERY (see alerts.py)
# ===================================================

def send_sms_alert(phone, hospital, distance_km, public_token,
                   donor_name="donor", blood_group="", units=1,
                   urgency="critical", email=None):
    """Kept for backwards compatibility; delegates to alerts.py."""
    results = alerts.send_donor_alert(
        phone, donor_name, hospital, distance_km,
        blood_group, units, urgency, public_token, email=email
    )
    return any(delivered for _, delivered, _ in results)


# ===================================================
# LIST OPEN REQUESTS
# ===================================================

@api_blueprint.route("/api/requests", methods=["GET"])
def list_requests():
    rows = requests_repo.list_open_requests()

    return jsonify({
        "success": True,
        "count": len(rows),
        "requests": [dict(row) for row in rows],
    }), 200


# ===================================================
# REQUEST STATUS BY PUBLIC TOKEN
# ===================================================

@api_blueprint.route("/api/requests/<token>", methods=["GET"])
def get_request(token):
    row = requests_repo.get_request_with_donor(token)

    if row is None:
        return _error("Request not found", 404)

    data = dict(row)

    # Privacy: donor identity is hidden until the request is accepted.
    if data.get("status") != "accepted":
        data["donor_name"] = None
        data["donor_phone"] = None
        data["donor_latitude"] = None
        data["donor_longitude"] = None

    return jsonify({
        "success": True,
        "request": data
    }), 200


# ===================================================
# DONOR ACCEPTS (race-safe: only the first donor wins)
# ===================================================

@api_blueprint.route("/api/requests/<token>/accept", methods=["POST"])
def accept_request(token):
    data = request.get_json(silent=True) or {}

    try:
        donor_id = int(data.get("donorId"))
    except (TypeError, ValueError):
        return _error("donorId is required")

    blood_request = requests_repo.get_request_by_token(token)

    if blood_request is None:
        return _error("Request not found", 404)

    if donors_repo.get_donor_by_id(donor_id) is None:
        return _error("Donor not found", 404)

    accepted = requests_repo.accept_request(token, donor_id)

    if not accepted:
        return _error(
            "This request has already been accepted or closed",
            409
        )

    events.add_request_event(
        blood_request["id"],
        "donor_accepted",
        actor_type="donor",
        actor_id=donor_id
    )

    return jsonify({
        "success": True,
        "message": "Request accepted. Route unlocked.",
        "routeUrl": f"/api/requests/{token}/route",
    }), 200


# ===================================================
# DONOR DECLINES
# ===================================================

@api_blueprint.route("/api/requests/<token>/decline", methods=["POST"])
def decline_request(token):
    data = request.get_json(silent=True) or {}

    blood_request = requests_repo.get_request_by_token(token)

    if blood_request is None:
        return _error("Request not found", 404)

    donor_id = data.get("donorId")

    events.add_request_event(
        blood_request["id"],
        "donor_declined",
        actor_type="donor",
        actor_id=int(donor_id) if donor_id else None
    )

    return jsonify({
        "success": True,
        "message": "Thank you for responding. We are contacting the next donor."
    }), 200


# ===================================================
# ROUTE AND ETA (privacy gate: only after acceptance)
# ===================================================

@api_blueprint.route("/api/requests/<token>/route", methods=["GET"])
def get_route(token):
    row = requests_repo.get_request_with_donor(token)

    if row is None:
        return _error("Request not found", 404)

    if row["status"] != "accepted" or row["donor_latitude"] is None:
        return _error(
            "Access denied: the route and contact details are released "
            "only after a donor accepts",
            403
        )

    blood_request = requests_repo.get_request_by_token(token)

    distance_km = matching.haversine_distance(
        row["donor_latitude"],
        row["donor_longitude"],
        blood_request["latitude"],
        blood_request["longitude"],
    )

    # Assumes an average city speed of 18 km/h.
    eta_minutes = max(1, math.ceil((distance_km / 18.0) * 60))

    maps_url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={row['donor_latitude']},{row['donor_longitude']}"
        f"&destination={blood_request['latitude']},{blood_request['longitude']}"
        "&travelmode=driving"
    )

    return jsonify({
        "success": True,
        "routing": {
            "donorName": row["donor_name"],
            "donorPhone": row["donor_phone"],
            "hospital": row["hospital"],
            "distanceKm": round(distance_km, 2),
            "etaMinutes": eta_minutes,
            "googleMapsUrl": maps_url,
        }
    }), 200


# ===================================================
# FULFILL AND CLOSE
# ===================================================

@api_blueprint.route("/api/requests/<token>/fulfill", methods=["POST"])
def fulfill_request(token):
    blood_request = requests_repo.get_request_by_token(token)

    if blood_request is None:
        return _error("Request not found", 404)

    requests_repo.update_request_status(
        blood_request["id"],
        requests_repo.FULFILLED
    )

    events.add_request_event(
        blood_request["id"],
        "request_fulfilled",
        actor_type="requester"
    )

    return jsonify({
        "success": True,
        "message": "Request fulfilled. The loop is closed."
    }), 200


# ===================================================
# MATCH PREVIEW (ranking without notifying anyone)
# ===================================================

@api_blueprint.route("/api/requests/<token>/matches", methods=["GET"])
def get_matches(token):
    blood_request = requests_repo.get_request_by_token(token)

    if blood_request is None:
        return _error("Request not found", 404)

    candidates = _collect_candidates(
        blood_request["blood_group"],
        blood_request["urgency"]
    )

    ranked = matching.score_and_rank_donors(
        candidates,
        blood_request["latitude"],
        blood_request["longitude"],
    )

    # Privacy: phone numbers are never included in the ranking.
    safe = []

    for entry in ranked:
        safe.append({
            "rank": entry["rank"],
            "donorId": entry["donor"]["id"],
            "name": entry["donor"]["name"],
            "bloodGroup": entry["donor"]["blood_group"],
            "verified": bool(entry["donor"]["verified"]),
            "distanceKm": entry["distance_km"],
            "score": entry["score"],
        })

    return jsonify({
        "success": True,
        "count": len(safe),
        "matches": safe,
    }), 200


# ===================================================
# ADMIN DASHBOARD
# ===================================================

@api_blueprint.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    return jsonify({
        "success": True,
        "stats": admin.get_admin_stats(),
    }), 200


@api_blueprint.route("/api/admin/events", methods=["GET"])
def admin_events():
    limit = request.args.get("limit", 20, type=int)
    rows = admin.get_recent_events(limit)

    return jsonify({
        "success": True,
        "count": len(rows),
        "events": [dict(row) for row in rows],
    }), 200
