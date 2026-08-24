# JeevanLink

An emergency blood network. A hospital request is turned into a ranked,
consent-based, trackable donor response using location matching,
WhatsApp alerts and route guidance.

---

## Quick start (local)

```bash
pip install -r requirements.txt

python -m jeevanlink.init_db      # create tables (once)
python -m jeevanlink.seed_data    # demo donors (optional)

python main.py
```

Open **http://127.0.0.1:5000**

| Page | Purpose |
|---|---|
| `/` | Home |
| `/donate` | Donor registration |
| `/request` | Create a blood request |
| `/respond/<token>` | Donor accepts or declines |
| `/api/health` | Backend status |

Tests:

```bash
python -m pytest jeevanlink/tests -q      # 17 passed
python verify.py                          # 30 end-to-end checks
```

---

## How a request flows

```
Requester fills /request
      ↓
requests.create_blood_request()      saved
donors.get_candidate_donors()        compatible + available + consented
matching.score_and_rank_donors()     0.7 x distance + 0.3 x recency
alerts.send_donor_alert()            WhatsApp to the top three
notifications.save_notification()    duplicate protection
events.add_request_event()           audit trail
      ↓
Donor taps the link  ->  /respond/<token>?d=<id>
      ↓
First donor to accept wins (atomic UPDATE, others get 409)
      ↓
Route, ETA and phone number unlock only after acceptance
```

---

## Two databases, one codebase

| Environment | Database | How |
|---|---|---|
| Local | SQLite | default, zero setup |
| Cloud | PostgreSQL | set `DATABASE_URL` |

The modules keep writing SQLite-flavoured SQL. `database.py` translates
it for PostgreSQL, so a shared cloud database needs no code changes.

Check which one is live:

```bash
curl http://127.0.0.1:5000/api/health
```

---

## Configuration

Run the setup wizard. It asks only for what you have, tests each
credential against the real service, and writes a working `.env`:

```bash
python setup_alerts.py
```

Or copy `.env.example` to `.env` and edit it by hand. The app loads
that file automatically on startup. Real environment variables always
take precedence, so a host like Render keeps working unchanged.

Diagnose email problems with:

```bash
python check_email.py you@example.com
```

## Alerts

| Channel | Enabled by |
|---|---|
| WhatsApp | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_WHATSAPP_FROM` |
| Email via Resend | `RESEND_API_KEY` |
| Email via SMTP | `SMTP_HOST` + `SMTP_USER` (+ `SMTP_PASSWORD`) |
| SMS | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_PHONE_NUMBER` |
| Console | nothing configured (default) |

Channels run together. A donor with both a phone number and an email
address receives both messages, and each delivery is recorded
separately in the `notifications` table.

Set `ALERT_CHANNELS=email` (or `whatsapp`) to force just one.

A delivery failure never breaks a request — it is logged, the other
channels still run, and the console fallback catches the rest.

---

## Going online

See **DEPLOY.md**. Neon (PostgreSQL) + Render (hosting) +
Twilio sandbox (WhatsApp), all on free tiers.

---

## Project layout

```
main.py                 entry point
verify.py               30-check end-to-end script
requirements.txt
Procfile  render.yaml   deployment
.env.example

jeevanlink/
    run.py              Flask app factory, serves frontend + API
    api.py              request lifecycle, matching, admin endpoints
    donors.py           donor endpoints + donor repository
    requests.py         blood request repository
    matching.py         Haversine distance and ranking
    alerts.py           WhatsApp / SMS / console delivery
    notifications.py    delivery records, deduplication
    events.py           audit trail
    admin.py            dashboard counters
    database.py         SQLite and PostgreSQL adapter
    schema.sql          SQLite schema
    schema_postgres.sql PostgreSQL schema
    init_db.py          create tables
    seed_data.py        demo donors
    tests/              17 tests

frontend/
    index.html/.css/.js     home
    donar.html/.css/.js     donor registration
    request.html/.js        blood request
    respond.html/.js        donor response
```

---

## Documentation

| File | Contents |
|---|---|
| `DEPLOY.md` | Putting it online, step by step |
| `VSCODE_SETUP.md` | Running it in VS Code on Windows |
| `TECH_MAP.md` | Where HTML, CSS, JS, Python and SQL are each used |
| `EXPLAINED.md` | Every file and concept explained |
| `FIXES.md` | Bugs that were found and how they were fixed |

---

## Safety note

JeevanLink coordinates people. It does not replace medical screening.
Final donor eligibility, cross-matching and compatibility checks are
always performed by the hospital or licensed blood bank.
