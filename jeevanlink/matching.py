"""Candidate ranking for a blood request.

SQL (``donors.get_candidate_donors``) only filters candidates. This module
turns that list into an ordered, preference-ranked result using distance and
recent-donation recency.

We use the Haversine formula to get great-circle distance in kilometres.
"""

import math
import sqlite3
from datetime import date
from typing import Dict, List, Sequence

# Mean radius of Earth in km.
EARTH_RADIUS_KM = 6371.0

# Relative weight of distance vs. recency. Tune for the product.
DISTANCE_WEIGHT = 0.7
RECENCY_WEIGHT = 0.3

# A donor who last donated this many days ago is "over the allowed gap" and
# gets the best recency score. 90 days is a common post-donation gap.
IDEAL_GAP_DAYS = 90


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _recency_score(last_donation: str | None, today: date | None = None) -> float:
    """Return a 0..1 score; higher = more eligible (longer since donating)."""
    today = today or date.today()
    last = _parse_date(last_donation)
    if last is None:
        # Never donated -> fully eligible.
        return 1.0
    gap_days = (today - last).days
    # Clamp so a very fresh donor isn't negative and an old donor caps at 1.
    return max(0.0, min(1.0, gap_days / IDEAL_GAP_DAYS))


def score_and_rank_donors(
    donors: Sequence[sqlite3.Row],
    request_lat: float,
    request_lon: float,
    today: date | None = None,
) -> List[Dict]:
    """Rank donors for a request.

    Each result is a dict with the donor fields plus:
        - ``distance_km``
        - ``distance_score`` (0..1, nearer = higher)
        - ``recency_score`` (0..1, longer since last donation = higher)
        - ``score``       (weighted blend, higher = better candidate)
        - ``rank``        (1 = best match)

    Default ordering is descending ``score`` so the first entry is the
    strongest candidate.
    """
    today = today or date.today()
    ranks: List[Dict] = []

    for donor in donors:
        lat = donor["latitude"]
        lon = donor["longitude"]
        if lat is None or lon is None:
            continue

        distance_km = haversine_distance(request_lat, request_lon, lat, lon)

        # Nearest donor -> score 1.0. Scale against a 25 km "max useful" radius.
        distance_score = max(0.0, 1.0 - distance_km / 25.0)

        recency_score = _recency_score(donor["last_donation_date"], today)

        score = DISTANCE_WEIGHT * distance_score + RECENCY_WEIGHT * recency_score

        ranks.append(
            {
                "donor": dict(donor),
                "distance_km": round(distance_km, 2),
                "distance_score": round(distance_score, 3),
                "recency_score": round(recency_score, 3),
                "score": round(score, 4),
            }
        )

    ranks.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(ranks, start=1):
        r["rank"] = i
    return ranks
