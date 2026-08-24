from flask import Blueprint
from flask import jsonify
from flask import request

from .database import IntegrityError
from .database import get_db_connection


donors_blueprint = Blueprint(
    "donors",
    __name__
)


VALID_BLOOD_GROUPS = [
    "A+",
    "A-",
    "B+",
    "B-",
    "AB+",
    "AB-",
    "O+",
    "O-"
]


VALID_AVAILABILITY = [
    "available",
    "urgent-only",
    "unavailable"
]


# ===================================================
# REGISTER DONOR
# ===================================================

@donors_blueprint.route(
    "/api/donors",
    methods=["POST"]
)
def register_donor():

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message": "No donor data received"
        }), 400


    name = str(
        data.get("name", "")
    ).strip()


    phone = str(
        data.get("phone", "")
    ).strip()


    email = str(
        data.get("email", "")
    ).strip()


    blood_group = str(
        data.get("bloodGroup", "")
    ).strip()


    availability = str(
        data.get("availability", "")
    ).strip()


    city = str(
        data.get("city", "")
    ).strip()


    last_donation_date = data.get(
        "lastDonationDate"
    )


    sms_consent = bool(
        data.get("smsConsent", False)
    )


    available = bool(
        data.get(
            "available",
            availability != "unavailable"
        )
    )


    urgent_only = bool(
        data.get(
            "urgentOnly",
            availability == "urgent-only"
        )
    )


    try:

        age = int(
            data.get("age")
        )

        latitude = float(
            data.get("latitude")
        )

        longitude = float(
            data.get("longitude")
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message":
                "Invalid age or location"
        }), 400


    # Validation

    if len(name) < 3:

        return jsonify({
            "success": False,
            "message":
                "Enter your complete name"
        }), 400


    if (
        len(phone) != 10
        or not phone.isdigit()
    ):

        return jsonify({
            "success": False,
            "message":
                "Enter a valid 10-digit phone number"
        }), 400


    if age < 18 or age > 65:

        return jsonify({
            "success": False,
            "message":
                "Age must be between 18 and 65"
        }), 400


    if blood_group not in VALID_BLOOD_GROUPS:

        return jsonify({
            "success": False,
            "message": "Invalid blood group"
        }), 400


    if availability not in VALID_AVAILABILITY:

        return jsonify({
            "success": False,
            "message":
                "Please select availability"
        }), 400


    if len(city) < 3:

        return jsonify({
            "success": False,
            "message":
                "Please enter city or area"
        }), 400


    connection = get_db_connection()


    try:

        cursor = connection.execute(
            """
            INSERT INTO donors (
                name,
                phone,
                email,
                age,
                blood_group,
                last_donation_date,
                availability,
                available,
                urgent_only,
                city,
                sms_consent,
                latitude,
                longitude,
                verified
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, 0
            )
            """,
            (
                name,
                phone,
                email or None,
                age,
                blood_group,
                last_donation_date or None,
                availability,
                1 if available else 0,
                1 if urgent_only else 0,
                city,
                1 if sms_consent else 0,
                latitude,
                longitude
            )
        )


        donor_id = cursor.lastrowid


        connection.commit()


        return jsonify({
            "success": True,

            "message":
                "Donor registered successfully",

            "donorId":
                f"JL-{donor_id:06d}"
        }), 201


    except IntegrityError as error:

        connection.rollback()


        if "phone" in str(error).lower():

            return jsonify({
                "success": False,

                "message":
                    "This phone number is already registered"
            }), 409


        return jsonify({
            "success": False,

            "message":
                "Database integrity error"
        }), 409


    except Exception as error:

        connection.rollback()

        print(
            "Donor registration error:",
            error
        )


        return jsonify({
            "success": False,

            "message":
                "Internal server error"
        }), 500


    finally:

        connection.close()


# ===================================================
# GET DONORS FOR TESTING
# ===================================================

