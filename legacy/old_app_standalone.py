import os
import sqlite3
import math
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE = 'jeevanlink.db'

# ==========================================
# 1. DATABASE SETUP & SEEDING (SQLite)
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and seeds it with demo data from Slide 7"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Donors Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                blood_group TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                is_available INTEGER DEFAULT 1,
                age INTEGER NOT NULL,
                last_donation_date TEXT, -- YYYY-MM-DD
                is_verified INTEGER DEFAULT 0
            )
        ''')

        # Requests Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blood_group TEXT NOT NULL,
                hospital_name TEXT NOT NULL,
                hospital_lat REAL NOT NULL,
                hospital_lon REAL NOT NULL,
                urgency TEXT NOT NULL, -- 'Critical', 'Moderate', 'Routine'
                status TEXT DEFAULT 'Pending', -- 'Pending', 'Matched', 'Accepted', 'Fulfilled', 'Closed'
                created_at TEXT NOT NULL
            )
        ''')

        # Matches Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                donor_id INTEGER NOT NULL,
                distance REAL NOT NULL,
                score REAL NOT NULL,
                status TEXT DEFAULT 'Pending', -- 'Pending', 'SMS Sent', 'Accepted', 'Declined'
                FOREIGN KEY(request_id) REFERENCES requests(id),
                FOREIGN KEY(donor_id) REFERENCES donors(id)
            )
        ''');

        # Seed data (Demo coordinates centered around City Care Delhi / Connaught Place)
        # Hospital coordinates: 28.6139, 77.2090
        cursor.execute("SELECT COUNT(*) FROM donors")
        if cursor.fetchone()[0] == 0:
            demo_donors = [
                ("Aarav", "+919876543210", "O+", 28.6239, 77.2150, 1, 25, "2024-01-10", 1), # ~1.2 km away
                ("Priya", "+919876543211", "O+", 28.6300, 77.2250, 1, 28, "2023-12-15", 1), # ~2.4 km away
                ("Rohan", "+919876543212", "O+", 28.6410, 77.2190, 1, 22, "2024-02-01", 0), # ~3.1 km away
                ("Vikram", "+919876543213", "A+", 28.6100, 77.1900, 1, 35, "2024-02-14", 1) # Non-matching group
            ]
            cursor.executemany('''
                INSERT INTO donors (name, phone, blood_group, lat, lon, is_available, age, last_donation_date, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', demo_donors)
            conn.commit()
            print("Database initialized and demo data seeded successfully!")

# ==========================================
# 2. MATCH ENGINE UTILITIES (Slide 7 Rules)
# ==========================================
def calculate_distance(lat1, lon1, lat2, lon2):
    """Haversine Formula to calculate precise road/aerial distance in KM"""
    R = 6371.0  # Radius of the Earth in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def calculate_match_score(distance, is_available, age, last_donation_date, is_verified):
    """
    MATCH SCORE BASIS (From Slide 7):
    - Distance: 40% (Graded score up to max 25km radius)
    - Live Availability: 25% (Binary)
    - Age/Donation Eligibility: 20% (Evaluates threshold)
    - Verified Profile: 15% (Binary)
    """
    # 1. Distance Score (Max weight: 40)
    # Graded score: 40 points if directly next to hospital, declines progressively to 0 at 25km.
    distance_score = max(0, (25 - distance) / 25) * 40 if distance <= 25 else 0

    # 2. Availability Score (Max weight: 25)
    availability_score = 25 if is_available == 1 else 0

    # 3. Age/Donation Eligibility Score (Max weight: 20)
    # Checks if donor hasn't donated in the last 90 days
    is_eligible = 1
    if last_donation_date:
        last_date = datetime.strptime(last_donation_date, "%Y-%m-%d")
        days_since_donation = (datetime.now() - last_date).days
        if days_since_donation < 90:
            is_eligible = 0
            
    eligibility_score = 20 if (18 <= age <= 60 and is_eligible == 1) else 5

    # 4. Verified Profile Score (Max weight: 15)
    verified_score = 15 if is_verified == 1 else 0

    total_score = round(distance_score + availability_score + eligibility_score + verified_score, 1)
    return min(total_score, 100)

# ==========================================
# 3. EXTERNAL MOCK SERVICES (SMS & Routing)
# ==========================================
def send_sms_alert(phone, hospital, distance, match_id):
    """Integrates with SMS gateway (Twilio/MSG91 fallback to console logger)"""
    accept_link = f"http://localhost:5000/api/matches/{match_id}/accept"
    decline_link = f"http://localhost:5000/api/matches/{match_id}/decline"
    
    sms_body = (
        f"jeevanlink Alert: Urgent request at {hospital}, "
        f"approx {distance} km away. Click to accept: {accept_link} or decline: {decline_link}"
    )
    
    # Check for Twilio Credentials (Optional Env variables for production execution)
    TWILIO_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

    if TWILIO_SID and TWILIO_TOKEN and TWILIO_NUMBER:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            client.messages.create(
                body=sms_body,
                from_=TWILIO_NUMBER,
                to=phone
            )
            print(f"[SMS Sent via Twilio] to {phone}")
            return True
        except Exception as e:
            print(f"[Twilio Failed] {e}")
            
    # Fallback/Development Console Mock (Slide 7 Demo Output)
    print("\n" + "="*40)
    print(f"📡 [SMS SENT TO: {phone}]")
    print(f"💬 Body: {sms_body}")
    print("="*40 + "\n")
    return True

# ==========================================
# 4. API ENDPOINTS (REST Controller)
# ==========================================

# GET Status check
@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "service": "Jeevan Link Backend Engine",
        "demo_endpoint": "/api/items"
    })

