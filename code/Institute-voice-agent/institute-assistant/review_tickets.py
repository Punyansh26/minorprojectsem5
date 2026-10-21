"""
Staff-facing review tool for pending escalation tickets. Nothing gets emailed anywhere
without a human explicitly approving it here.

Usage:
    python review_tickets.py
"""
from assistant.db import list_tickets, update_ticket_status
from assistant.notify import send_email


def main():
    tickets = list_tickets(status="pending")
    if not tickets:
        print("No pending tickets.")
        return

    print(f"{len(tickets)} pending ticket(s):\n")
    for t in tickets:
        print(f"--- Ticket #{t.id} ({t.timestamp}) ---")
        print(f"Student: {t.student_id} ({t.student_category}) | Category: {t.detected_category}")
        print(f"Question: {t.question}")
        print(f"To: {t.recipient_email}")
        print(f"Subject: {t.email_subject}")
        print(f"Body:\n{t.email_body}\n")

        choice = input(f"[a]pprove & send / [r]eject / [s]kip for ticket #{t.id}? ").strip().lower()
        if choice == "a":
            try:
                send_email(t.recipient_email, t.email_subject, t.email_body)
                update_ticket_status(t.id, "sent")
                print(f"✅ Sent and marked ticket #{t.id} as sent.\n")
            except Exception as e:
                print(f"❌ Failed to send ticket #{t.id}: {e}\n")
        elif choice == "r":
            update_ticket_status(t.id, "rejected")
            print(f"Ticket #{t.id} rejected.\n")
        else:
            print(f"Skipped ticket #{t.id} (still pending).\n")


if __name__ == "__main__":
    main()