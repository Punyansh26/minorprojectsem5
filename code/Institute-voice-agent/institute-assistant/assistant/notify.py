"""
Sends an approved ticket's email via SMTP. Deliberately NOT called anywhere automatically —
only review_tickets.py invokes this, after a human has explicitly approved a specific ticket.

Setup (Gmail example): create a dedicated project email account, then generate an "app
password" (Google Account -> Security -> 2-Step Verification -> App Passwords) — this is
NOT your normal account password, and using a dedicated account (not your real institute
email) is deliberate: this is a student project, not a system that should send mail as if
from the actual institute.
"""
import smtplib
from email.mime.text import MIMEText

from assistant.config import settings
from assistant.dialogue import valid_email


def send_email(to: str, subject: str, body: str):
    """Reject invalid/example recipients before opening a bounded SMTP connection."""
    if not valid_email(to) or to.rsplit("@", 1)[-1].lower().endswith("example.edu"):
        raise ValueError("Configure a real, valid recipient email before sending.")
    if any(c in subject for c in "\r\n"):
        raise ValueError("Email subject must be a single line.")
    if not settings.SMTP_USER or not settings.SMTP_APP_PASSWORD:
        raise RuntimeError(
            "SMTP_USER / SMTP_APP_PASSWORD not set in .env — cannot send email. "
            "See assistant/notify.py's module docstring for setup."
        )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"] = to

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_APP_PASSWORD)
        server.sendmail(settings.SMTP_USER, [to], msg.as_string())
