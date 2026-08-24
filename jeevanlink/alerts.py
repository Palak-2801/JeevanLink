"""Outbound alerts to donors.

Three delivery channels, any combination of which can be active at the
same time. A donor with both a phone number and an email address can
receive both messages.

1. **WhatsApp** via the Twilio sandbox. Free, no credit card. Each
   recipient sends one join message to the sandbox number first.
2. **Email**, either through the Resend HTTP API (one API key, nothing
   else to configure) or through any SMTP server such as Gmail or
   Brevo. No opt-in step is required for either.
3. **SMS** via Twilio. Needs a purchased number.

If nothing is configured, or every configured channel fails, the alert
is printed to the console so development and demos still work.

Environment variables
---------------------
ALERT_CHANNELS          comma separated: whatsapp,email,sms
                        empty = use whatever is configured

TWILIO_ACCOUNT_SID      Twilio console
TWILIO_AUTH_TOKEN       Twilio console
TWILIO_WHATSAPP_FROM    whatsapp:+14155238886
TWILIO_PHONE_NUMBER     only for real SMS

RESEND_API_KEY          re_... from resend.com, simplest option
RESEND_FROM             onboarding@resend.dev unless you own a domain

SMTP_HOST               smtp.gmail.com
SMTP_PORT               587
SMTP_USER               you@gmail.com
SMTP_PASSWORD           16 character Gmail app password
SMTP_FROM               optional display sender
SMTP_USE_TLS            true by default

DEFAULT_COUNTRY_CODE    +91
PUBLIC_BASE_URL         https://your-app.onrender.com
"""

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage


DEFAULT_COUNTRY_CODE = os.getenv("DEFAULT_COUNTRY_CODE", "+91")


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def normalise_phone(phone: str) -> str:
    """Convert a stored number into E.164 format.

    ``9876543210``    -> ``+919876543210``
    ``09876543210``   -> ``+919876543210``
    ``+919876543210`` -> unchanged
    """
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")

    if digits.startswith("+"):
        return digits

    digits = digits.lstrip("0")
    country = DEFAULT_COUNTRY_CODE.lstrip("+")

    if digits.startswith(country) and len(digits) > 10:
        return "+" + digits

    return DEFAULT_COUNTRY_CODE + digits


def respond_url(public_token: str, donor_id=None) -> str:
    url = f"{public_base_url()}/respond/{public_token}"
    if donor_id is not None:
        url += f"?d={donor_id}"
    return url


# ---------------------------------------------------------------------
# WHICH CHANNELS ARE AVAILABLE
# ---------------------------------------------------------------------

def twilio_configured() -> bool:
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))


def whatsapp_configured() -> bool:
    return twilio_configured() and bool(os.getenv("TWILIO_WHATSAPP_FROM"))


def sms_configured() -> bool:
    return twilio_configured() and bool(os.getenv("TWILIO_PHONE_NUMBER"))


def resend_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY"))


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER"))


def email_configured() -> bool:
    return resend_configured() or smtp_configured()


def email_provider() -> str:
    if resend_configured():
        return "resend"
    if smtp_configured():
        return "smtp"
    return "none"


def active_channels() -> list:
    """Channels that will be attempted, in order."""
    forced = os.getenv("ALERT_CHANNELS", "").strip().lower()

    if forced:
        wanted = [c.strip() for c in forced.split(",") if c.strip()]
        return [c for c in wanted if c in ("whatsapp", "email", "sms", "console")]

    channels = []
    if whatsapp_configured():
        channels.append("whatsapp")
    if email_configured():
        channels.append("email")
    if sms_configured() and not whatsapp_configured():
        channels.append("sms")

    return channels or ["console"]


def active_channel() -> str:
    """Single label for the health endpoint."""
    return ", ".join(active_channels())


# ---------------------------------------------------------------------
# MESSAGE CONTENT
# ---------------------------------------------------------------------

