"""Delivery validation must reject bad input before connecting to SMTP or SQLite."""
from unittest.mock import Mock

import pytest

from assistant import db, notify


@pytest.mark.parametrize("recipient", ["abc", "admissions@iiitnr.example.edu", "a@b.com\nBcc:other@b.com"])
def test_invalid_or_placeholder_recipient_does_not_connect(monkeypatch, recipient):
    smtp = Mock()
    monkeypatch.setattr(notify.smtplib, "SMTP", smtp)
    with pytest.raises(ValueError):
        notify.send_email(recipient, "Subject", "Body")
    smtp.assert_not_called()


def test_reminder_database_rejects_invalid_details_before_opening(monkeypatch):
    conn = Mock()
    monkeypatch.setattr(db, "_get_conn", conn)
    for email, due in [("abc", "2099-10-01"), ("ok@example.org", "2099-02-30"), ("ok@example.org", "2000-01-01")]:
        with pytest.raises(ValueError):
            db.create_reminder("100", email, "Submit form", due)
    conn.assert_not_called()
