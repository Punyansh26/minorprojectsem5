"""
Tickets: one row per escalated question, holding a drafted email and its review status.
Reminders: one row per "remind me to X by Y" request — genuinely checked and sent, not mocked.

Status lifecycle (tickets): pending -> sent (staff approved) or rejected (staff dismissed it).
This is deliberately a plain SQLite table, not an ORM — small, inspectable, and enough for
a student project's real (not simulated) escalation/reminder system.
"""
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from assistant.config import settings
from assistant.dialogue import valid_email
from assistant import action_requests


@dataclass
class Ticket:
    id: int
    timestamp: str
    student_id: str
    student_category: str
    detected_category: str
    question: str
    recipient_email: str
    email_subject: str
    email_body: str
    status: str  # "pending" | "sent" | "rejected"


@dataclass
class Reminder:
    id: int
    created_at: str
    student_id: str
    student_email: str
    message: str
    due_date: str  # YYYY-MM-DD
    sent: int  # 0 or 1


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.TICKETS_DB_PATH, timeout=settings.CHECKPOINT_TIMEOUT_SECONDS)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            student_id TEXT NOT NULL,
            student_category TEXT NOT NULL,
            detected_category TEXT NOT NULL,
            question TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            email_subject TEXT NOT NULL,
            email_body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            student_id TEXT NOT NULL,
            student_email TEXT NOT NULL,
            message TEXT NOT NULL,
            due_date TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
        )
    """)
    return conn


def create_ticket(student_id: str, student_category: str, detected_category: str, question: str,
                   recipient_email: str, email_subject: str, email_body: str) -> int:
    conn = _get_conn()
    try:
        request = action_requests.begin(conn, "ticket", [student_id, student_category, detected_category,
            question, recipient_email, email_subject, email_body])
        if request and request[2] is not None:
            return request[2]
        cur = conn.execute(
            """INSERT INTO tickets
               (timestamp, student_id, student_category, detected_category, question,
                recipient_email, email_subject, email_body, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (datetime.now(timezone.utc).isoformat(), student_id, student_category, detected_category,
             question, recipient_email, email_subject, email_body),
        )
        ticket_id = cur.lastrowid
        action_requests.finish(conn, request, ticket_id)
        return ticket_id
    finally:
        conn.close()


def list_tickets(status: str | None = "pending") -> list[Ticket]:
    conn = _get_conn()
    if status:
        rows = conn.execute("SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    conn.close()
    return [Ticket(*row) for row in rows]


def get_ticket(ticket_id: int) -> Ticket | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return Ticket(*row) if row else None


def update_ticket_status(ticket_id: int, status: str):
    conn = _get_conn()
    conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
    conn.commit()
    conn.close()


def create_reminder(student_id: str, student_email: str, message: str, due_date: str) -> int:
    """Validate delivery details even when called outside the conversational graph."""
    due = date.fromisoformat(due_date)
    if not valid_email(student_email) or not message.strip():
        raise ValueError("A valid email and reminder message are required.")
    if due < datetime.now(ZoneInfo(settings.TIMEZONE)).date():
        raise ValueError("Reminder date cannot be in the past.")
    due_date = due.isoformat()
    conn = _get_conn()
    try:
        request = action_requests.begin(conn, "reminder", [student_id, student_email, message, due_date])
        if request and request[2] is not None:
            return request[2]
        cur = conn.execute(
            """INSERT INTO reminders (created_at, student_id, student_email, message, due_date, sent)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (datetime.now(timezone.utc).isoformat(), student_id, student_email, message, due_date),
        )
        reminder_id = cur.lastrowid
        action_requests.finish(conn, request, reminder_id)
        return reminder_id
    finally:
        conn.close()


def list_due_reminders(as_of: str | None = None) -> list[Reminder]:
    """Reminders with due_date <= as_of (default: today) that haven't been sent yet."""
    as_of = date.fromisoformat(as_of).isoformat() if as_of else datetime.now(ZoneInfo(settings.TIMEZONE)).date().isoformat()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE sent = 0 AND due_date <= ? ORDER BY due_date", (as_of,)
    ).fetchall()
    conn.close()
    return [Reminder(*row) for row in rows]


def mark_reminder_sent(reminder_id: int):
    conn = _get_conn()
    conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()
