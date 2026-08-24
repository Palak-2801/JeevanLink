-- =========================================================
-- JEEVANLINK DATABASE SCHEMA
-- =========================================================

-- Enable foreign-key enforcement (SQLite has it off by default).

PRAGMA foreign_keys = ON;


-- =========================================================
-- 1. DONORS TABLE
-- =========================================================

-- Stores every registered blood donor.

CREATE TABLE IF NOT EXISTS donors (

    -- Unique identifier for the donor.
    id INTEGER PRIMARY KEY AUTOINCREMENT,


    -- Donor's full name.
    name TEXT NOT NULL,


    -- Contact number. UNIQUE prevents the same number from being
    -- registered twice.
    phone TEXT NOT NULL UNIQUE,


    -- Donor's email address (optional)
    email TEXT,


    -- Donor's city or area
    city TEXT,


    -- Donor's age in years.
    age INTEGER NOT NULL,


    -- One of: A+, A-, B+, B-, AB+, AB-, O+, O-
    blood_group TEXT NOT NULL,


    -- Date of the donor's most recent donation.
    -- NULL if they have never donated.
    last_donation_date TEXT,


    -- Reserved for a future eligibility calculation.
    next_eligible_date TEXT,


    -- Availability option chosen on the registration form
    -- available | urgent-only | unavailable
    availability TEXT NOT NULL DEFAULT 'available',


    -- Whether the donor is currently accepting alerts.
    -- 1 = available, 0 = unavailable
    available INTEGER NOT NULL DEFAULT 1,


    -- Only alert this donor for critical/urgent requests
    -- 1 = Yes, 0 = No
    urgent_only INTEGER NOT NULL DEFAULT 0,


    -- Whether an administrator has verified this profile.
    -- 1 = verified, 0 = not verified
    verified INTEGER NOT NULL DEFAULT 0,


    -- Whether the donor consented to receive alerts.
    -- 1 = consent given, 0 = no consent
    sms_consent INTEGER NOT NULL DEFAULT 0,


    -- Donor's latitude, used for distance matching.
    latitude REAL,


    -- Donor's longitude, used for distance matching.
    longitude REAL,


    -- When the donor registered.
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 2. BLOOD REQUESTS TABLE
-- =========================================================

-- Stores blood requests raised by patients or their relatives.

CREATE TABLE IF NOT EXISTS blood_requests (

    -- Unique identifier for the request.
    id INTEGER PRIMARY KEY AUTOINCREMENT,


    -- Unguessable token used in public URLs, for example
    --     /respond/abcd1234-secure-token
    -- Sequential ids would let anyone enumerate other requests.
    public_token TEXT NOT NULL UNIQUE,


    -- Name of the person raising the request.
    requester_name TEXT NOT NULL,


    -- Contact number of the requester.
    requester_phone TEXT NOT NULL,


    -- Blood group needed.
    blood_group TEXT NOT NULL,


    -- Component needed: whole_blood, platelets, plasma, rbc.
    blood_component TEXT,


    -- Number of units needed.
    units INTEGER NOT NULL DEFAULT 1,


    -- Hospital name.
    hospital TEXT NOT NULL,


    -- How urgent the request is: critical, urgent or normal.
    urgency TEXT NOT NULL,


    -- Hospital latitude.
    latitude REAL NOT NULL,


    -- Hospital longitude.
    longitude REAL NOT NULL,


    -- Lifecycle status:
    -- open, alerted, accepted, fulfilled, cancelled, expired
    status TEXT NOT NULL DEFAULT 'open',


    -- The donor who accepted. NULL until someone accepts.
    accepted_donor_id INTEGER,


    -- When the request was created.
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- When the request should stop accepting responses.
    expires_at TEXT,


    -- Link to the donors table.
    FOREIGN KEY (accepted_donor_id)
        REFERENCES donors(id)
        ON DELETE SET NULL
);


-- =========================================================
-- 3. NOTIFICATIONS TABLE
-- =========================================================

-- Records every alert sent to a donor.

CREATE TABLE IF NOT EXISTS notifications (

    -- Unique identifier for the notification.
    id INTEGER PRIMARY KEY AUTOINCREMENT,


    -- The request this alert belongs to.
    request_id INTEGER NOT NULL,


    -- The donor who was alerted.
    donor_id INTEGER NOT NULL,


    -- Delivery channel: sms, whatsapp, in_app or email.
    channel TEXT NOT NULL DEFAULT 'sms',


    -- Delivery status: pending, sent, delivered or failed.
    delivery_status TEXT NOT NULL DEFAULT 'pending',


    -- Message id returned by the delivery provider.
    provider_message_id TEXT,


    -- When the alert was sent.
    sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- Link to the blood_requests table.
    FOREIGN KEY (request_id)
        REFERENCES blood_requests(id)
        ON DELETE CASCADE,


    -- Link to the donors table.
    FOREIGN KEY (donor_id)
        REFERENCES donors(id)
        ON DELETE CASCADE,


    -- Prevents alerting the same donor twice for the same request
    -- on the same channel.
    UNIQUE (
        request_id,
        donor_id,
        channel
    )
);


-- =========================================================
-- 4. REQUEST EVENTS TABLE
-- =========================================================

-- Append-only audit log of everything that happens to a request.

CREATE TABLE IF NOT EXISTS request_events (

    -- Unique identifier for the event.
    id INTEGER PRIMARY KEY AUTOINCREMENT,


    -- The request this event belongs to.
    request_id INTEGER NOT NULL,


    -- One of:
    --   request_created
    --   donors_matched
    --   sms_sent
    --   donor_accepted
    --   donor_declined
    --   request_fulfilled
    --   request_cancelled
    event_type TEXT NOT NULL,


    -- Who performed the action: requester, donor, admin or system.
    actor_type TEXT,


    -- Optional identifier of the actor.
    actor_id INTEGER,


    -- When the event occurred.
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,


    -- Link to the blood_requests table.
    FOREIGN KEY (request_id)
        REFERENCES blood_requests(id)
        ON DELETE CASCADE
);


-- =========================================================
-- 5. DATABASE INDEXES
-- =========================================================

-- Indexes keep the lookups below fast as the tables grow.


-- Donor lookup by blood group.

CREATE INDEX IF NOT EXISTS idx_donors_blood_group
ON donors (
    blood_group
);


-- Donor lookup by availability.

CREATE INDEX IF NOT EXISTS idx_donors_available
ON donors (
    available
);


-- Donor lookup by alert consent.

CREATE INDEX IF NOT EXISTS idx_donors_sms_consent
ON donors (
    sms_consent
);


-- Composite index used by the matching query.

CREATE INDEX IF NOT EXISTS idx_donors_matching
ON donors (
    blood_group,
    available,
    sms_consent
);


-- Request lookup by status.

CREATE INDEX IF NOT EXISTS idx_requests_status
ON blood_requests (
    status
);


-- Request lookup by urgency.

CREATE INDEX IF NOT EXISTS idx_requests_urgency
ON blood_requests (
    urgency
);


-- Notification lookup by request.

CREATE INDEX IF NOT EXISTS idx_notifications_request
ON notifications (
    request_id
);


-- Notification lookup by donor.

CREATE INDEX IF NOT EXISTS idx_notifications_donor
ON notifications (
    donor_id
);


-- Event lookup by request.

CREATE INDEX IF NOT EXISTS idx_request_events_request
ON request_events (
    request_id
);


-- =========================================================
-- END OF JEEVANLINK DATABASE SCHEMA
-- =========================================================
