
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.services.persistence import (
    save_audit_event,
    get_persisted_audit_events,
)


def calculate_hash(event_data):
    event_string = json.dumps(
        event_data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(event_string.encode("utf-8")).hexdigest()


def _normalize_event(row):
    event = dict(row)

    event["event_id"] = str(event["event_id"])
    event["request_id"] = str(event["request_id"])

    timestamp = event.get("timestamp") or event.get("event_timestamp")

    if isinstance(timestamp, datetime):
        timestamp = timestamp.astimezone(timezone.utc).isoformat()

    event["timestamp"] = timestamp

    # Database column names are mapped to the names used by the hash chain.
    event.pop("event_timestamp", None)
    event.pop("event_sequence", None)

    return event


def _get_all_events():
    rows = get_persisted_audit_events()
    return [_normalize_event(row) for row in rows]


def record_audit_event(
    request_id: str,
    action: str,
    actor: str,
    details: str = "",
):
    events = _get_all_events()

    previous_hash = (
        events[-1]["event_hash"] if events else "GENESIS"
    )

    event = {
        "event_id": str(uuid4()),
        "request_id": str(request_id),
        "action": action,
        "actor": actor,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "previous_hash": previous_hash,
    }

    event["event_hash"] = calculate_hash(event)

    # Persist before returning the event.
    save_audit_event(event)

    return event


def get_audit_events(request_id: str = None):
    events = _get_all_events()

    if request_id is None:
        return events

    return [
        event for event in events
        if event["request_id"] == str(request_id)
    ]


def verify_audit_chain():
    events = _get_all_events()
    previous_hash = "GENESIS"

    for event in events:
        event_data = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }

        if event.get("previous_hash") != previous_hash:
            return False

        expected_hash = calculate_hash(event_data)

        if event.get("event_hash") != expected_hash:
            return False

        previous_hash = event["event_hash"]

    return True


def test_tampering():
    events = _get_all_events()

    if not events:
        return {
            "message": "No audit events available to test",
            "integrity": verify_audit_chain(),
        }

    test_events = [dict(event) for event in events]
    test_events[0]["details"] = "Modified audit record"

    previous_hash = "GENESIS"

    for event in test_events:
        event_data = {
            key: value
            for key, value in event.items()
            if key != "event_hash"
        }

        if (
            event.get("previous_hash") != previous_hash
            or event.get("event_hash") != calculate_hash(event_data)
        ):
            return {
                "message": "Tampering detected successfully",
                "integrity": False,
            }

        previous_hash = event["event_hash"]

    return {
        "message": "No tampering detected",
        "integrity": True,
    }
