"""Email delivery diagnostic.

Run this when an alert email does not arrive:

    .\\.venv\\Scripts\\python.exe check_email.py you@gmail.com

It reports which settings were found, connects to the SMTP server,
and sends one test message, printing the exact failure if there is one.
"""

import os
import smtplib
import ssl
import sys

import jeevanlink  # loads .env
from jeevanlink import alerts


def mask(value):
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def main():
    print("=" * 60)
    print("  JEEVANLINK EMAIL DIAGNOSTIC")
    print("=" * 60)

    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT", "587")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM") or user

    print("\n1. SETTINGS FOUND")
    print(f"   SMTP_HOST     : {host or '(not set)'}")
    print(f"   SMTP_PORT     : {port}")
    print(f"   SMTP_USER     : {user or '(not set)'}")
    print(f"   SMTP_PASSWORD : {mask(password)}  "
          f"({len(password)} characters)")
    print(f"   active channels: {alerts.active_channels()}")

    problems = []

    if not host:
        problems.append("SMTP_HOST is missing")
    if not user:
        problems.append("SMTP_USER is missing")
    local_server = (host or "").lower() in ("127.0.0.1", "localhost", "::1")

    if not password and not local_server:
        problems.append("SMTP_PASSWORD is missing")

    if password and "gmail" in (host or ""):
        stripped = password.replace(" ", "")
        if len(stripped) != 16:
            problems.append(
                f"a Gmail app password is 16 characters, this one is "
                f"{len(stripped)} - a normal account password will not work"
            )

    if problems:
        print("\n   PROBLEMS")
        for item in problems:
            print(f"     - {item}")
        print("\n   Fix the .env file and run this again.")
        return 1

    recipient = sys.argv[1] if len(sys.argv) > 1 else user
    print(f"\n2. SENDING A TEST MESSAGE TO {recipient}")

    try:
        port_number = int(port)

        if port_number == 465:
            server = smtplib.SMTP_SSL(
                host, port_number,
                context=ssl.create_default_context(), timeout=20
            )
        else:
            server = smtplib.SMTP(host, port_number, timeout=20)
            server.ehlo()
            use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"
            if use_tls:
                try:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    print("   TLS negotiated                 OK")
                except Exception as tls_error:
                    print(f"   TLS unavailable, continuing    ({tls_error})")

        print("   connected to the server        OK")

        if password:
            server.login(user, password)
            print("   signed in                      OK")
        else:
            print("   sign in skipped (no password)  OK")

        message = (
            f"From: JeevanLink <{sender}>\r\n"
            f"To: {recipient}\r\n"
            f"Subject: JeevanLink test message\r\n"
            f"\r\n"
            f"If you can read this, email alerts are working.\r\n"
        )
        server.sendmail(sender, [recipient], message)
        print("   message accepted               OK")

        server.quit()

        print(f"\n   SUCCESS. Check the inbox for {recipient}, "
              f"including the spam folder.")
        return 0

    except smtplib.SMTPAuthenticationError as error:
        print("   sign in                        FAILED")
        print(f"\n   {error}")
        print("\n   The password was rejected. Use an app password from")
        print("   myaccount.google.com/apppasswords, not the password you")
        print("   type into Gmail. Two step verification must be on first.")
        return 1

    except Exception as error:
        print("   FAILED")
        print(f"\n   {type(error).__name__}: {error}")
        print("\n   Common causes: wrong SMTP_HOST or SMTP_PORT, or a")
        print("   network or firewall block on the outgoing connection.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
