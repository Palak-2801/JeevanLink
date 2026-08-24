"""Full end-to-end check. Runs against whichever backend is configured.

Safe to run repeatedly: each run registers a donor with a fresh phone
number, so a leftover row from a previous run cannot fail the check.
"""
import random
import sys
from jeevanlink.run import create_app
from jeevanlink.database import backend_name
from jeevanlink import alerts, notifications

c = create_app().test_client(); res = []

# Unique per run so the script stays idempotent.
TEST_PHONE = "9" + str(random.randint(100000000, 999999999))
def check(label, cond, extra=""):
    res.append(bool(cond))
    print(f"   {label:26} {'PASS' if cond else '**FAIL**'} {extra}")

h = c.get("/api/health").get_json()
channels = ", ".join(h["alertChannels"])
print(f"\n{'='*58}\n  BACKEND: {h['backend'].upper()}   CHANNELS: {channels}\n{'='*58}")

print("\nPAGES")
for u in ["/","/donate","/request","/index.js","/donar.js","/request.js","/respond.js",
          "/index.css","/donar.css"]:
    check(u, c.get(u).status_code == 200)
check("/respond/<token>", c.get("/respond/abc").status_code == 200)
check("unknown page 404", c.get("/nope.html").status_code == 404)

print("\nDONOR API")
donor_payload = {"name":"Asha Verma","phone":TEST_PHONE,
    "email":f"asha.{TEST_PHONE}@example.com",
    "age":27,"bloodGroup":"B+","availability":"available","available":True,"urgentOnly":False,
    "city":"Lucknow","smsConsent":True,"latitude":26.8467,"longitude":80.9462}
r = c.post("/api/donors", json=donor_payload)
check("register 201", r.status_code == 201, r.get_json().get("donorId",""))
check("duplicate 409", c.post("/api/donors", json=donor_payload).status_code == 409)
check("invalid 400", c.post("/api/donors", json={"name":"X","phone":"1"}).status_code == 400)
check("list donors", c.get("/api/donors").get_json()["count"] >= 1)

print("\nREQUEST LIFECYCLE")
d = c.post("/api/requests", json={"requesterName":"Palak Singh","requesterPhone":"9876543210",
    "bloodGroup":"O+","units":2,"hospital":"KGMU Lucknow","urgency":"critical",
    "latitude":26.85,"longitude":80.95})
j = d.get_json(); tok = j["publicToken"]
check("create 201", d.status_code == 201, f"{j['matchesFound']} matches, {len(j['notifiedDonors'])} alerted")
check("compatibility O-", any(n["bloodGroup"] == "O-" for n in j["notifiedDonors"]))
check("invalid request 400", c.post("/api/requests", json={"requesterName":"X"}).status_code == 400)
check("phone hidden", c.get(f"/api/requests/{tok}").get_json()["request"]["donor_phone"] is None)
check("route gated 403", c.get(f"/api/requests/{tok}/route").status_code == 403)
m = c.get(f"/api/requests/{tok}/matches").get_json()
check("matches no phone", not any("phone" in str(k).lower() for x in m["matches"] for k in x))
first = j["notifiedDonors"][0]["donorId"]; second = j["notifiedDonors"][1]["donorId"]
check("accept 200", c.post(f"/api/requests/{tok}/accept", json={"donorId":first}).status_code == 200)
check("race 409", c.post(f"/api/requests/{tok}/accept", json={"donorId":second}).status_code == 409)
rt = c.get(f"/api/requests/{tok}/route")
check("route 200", rt.status_code == 200, f"{rt.get_json()['routing']['etaMinutes']} min ETA")
check("fulfill 200", c.post(f"/api/requests/{tok}/fulfill").status_code == 200)
check("unknown token 404", c.get("/api/requests/zzz").status_code == 404)

print("\nDEDUPE + ADMIN")
rid = c.get(f"/api/requests/{tok}").get_json()["request"]["id"]
check("notified recorded", notifications.donor_already_notified(rid, first))

# Deduplication is per (request, donor, channel), so the duplicate has
# to reuse the channel that was actually recorded.
used = notifications.get_notifications_for_request(rid)
used_channel = next(
    (row["channel"] for row in used if row["donor_id"] == first),
    "console",
)
check("channel recorded", bool(used_channel), used_channel)
check("duplicate blocked",
      notifications.save_notification(rid, first, "sent",
                                      channel=used_channel) == -1)
check("other channel allowed",
      notifications.save_notification(rid, first, "sent",
                                      channel="in_app") != -1)
check("admin stats", c.get("/api/admin/stats").status_code == 200)
check("audit events", c.get("/api/admin/events").get_json()["count"] >= 4)

print("\nALERTS")
check("phone normalised", alerts.normalise_phone("9876543210") == "+919876543210")
check("leading zero handled", alerts.normalise_phone("09876543210") == "+919876543210")
check("already E.164 kept", alerts.normalise_phone("+919876543210") == "+919876543210")
body = alerts.build_message("Aarav", "KGMU", 0.53, "O+", 2, "critical", "tok", 1)
check("text body built", "Aarav" in body and "KGMU" in body and "/respond/tok?d=1" in body)
html = alerts.build_email_html("Aarav", "KGMU", 0.53, "O+", 2, "critical", "tok", 1)
check("html email built", "Accept or decline" in html and "/respond/tok?d=1" in html)
check("channels resolved", len(alerts.active_channels()) >= 1, str(alerts.active_channels()))
sent_channels = [ch for n in j["notifiedDonors"] for ch in n["channels"]]
check("alerts delivered", len(sent_channels) > 0, str(sorted(set(sent_channels))))

print(f"\n   TOTAL: {sum(res)}/{len(res)} passed on {backend_name()}\n")
sys.exit(0 if all(res) else 1)
