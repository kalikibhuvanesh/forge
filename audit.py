"""SHA-256 hash-chained audit log. Never put personal data or documents in these records."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent

GENESIS = "0" * 64
_FIELDS = ("event_id", "action_type", "occurred_at", "application_ref", "verification_result", "evidence_ref")


def compute_hash(prev_hash: str, payload: dict) -> str:
    body = json.dumps({k: payload.get(k) for k in _FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def _payload(e: AuditEvent) -> dict:
    return {k: getattr(e, k) for k in _FIELDS}


def record(db: Session, action_type: str, application_ref: str | None = None,
           verification_result: str | None = None, evidence_ref: str | None = None) -> AuditEvent:
    last = db.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)).first()
    prev = last.event_hash if last else GENESIS
    ev = AuditEvent(action_type=action_type, occurred_at=datetime.now(timezone.utc).isoformat(),
                    application_ref=application_ref, verification_result=verification_result,
                    evidence_ref=evidence_ref, prev_hash=prev, event_hash="")
    import uuid
    ev.event_id = str(uuid.uuid4())
    ev.event_hash = compute_hash(prev, _payload(ev))
    db.add(ev)
    db.commit()
    return ev


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for e in db.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
        count += 1
        if e.prev_hash != prev or compute_hash(prev, _payload(e)) != e.event_hash:
            return {"valid": False, "checked": count, "first_bad_seq": e.seq}
        prev = e.event_hash
    return {"valid": True, "checked": count, "first_bad_seq": None}
