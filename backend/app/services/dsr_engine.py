
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.request import RequestCreate
from app.services.audit_logger import record_audit_event

from app.services.persistence import (
    save_request,
    get_request,
    update_request_status,
)


# Temporary in-memory cache.
# PostgreSQL is now the persistent source of truth.
requests_store = {}


def _restore_request(db_record):
    """
    Convert a PostgreSQL request row into the dictionary
    format expected by the existing application.
    """

    if db_record is None:
        return None

    request_data = db_record.get("request_data") or {}

    request_record = {
        **request_data,
        "request_id": str(db_record["request_id"]),
        "full_name": db_record["full_name"],
        "email": db_record["email"],
        "request_type": db_record["request_type"],
        "status": db_record["status"],
        "created_at": (
            db_record["created_at"].isoformat()
            if db_record.get("created_at")
            else request_data.get("created_at")
        ),
    }

    return request_record


def create_request(request_data: RequestCreate):
    """
    Create a new DSR request and persist it in PostgreSQL.
    """

    request_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    new_request = {
        "request_id": request_id,
        "full_name": request_data.full_name,
        "email": request_data.email,
        "request_type": request_data.request_type,
        "status": "received",
        "created_at": created_at,
    }

    # Save to PostgreSQL first.
    # If this fails, the request is not added to the cache.
    save_request(request_id, new_request)

    # Update temporary cache only after successful persistence.
    requests_store[request_id] = new_request

    # Record request creation in the audit system.
    record_audit_event(
        request_id=request_id,
        action="REQUEST_CREATED",
        actor="request-service",
        details=f"{request_data.request_type} request created",
    )

    return new_request


def get_all_requests():
    """
    Retrieve all requests from PostgreSQL.
    """

    from app.database import get_app_connection

    with get_app_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM dsr_requests
                ORDER BY created_at DESC;
                """
            )

            records = cursor.fetchall()

    result = []

    for record in records:
        request_record = _restore_request(record)
        result.append(request_record)

        # Refresh cache.
        requests_store[request_record["request_id"]] = request_record

    return result


def get_request_by_id(request_id: str):
    """
    Retrieve one request from PostgreSQL.
    """

    db_record = get_request(request_id)

    if db_record is None:
        requests_store.pop(request_id, None)
        return None

    request_record = _restore_request(db_record)

    # Refresh cache.
    requests_store[request_id] = request_record

    return request_record


ALLOWED_TRANSITIONS = {
    "received": "verified",
    "verified": "located",
    "located": "approved",
    "approved": "executed",
    "executed": "certified",
}


def advance_request(request_id: str):
    """
    Advance a request through the permitted workflow.

    The new status is persisted in PostgreSQL.
    """

    request_record = get_request_by_id(request_id)

    if request_record is None:
        return None, "Request not found"

    current_status = request_record["status"]

    if current_status == "received":
        return None, (
            "Identity verification is required before advancing"
        )

    next_status = ALLOWED_TRANSITIONS.get(current_status)

    if next_status is None:
        return None, (
            "Request has already completed the workflow"
        )

    # Persist status change first.
    update_request_status(request_id, next_status)

    # Update cache after successful database operation.
    request_record["status"] = next_status
    requests_store[request_id] = request_record

    return request_record, None
