from datetime import datetime, timezone
from uuid import uuid4

from app.services.persistence import (
    get_request,
    get_verification,
    get_deletion_plan,
    get_approval,
    get_execution,
)

from app.services.audit_logger import (
    get_audit_events,
    verify_audit_chain,
)


def _data(row, field):
    if not row:
        return {}
    value = row.get(field, {})
    return value if isinstance(value, dict) else {}


def generate_evidence_report(request_id: str):
    request_row = get_request(request_id)

    if not request_row:
        return None, "Request not found"

    verification_row = get_verification(request_id)
    plan_row = get_deletion_plan(request_id)
    approval_row = get_approval(request_id)
    execution_row = get_execution(request_id)

    verification = _data(verification_row, "verification_data")
    plan = _data(plan_row, "plan_data")
    approval = _data(approval_row, "approval_data")
    execution = _data(execution_row, "execution_data")

    records = plan.get("records", [])
    table_counts = {}

    for record in records:
        table = record.get("table", "unknown")
        table_counts[table] = table_counts.get(table, 0) + 1

    dependent_records = [
        record for record in records
        if record.get("related_record", False)
    ]

    verified = bool(
        verification_row
        and verification_row.get("status") == "verified"
    )

    executed = bool(execution_row)

    audit_events = get_audit_events(request_id)
    integrity = verify_audit_chain()

    if isinstance(integrity, dict):
        integrity_valid = integrity.get("valid", False)
    else:
        integrity_valid = bool(integrity)

    execution_status = (
        execution.get("status", execution_row.get("status"))
        if executed else "not_executed"
    )

    dry_run = (
        execution.get("dry_run", execution_row.get("dry_run", True))
        if executed else True
    )

    report = {
        "report_id": f"REPORT-{str(uuid4())[:8].upper()}",
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "request": {
            "request_id": request_id,
            "request_type": request_row.get("request_type"),
            "status": request_row.get("status"),
            "created_at": request_row.get("created_at"),
        },

        "verification": {
            "verified": verified,
            "message": (
                "Identity verified successfully"
                if verified else "Identity verification not completed"
            ),
        },

        "discovery": {
            "preview_status": plan_row.get("status", "not_generated")
            if plan_row else "not_generated",
            "direct_matching_rows": plan.get("direct_matching_rows", 0),
            "dependent_records": len(dependent_records),
            "total_records_identified": plan.get(
                "total_records_to_delete", len(records)
            ),
            "previewed_records": plan.get("previewed_records", len(records)),
            "records_truncated": plan.get("records_truncated", False),
            "table_wise_records": table_counts,
        },

        "approval": {
            "decision": (
                approval_row.get("decision", "pending")
                if approval_row else "pending"
            ),
            "reviewer_id": (
                approval_row.get("reviewer_id")
                if approval_row else None
            ),
            "reviewer_role": (
                approval_row.get("reviewer_role")
                if approval_row else None
            ),
            "reviewed_at": (
                approval_row.get("reviewed_at")
                if approval_row else None
            ),
        },

        "execution": {
            "execution_id": (
                execution.get("execution_id")
                if executed else None
            ),
            "status": execution_status,
            "dry_run": dry_run,
            "records_validated": execution.get(
                "records_validated", 0
            ),
            "table_wise_validated_records": execution.get(
                "table_counts", {}
            ),
            "executed_at": execution.get("executed_at"),
            "rollback_confirmed": (
                execution_status == "dry_run_rolled_back"
                and dry_run is True
            ),
            "message": execution.get(
                "message", "No execution record found"
            ),
        },

        "audit": {
            "total_events": len(audit_events),
            "integrity": "valid" if integrity_valid else "invalid",
            "actions": [
                event.get("action") for event in audit_events
            ],
            "events": audit_events,
        },
    }

    return report, None