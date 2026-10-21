"""Bind action ownership and idempotency to the same SQLite transaction as its draft."""
import hashlib
import json

from assistant.operations import current, check


def begin(conn, kind, payload):
    """Return an existing action ID, rejecting reuse for different action contents."""
    check("saving_action")
    operation = current()
    if operation is None:
        return None
    conn.execute("""CREATE TABLE IF NOT EXISTS action_requests (
        conversation_id TEXT NOT NULL, turn_id TEXT NOT NULL, kind TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL, action_id INTEGER NOT NULL,
        PRIMARY KEY(conversation_id, turn_id, kind))""")
    conn.execute("BEGIN IMMEDIATE")
    check()
    identity = (operation.conversation_id, operation.turn_id, kind)
    row = conn.execute("SELECT action_id,payload_sha256 FROM action_requests WHERE conversation_id=? AND turn_id=? AND kind=?",
                       identity).fetchone()
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if row and row[1] != fingerprint:
        conn.rollback()
        raise ValueError("request_conflict")
    return (identity, fingerprint, row[0] if row else None)


def finish(conn, request, action_id):
    """Commit the action and its request key together, closing the replay crash window."""
    if request:
        identity, fingerprint, _ = request
        conn.execute("INSERT INTO action_requests VALUES (?,?,?,?,?)", (*identity, fingerprint, action_id))
    conn.commit()