def build_message(donor_name, hospital, distance_km, blood_group,
                  units, urgency, public_token, donor_id=None) -> str:
    """Plain text body, used for WhatsApp and SMS."""
    return (
        f"JeevanLink emergency alert\n\n"
        f"Hello {donor_name}, a patient near you needs blood.\n\n"
        f"Blood group : {blood_group}\n"
        f"Units       : {units}\n"
        f"Hospital    : {hospital}\n"
        f"Distance    : about {distance_km} km from you\n"
        f"Urgency     : {urgency}\n\n"
        f"Tap to accept or decline:\n"
        f"{respond_url(public_token, donor_id)}\n\n"
        f"Your number stays private until you accept."
    )


def build_email_html(donor_name, hospital, distance_km, blood_group,
                     units, urgency, public_token, donor_id=None) -> str:
    """HTML body for email. Inline styles only, for mail client support."""
    link = respond_url(public_token, donor_id)

    rows = [
        ("Blood group", blood_group),
        ("Units needed", units),
        ("Hospital", hospital),
        ("Distance", f"about {distance_km} km from you"),
        ("Urgency", str(urgency).capitalize()),
    ]

    cells = "".join(
        f'<tr>'
        f'<td style="padding:10px 0;color:#6f545a;font-size:14px;">{label}</td>'
        f'<td style="padding:10px 0;text-align:right;font-weight:600;'
        f'font-size:14px;color:#1a1416;">{value}</td>'
        f'</tr>'
        for label, value in rows
    )

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#f7f2f3;
             font-family:Arial,Helvetica,sans-serif;">

  <div style="max-width:520px;margin:0 auto;background:#ffffff;
              border-radius:14px;overflow:hidden;
              border:1px solid #ecdfe2;">

    <div style="background:#a5182b;padding:24px 28px;">
      <p style="margin:0;color:#ffc7d1;font-size:11px;
                letter-spacing:.12em;font-weight:700;">
        JEEVANLINK EMERGENCY ALERT
      </p>
      <h1 style="margin:8px 0 0;color:#ffffff;font-size:24px;">
        A patient near you needs blood
      </h1>
    </div>

    <div style="padding:28px;">

      <p style="margin:0 0 18px;color:#1a1416;font-size:15px;">
        Hello {donor_name},
      </p>

      <table style="width:100%;border-collapse:collapse;">
        {cells}
      </table>

      <div style="text-align:center;margin:28px 0 8px;">
        <a href="{link}"
           style="display:inline-block;padding:14px 30px;
                  background:#a5182b;color:#ffffff;
                  text-decoration:none;border-radius:999px;
                  font-weight:700;font-size:15px;">
          Accept or decline
        </a>
      </div>

      <p style="margin:20px 0 0;color:#6f545a;font-size:12px;
                text-align:center;">
        Your phone number stays private until you accept.
      </p>

      <p style="margin:16px 0 0;color:#9b8b8f;font-size:11px;
                text-align:center;word-break:break-all;">
        {link}
      </p>

    </div>

    <div style="padding:16px 28px;background:#faf6f7;
                border-top:1px solid #ecdfe2;">
      <p style="margin:0;color:#9b8b8f;font-size:11px;text-align:center;">
        Final screening and compatibility checks are carried out by the
        hospital or licensed blood bank.
      </p>
    </div>

  </div>

