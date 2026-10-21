"""
Checks for due reminders and actually sends them. Unlike escalation tickets, reminders don't
need human review — the student already asked for this specific reminder, so there's no
judgment call to make; just send it when the date arrives.

Usage:
    python check_reminders.py
    python check_reminders.py --as-of 2026-10-15   # test with a specific date instead of today
"""
import argparse

from assistant.db import list_due_reminders, mark_reminder_sent
from assistant.notify import send_email
from assistant.dialogue import valid_email


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD — check as of this date instead of today")
    args = parser.parse_args()

    due = list_due_reminders(as_of=args.as_of)
    if not due:
        print("No due reminders.")
        return

    print(f"{len(due)} due reminder(s):\n")
    for r in due:
        print(f"Reminder #{r.id} for {r.student_id} <{r.student_email}>: \"{r.message}\" (due {r.due_date})")
        if not valid_email(r.student_email):
            print("  No valid email on file — skipping, not marking as sent.\n")
            continue
        try:
            send_email(
                to=r.student_email,
                subject=f"Reminder: {r.message}",
                body=f"This is your requested reminder from the IIIT-NR Institute Assistant:\n\n{r.message}\n\n(Due: {r.due_date})",
            )
            mark_reminder_sent(r.id)
            print(f"  ✅ Sent and marked as sent.\n")
        except Exception as e:
            print(f"  ❌ Failed to send: {e}\n")


if __name__ == "__main__":
    main()