@donors_blueprint.route(
    "/api/donors",
    methods=["GET"]
)
def get_donors():

    connection = get_db_connection()


    donors = connection.execute(
        """
        SELECT
            id,
            name,
            age,
            blood_group,
            availability,
            city,
            verified,
            created_at

        FROM donors

        ORDER BY id DESC
        """
    ).fetchall()


    connection.close()


    donor_list = []


    for donor in donors:

        donor_list.append({
            "id": donor["id"],

            "name": donor["name"],

            "age": donor["age"],

            "bloodGroup":
                donor["blood_group"],

            "availability":
                donor["availability"],

            "city": donor["city"],

            "verified":
                bool(donor["verified"]),

            "createdAt":
                donor["created_at"]
        })


    return jsonify({
        "success": True,
        "count": len(donor_list),
        "donors": donor_list
    }), 200


# ===================================================
# CANDIDATE DONORS (called by matching.py)
# ===================================================

def get_candidate_donors(blood_group, urgency="normal"):
    """Return donors eligible to be alerted for a request.

    Filters applied:
      - matching blood group
      - available = 1
      - sms_consent = 1
      - donors who opted into "urgent-only" are included only for
        critical/urgent requests
      - latitude/longitude must be present (needed for distance)

    This only FILTERS. Ranking is done by
    ``matching.score_and_rank_donors``.
    """
    connection = get_db_connection()

    try:
        query = """
            SELECT *
            FROM donors
            WHERE blood_group = ?
              AND available = 1
              AND sms_consent = 1
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
        """

        params = [blood_group]

        if urgency not in ("critical", "urgent"):
            query += " AND urgent_only = 0"

        return connection.execute(query, params).fetchall()

    finally:
        connection.close()


def get_donor_by_id(donor_id):
    connection = get_db_connection()

    try:
        return connection.execute(
            "SELECT * FROM donors WHERE id = ?",
            (donor_id,)
        ).fetchone()

    finally:
        connection.close()


# ===================================================
# REPOSITORY HELPERS (used by tests and internal callers)
# ===================================================

def create_donor(data):
    """Insert a donor from a dict and return the new id.

    The API layer (``register_donor``) handles the camelCase keys
    that arrive in the HTTP request. This function takes snake_case
    column names directly, which keeps tests and seed scripts simple.
    """
    availability = data.get("availability")

    if availability is None:
        if not data.get("available", True):
            availability = "unavailable"
        elif data.get("urgent_only"):
            availability = "urgent-only"
        else:
            availability = "available"

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO donors (
                name,
                phone,
                email,
                city,
                age,
                blood_group,
                last_donation_date,
                availability,
                available,
                urgent_only,
                sms_consent,
                latitude,
                longitude,
                verified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["phone"],
                data.get("email"),
                data.get("city"),
                data["age"],
                data["blood_group"],
                data.get("last_donation_date"),
                availability,
                1 if data.get("available", True) else 0,
                1 if data.get("urgent_only", False) else 0,
                1 if data.get("sms_consent", False) else 0,
                data.get("latitude"),
                data.get("longitude"),
                1 if data.get("verified", False) else 0,
            ),
        )

        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


def update_donor_availability(donor_id, available):
    """Toggle a donor's availability.

    The ``availability`` text column is kept in sync with the
    ``available`` flag so the two can never disagree.
    """
    connection = get_db_connection()

    try:
        connection.execute(
            """
            UPDATE donors
            SET available = ?,
                availability = ?
            WHERE id = ?
            """,
            (
                1 if available else 0,
                "available" if available else "unavailable",
                donor_id,
            ),
        )
        connection.commit()

    finally:
        connection.close()


def update_donor_location(donor_id, latitude, longitude):
    connection = get_db_connection()

    try:
        connection.execute(
            """
            UPDATE donors
            SET latitude = ?,
                longitude = ?
            WHERE id = ?
            """,
            (latitude, longitude, donor_id),
        )
        connection.commit()

    finally:
        connection.close()