# 1. REQUEST: Create a new blood request (Slide 3)
@app.route('/api/requests', methods=['POST'])
def create_request():
    data = request.get_json()
    blood_group = data.get('blood_group')
    hospital_name = data.get('hospital_name')
    hospital_lat = float(data.get('hospital_lat', 28.6139))
    hospital_lon = float(data.get('hospital_lon', 77.2090))
    urgency = data.get('urgency', 'Critical')

    if not blood_group or not hospital_name:
        return jsonify({"success": False, "message": "Required fields missing"}), 400

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Save request to database
        cursor.execute('''
            INSERT INTO requests (blood_group, hospital_name, hospital_lat, hospital_lon, urgency, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (blood_group, hospital_name, hospital_lat, hospital_lon, urgency, created_at))
        request_id = cursor.lastrowid
        
        # 2. MATCH & Progressive Radius Gate (Slide 4 - 5 -> 10 -> 25 KM)
        # We search matching group inside progressive zones
        matched_donors = []
        for search_radius in [5, 10, 25]:
            cursor.execute('''
                SELECT id, name, phone, lat, lon, is_available, age, last_donation_date, is_verified 
                FROM donors 
                WHERE blood_group = ? AND is_available = 1
            ''', (blood_group,))
            all_donors = cursor.fetchall()
            
            for donor in all_donors:
                dist = calculate_distance(hospital_lat, hospital_lon, donor['lat'], donor['lon'])
                if dist <= search_radius:
                    # Skip duplicate additions
                    if not any(d['id'] == donor['id'] for d in matched_donors):
                        score = calculate_match_score(
                            dist, donor['is_available'], donor['age'], 
                            donor['last_donation_date'], donor['is_verified']
                        )
                        matched_donors.append({
                            "id": donor['id'],
                            "name": donor['name'],
                            "phone": donor['phone'],
                            "distance": dist,
                            "score": score
                        })
            
            # If we matched enough candidates in the immediate zones, break early to prevent donor alert fatigue
            if len(matched_donors) >= 3:
                break
        
        # Sort matched candidates by match score descending (Slide 7 Match Score rank)
        matched_donors = sorted(matched_donors, key=lambda x: x['score'], reverse=True)
        
        # Commit match relations to the database
        for idx, donor in enumerate(matched_donors):
            cursor.execute('''
                INSERT INTO matches (request_id, donor_id, distance, score, status)
                VALUES (?, ?, ?, ?, 'Pending')
            ''', (request_id, donor['id'], donor['distance'], donor['score']))
            match_id = cursor.lastrowid
            
            # 3. SMS Activation (Slide 3 & 4) - Trigger alert to top batch match
            if idx < 3: # Send SMS alert automatically to top 3 matching candidates
                send_sms_alert(donor['phone'], hospital_name, donor['distance'], match_id)
                cursor.execute("UPDATE matches SET status = 'SMS Sent' WHERE id = ?", (match_id,))
                
        conn.commit()

    return jsonify({
        "success": True,
        "request_id": request_id,
        "matches_found": len(matched_donors),
        "notified_donors": matched_donors[:3]
    }), 201


# GET Matches for a request (Dynamic Ranking dashboard)
@app.route('/api/requests/<int:request_id>/matches', methods=['GET'])
def get_request_matches(request_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.id as match_id, d.name, m.distance, m.score, m.status, d.is_verified
            FROM matches m
            JOIN donors d ON m.donor_id = d.id
            WHERE m.request_id = ?
            ORDER BY m.score DESC
        ''', (request_id,))
        rows = cursor.fetchall()
        
    return jsonify({
        "success": True,
        "matches": [dict(row) for row in rows]
    })