</body>
</html>"""


# ---------------------------------------------------------------------
# DELIVERY: WHATSAPP AND SMS
# ---------------------------------------------------------------------

def _twilio_client():
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")

    if not sid or not token:
        return None

    try:
        from twilio.rest import Client
        return Client(sid, token)
    except Exception as error:
        print(f"[alerts] Twilio client unavailable: {error}")
        return None


def send_via_twilio(channel, to_number, body):
    """Returns ``(delivered, provider_message_id)``."""
    client = _twilio_client()

    if client is None:
        return False, None

    try:
        if channel == "whatsapp":
            sender = os.getenv("TWILIO_WHATSAPP_FROM", "")
            if not sender.startswith("whatsapp:"):
                sender = "whatsapp:" + sender
            destination = "whatsapp:" + to_number
        else:
            sender = os.getenv("TWILIO_PHONE_NUMBER", "")
            destination = to_number

        message = client.messages.create(
            body=body,
            from_=sender,
            to=destination,
        )

        print(f"[alerts] {channel} sent to {to_number} ({message.sid})")
        return True, message.sid

    except Exception as error:
        print(f"[alerts] {channel} failed for {to_number}: {error}")
        return False, None


# ---------------------------------------------------------------------
# DELIVERY: EMAIL VIA THE RESEND HTTP API
# ---------------------------------------------------------------------

def send_via_resend(to_address, subject, text_body, html_body):
    """Send through Resend. Returns ``(delivered, message_id)``.

    Only an API key is needed. Without a verified domain Resend allows
    the shared ``onboarding@resend.dev`` sender, which can deliver to
    the address the Resend account was registered with.
    """
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("RESEND_FROM", "JeevanLink <onboarding@resend.dev>")

    if not api_key or not to_address:
        return False, None

    payload = json.dumps({
        "from": sender,
        "to": [to_address],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "JeevanLink/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
            message_id = body.get("id")
            print(f"[alerts] email sent to {to_address} via Resend ({message_id})")
            return True, message_id

    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        print(f"[alerts] Resend rejected {to_address}: {error.code} {detail}")
        return False, None

    except Exception as error:
        print(f"[alerts] Resend failed for {to_address}: {error}")
        return False, None


# ---------------------------------------------------------------------
# DELIVERY: EMAIL VIA SMTP
# ---------------------------------------------------------------------

def send_via_email(to_address, subject, text_body, html_body):
    """Returns ``(delivered, message_id)``."""
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("SMTP_FROM") or user
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() != "false"

    if not host or not user or not to_address:
        return False, None

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"JeevanLink <{sender}>"
    message["To"] = to_address
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                if password:
                    server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                if use_tls:
                    try:
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                    except Exception:
                        # Local test servers often have no TLS. Keep going.
                        pass
                if password:
                    server.login(user, password)
                server.send_message(message)

        print(f"[alerts] email sent to {to_address}")
        return True, message.get("Message-ID")

    except Exception as error:
        print(f"[alerts] email failed for {to_address}: {error}")
        return False, None


# ---------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------

def send_donor_alert(phone, donor_name, hospital, distance_km,
                     blood_group, units, urgency, public_token,
                     donor_id=None, email=None):
    """Alert one donor on every configured channel.

    Returns a list of ``(channel, delivered, provider_message_id)``, one
    entry per channel that was attempted. The console fallback is only
    used when nothing else delivered.
    """
    text_body = build_message(
        donor_name, hospital, distance_km,
        blood_group, units, urgency, public_token, donor_id
    )

    to_number = normalise_phone(phone)
    results = []

    for channel in active_channels():

        if channel == "whatsapp" and whatsapp_configured():
            delivered, provider_id = send_via_twilio("whatsapp", to_number, text_body)
            results.append(("whatsapp", delivered, provider_id))

        elif channel == "sms" and sms_configured():
            delivered, provider_id = send_via_twilio("sms", to_number, text_body)
            results.append(("sms", delivered, provider_id))

        elif channel == "email" and email_configured() and email:
            html_body = build_email_html(
                donor_name, hospital, distance_km,
                blood_group, units, urgency, public_token, donor_id
            )
            subject = f"Urgent: {blood_group} blood needed at {hospital}"

            if resend_configured():
                delivered, provider_id = send_via_resend(
                    email, subject, text_body, html_body
                )
            else:
                delivered, provider_id = send_via_email(
                    email, subject, text_body, html_body
                )

            results.append(("email", delivered, provider_id))

    if not any(delivered for _, delivered, _ in results):
        print("=" * 58)
        print(f"  ALERT (console) -> {to_number}"
              + (f" / {email}" if email else ""))
        for line in text_body.splitlines():
            print(f"  {line}")
        print("=" * 58)
        results.append(("console", True, None))

    return results