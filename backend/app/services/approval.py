from datetime import datetime, timezone

from app.services.dsr_engine import get_request_by_id
from app.services.deletion_plan import get_deletion_plan
from app.services.audit_logger import record_audit_event
from app.services.persistence import (
    save_approval,
    get_approval as get_persisted_approval,
    update_request_status,
)

approval_store = {}


def process_approval(request_id: str, approval_data, reviewer):

    request_record = get_request_by_id(request_id)

    if request_record is None:
        return None, "Request not found"

    # Server-side role verification
    if reviewer.get("role") != "admin":
        return None, "Only administrators can review deletion plans"

    # Identity comes from the authenticated account
    reviewer_id = reviewer["email"]
    reviewer_role = reviewer["role"]

    if (
        reviewer_id.strip().lower()
        == request_record["email"].strip().lower()
    ):
        return None, "Requester cannot approve their own deletion request"

    if request_record.get("request_type") != "deletion":
        return None, "Only deletion requests can be approved"

    if request_record.get("status") != "located":
        return None, "Request must have a deletion preview before approval"

    deletion_plan = get_deletion_plan(request_id)

    if not deletion_plan:
        return None, "Deletion preview must be generated first"

    if get_persisted_approval(request_id) is not None:
        return None, "This request has already been reviewed"

    decision = approval_data.decision

    reviewed_at = datetime.now(timezone.utc).isoformat()

    approval_record = {
        "request_id": request_id,
        "reviewer_id": reviewer_id,
        "reviewer_role": reviewer_role,
        "decision": decision,
        "comments": approval_data.comments,
        "status": decision,
        "reviewed_at": reviewed_at,
    }

    try:
        save_approval(request_id, approval_record)

        persisted = get_persisted_approval(request_id)

        if persisted is None:
            return None, "Approval could not be saved"

        saved_record = persisted.get("approval_data", {})

        if (
            saved_record.get("reviewer_id") != reviewer_id
            or saved_record.get("decision") != decision
        ):
            return None, "This request has already been reviewed"

        new_status = (
            "approved" if decision == "approved" else "rejected"
        )

        update_request_status(request_id, new_status)

        record_audit_event(
            request_id=request_id,
            action=(
                "DELETION_APPROVED"
                if decision == "approved"
                else "DELETION_REJECTED"
            ),
            actor=reviewer_id,
            details=f"Deletion plan {decision}",
        )

        approval_store[request_id] = approval_record

        return approval_record, None

    except Exception:
        return None, "Unable to persist approval. Check application database."


def get_approval(request_id: str):

    persisted_record = get_persisted_approval(request_id)

    if persisted_record is None:
        approval_store.pop(request_id, None)
        return None

    approval_record = persisted_record.get("approval_data")

    if approval_record is None:
        return None

    approval_store[request_id] = approval_record

    return approval_record