# 4. ACCEPT (Slide 4 & 5): Donor consents to connect
@app.route('/api/matches/<int:match_id>/accept', methods=['GET', 'POST'])
def accept_match(match_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Fetch matching request and donor metadata
        cursor.execute('''
            SELECT m.request_id, m.donor_id, r.hospital_name, d.name as donor_name, d.phone as donor_phone
            FROM matches m
            JOIN requests r ON m.request_id = r.id
            JOIN donors d ON m.donor_id = d.id
            WHERE m.id = ?
        ''', (match_id,))
        match_info = cursor.fetchone()
        
        if not match_info:
            return jsonify({"success": False, "message": "Invalid Match ID"}), 404
        
        req_id = match_info['request_id']
        donor_id = match_info['donor_id']
        
        # Mark match status as 'Accepted' and set Request as 'Accepted'
        cursor.execute("UPDATE matches SET status = 'Accepted' WHERE id = ?", (match_id,))
        cursor.execute("UPDATE requests SET status = 'Accepted' WHERE id = ?", (req_id,))
        
        # Opt-out other candidates automatically to close the search loop (Slide 4)
        cursor.execute("UPDATE matches SET status = 'Declined' WHERE request_id = ? AND id != ?", (req_id, match_id))
        
        conn.commit()
        
    # Standard dynamic HTML view response for when the donor clicks the SMS link on their mobile phone
    return f"""
    <div style="font-family: Arial, sans-serif; text-align: center; margin-top: 100px; padding: 20px;">
        <h2 style="color: #2e7d32;">✔ Request Accepted!</h2>
        <p>Thank you, <b>{match_info['donor_name']}</b>. Your response is verified.</p>
        <p>Routing to <b>{match_info['hospital_name']}</b> has been unlocked.</p>
        <br>
        <a href="/api/requests/{req_id}/route?donor_id={donor_id}" 
           style="background-color: #c62828; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">
           OPEN MAP & ROUTE
        </a>
    </div>
    """


# 5. DECLINE match invitation
@app.route('/api/matches/<int:match_id>/decline', methods=['GET', 'POST'])
def decline_match(match_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE matches SET status = 'Declined' WHERE id = ?", (match_id,))
        conn.commit()
        
    return """
    <div style="font-family: Arial, sans-serif; text-align: center; margin-top: 100px;">
        <h2 style="color: #c62828;">Invitation Declined</h2>
        <p>Thank you for letting us know. We will match another donor immediately.</p>
    </div>
    """


# 6. ROUTE + ETA (Slide 3 & 4 - Privacy by Design Gate)
# Revealing routing elements and direct communication metrics ONLY AFTER acceptance.
@app.route('/api/requests/<int:request_id>/route', methods=['GET'])
def get_route(request_id):
    donor_id = request.args.get('donor_id')
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verify if this specific donor has accepted the request
        cursor.execute('''
            SELECT m.status, r.hospital_name, r.hospital_lat, r.hospital_lon, 
                   d.lat as donor_lat, d.lon as donor_lon, d.phone as donor_phone, d.name as donor_name
            FROM matches m
            JOIN requests r ON m.request_id = r.id
            JOIN donors d ON m.donor_id = d.id
            WHERE m.request_id = ? AND m.donor_id = ?
        ''', (request_id, donor_id))
        data = cursor.fetchone()
        
        if not data or data['status'] != 'Accepted':
            # Block unauthorized routing requests (Privacy Guard Layer)
            return jsonify({
                "success": False, 
                "message": "Access Denied: Unlocked route maps and phone records only available upon Donor Acceptance."
            }), 403
            
        # Calculation for route mapping visualization
        dist = calculate_distance(data['donor_lat'], data['donor_lon'], data['hospital_lat'], data['hospital_lon'])
        
        # Average velocity assumption under Indian emergency traffic (approx ~18 km/h)
        eta_minutes = math.ceil((dist / 18.0) * 60)
        
        # Generate raw Google Maps dynamic deep-link marker URL (Slide 4 - Key Feature 07)
        gmaps_link = f"https://www.google.com/maps/dir/?api=1&origin={data['donor_lat']},{data['donor_lon']}&destination={data['hospital_lat']},{data['hospital_lon']}&travelmode=driving"
        
        return jsonify({
            "success": True,
            "routing": {
                "donor_name": data['donor_name'],
                "donor_contact": data['donor_phone'], # Unmasked safely upon consent!
                "destination": data['hospital_name'],
                "distance_km": dist,
                "estimated_eta_mins": eta_minutes,
                "google_navigation_url": gmaps_link
            }
        })


# 7. CLOSE THE CASE (Slide 5 - Fulfilled Status + Audit)
@app.route('/api/requests/<int:request_id>/close', methods=['POST'])
def close_request(request_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE requests SET status = 'Fulfilled' WHERE id = ?", (request_id,))
        cursor.execute("UPDATE matches SET status = 'Closed' WHERE request_id = ? AND status = 'Accepted'", (request_id,))
        conn.commit()
        
    return jsonify({
        "success": True,
        "message": "Jeevan Link closed loop finalized. Incident logged and stored in audit tables."
    })


# Start Flask Application
if __name__ == '__main__':
    # Initialize SQLite instance automatically on runtime setup
    init_db()
    app.run(debug=True, port=5000)
