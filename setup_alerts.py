"""Interactive setup for JeevanLink.

    python setup_alerts.py

Asks for the credentials you have, tests each one against the real
service, and writes a working .env file. Anything you skip simply
falls back to printing alerts in the terminal, and the rest of the
app keeps working.
"""

import getpass
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def line(char="-", width=62):
    print(char * width)


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def ask_secret(prompt):
    try:
        value = getpass.getpass(f"{prompt}: ").strip()
    except Exception:
        value = input(f"{prompt}: ").strip()
    return value


def ask_yes(prompt, default=True):
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({hint}): ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


# ---------------------------------------------------------------------
# LIVE TESTS
# ---------------------------------------------------------------------

def test_resend(api_key, sender, recipient):
    payload = json.dumps({
        "from": sender,
        "to": [recipient],
        "subject": "JeevanLink setup test",
        "text": "If you can read this, email alerts are working.",
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
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
            return True, f"accepted, id {body.get('id')}"

    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:500]

        if error.code == 401:
            return False, f"HTTP 401 — invalid or revoked API key. Detail: {detail}"

        if error.code == 403:
            return False, f"HTTP 403 — access denied. Detail: {detail}"

        if error.code == 422:
            return False, (
                "HTTP 422 — Resend refused the sender or recipient. "
                "Without a verified domain, onboarding@resend.dev can "
                "send only to the email used for your Resend account. "
                f"Detail: {detail}"
            )

        return False, f"HTTP {error.code}: {detail}"

    except Exception as error:
        return False, str(error)


def test_smtp(host, port, user, password, recipient):
    try:
        port = int(port)

        if port == 465:
            server = smtplib.SMTP_SSL(
                host, port, context=ssl.create_default_context(), timeout=25
            )
        else:
            server = smtplib.SMTP(host, port, timeout=25)
            server.ehlo()
            try:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            except Exception:
                pass

        if password:
            server.login(user, password)

        message = (
            f"From: JeevanLink <{user}>\r\n"
            f"To: {recipient}\r\n"
            f"Subject: JeevanLink setup test\r\n"
            f"\r\n"
            f"If you can read this, email alerts are working.\r\n"
        )
        server.sendmail(user, [recipient], message)
        server.quit()
        return True, "message accepted"

    except smtplib.SMTPAuthenticationError:
        return False, (
            "the password was rejected. Gmail needs an App Password "
            "from myaccount.google.com/apppasswords, not your normal "
            "account password"
        )

    except Exception as error:
        return False, f"{type(error).__name__}: {error}"


def test_twilio(sid, token, sender, recipient):
    try:
        from twilio.rest import Client
    except ImportError:
        return False, "the twilio package is not installed"

    try:
        client = Client(sid, token)
        if not sender.startswith("whatsapp:"):
            sender = "whatsapp:" + sender

        message = client.messages.create(
            body="JeevanLink setup test. Alerts are working.",
            from_=sender,
            to="whatsapp:" + recipient,
        )
        return True, f"accepted, sid {message.sid}"

    except Exception as error:
        text = str(error)
        if "20003" in text:
            return False, "the Account SID or Auth Token was rejected"
        if "63007" in text or "not currently opted in" in text:
            return False, (
                "that number has not joined the sandbox. Send the join "
                "code to the sandbox number from WhatsApp first"
            )
        return False, text[:200]


# ---------------------------------------------------------------------
# WIZARD
# ---------------------------------------------------------------------

def main():
    settings = {}

    line("=")
    print("  JEEVANLINK ALERT SETUP")
    line("=")
    print()
    print("  Anything you skip falls back to printing alerts in the")
    print("  terminal. The app works either way.")
    print()

    # ---------- EMAIL ----------
    line()
    print("  EMAIL")
    line()
    print("  1  Resend       one API key, nothing else  (easiest)")
    print("  2  Gmail        needs a 16 character App Password")
    print("  3  Other SMTP   Brevo, Outlook, your college server")
    print("  4  Skip email")
    print()

    choice = ask("  Choose 1-4", "1")

    if choice == "1":
        print()
        print("  Sign up at resend.com, then open API Keys and create one.")
        print("  It starts with re_")
        print()
        api_key = ask_secret("  API key")

        if api_key:
            sender = ask("  Send from",
                         "JeevanLink <onboarding@resend.dev>")
            recipient = ask("  Send the test to (your Resend account email)")

            if recipient:
                print("\n  Testing ...")
                ok, detail = test_resend(api_key, sender, recipient)
                print(f"  {'PASS' if ok else 'FAIL'}: {detail}\n")

                if ok or ask_yes("  Save these settings anyway?", False):
                    settings["RESEND_API_KEY"] = api_key
                    settings["RESEND_FROM"] = sender

    elif choice == "2":
        print()
        print("  Turn on 2-Step Verification at")
        print("    myaccount.google.com/security")
        print("  then create an App Password at")
        print("    myaccount.google.com/apppasswords")
        print()
        user = ask("  Gmail address")
        password = ask_secret("  App Password (16 characters)")
        password = password.replace(" ", "")

        if password and len(password) != 16:
            print(f"\n  Note: that is {len(password)} characters. An App "
                  f"Password is 16.")

        if user and password:
            print("\n  Testing ...")
            ok, detail = test_smtp("smtp.gmail.com", 587, user, password, user)
            print(f"  {'PASS' if ok else 'FAIL'}: {detail}\n")

            if ok or ask_yes("  Save these settings anyway?", False):
                settings["SMTP_HOST"] = "smtp.gmail.com"
                settings["SMTP_PORT"] = "587"
                settings["SMTP_USER"] = user
                settings["SMTP_PASSWORD"] = password

    elif choice == "3":
        host = ask("  SMTP host")
        port = ask("  SMTP port", "587")
        user = ask("  Username")
        password = ask_secret("  Password")
        recipient = ask("  Send the test to", user)

        if host and user:
            print("\n  Testing ...")
            ok, detail = test_smtp(host, port, user, password, recipient)
            print(f"  {'PASS' if ok else 'FAIL'}: {detail}\n")

            if ok or ask_yes("  Save these settings anyway?", False):
                settings["SMTP_HOST"] = host
                settings["SMTP_PORT"] = port
                settings["SMTP_USER"] = user
                settings["SMTP_PASSWORD"] = password

    # ---------- WHATSAPP ----------
    print()
    line()
    print("  WHATSAPP")
    line()
    print("  Sign up at twilio.com, then open")
    print("    Messaging  ->  Try it out  ->  Send a WhatsApp message")
    print("  Send the join code shown there to the sandbox number from")
    print("  your own WhatsApp before testing.")
    print()

    if ask_yes("  Set up WhatsApp now?", True):
        sid = ask("  Account SID (starts with AC)")
        token = ask_secret("  Auth Token")
        sender = ask("  Sandbox number", "whatsapp:+14155238886")
        recipient = ask("  Send the test to (+91...)")

        if sid and token and recipient:
            if not recipient.startswith("+"):
                recipient = "+91" + recipient.lstrip("0")

            print("\n  Testing ...")
            ok, detail = test_twilio(sid, token, sender, recipient)
            print(f"  {'PASS' if ok else 'FAIL'}: {detail}\n")

            if ok or ask_yes("  Save these settings anyway?", False):
                settings["TWILIO_ACCOUNT_SID"] = sid
                settings["TWILIO_AUTH_TOKEN"] = token
                settings["TWILIO_WHATSAPP_FROM"] = sender

    # ---------- DATABASE ----------
    print()
    line()
    print("  DATABASE")
    line()
    print("  Leave empty to use the local SQLite file.")
    print("  Paste a Neon or Render connection string to share one")
    print("  database across devices.")
    print()
    database_url = ask("  DATABASE_URL")
    if database_url:
        settings["DATABASE_URL"] = database_url

    # ---------- WRITE ----------
    settings.setdefault("PUBLIC_BASE_URL", "http://127.0.0.1:5000")
    settings.setdefault("DEFAULT_COUNTRY_CODE", "+91")

    print()
    line("=")

    if not settings:
        print("  Nothing to save. Alerts will print in the terminal.")
        line("=")
        return 0

    if ENV_PATH.exists():
        backup = ENV_PATH.parent / ".env.backup"
        backup.write_text(ENV_PATH.read_text(encoding="utf-8"),
                          encoding="utf-8")
        print(f"  Existing .env copied to {backup.name}")

    body = ["# Written by setup_alerts.py", ""]
    for key, value in settings.items():
        body.append(f"{key}={value}")
    body.append("")

    ENV_PATH.write_text("\n".join(body), encoding="utf-8")

    print(f"  Saved {len(settings)} settings to .env")
    print()
    print("  Next:")
    print("    .\\.venv\\Scripts\\python.exe main.py")
    print("    open http://127.0.0.1:5000/api/health")
    line("=")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was written.")
        sys.exit(1)
