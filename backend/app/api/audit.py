
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_admin

from app.services.audit_logger import (
    record_audit_event,
    get_audit_events,
    verify_audit_chain,
)

router = APIRouter(
    prefix="/audit",
    tags=["Audit Logging"],
)


class AuditEventCreate(BaseModel):
    request_id: str
    action: str = Field(min_length=2, max_length=100)
    details: str = Field(default="", max_length=500)


@router.post("/test-event")
def create_test_audit_event(
    event_data: AuditEventCreate,
    current_user=Depends(require_admin),
):
    event = record_audit_event(
        request_id=event_data.request_id,
        action=event_data.action,
        actor=current_user["email"],
        details=event_data.details,
    )

    return {
        "message": "Audit event recorded",
        "data": event,
    }


@router.get("/events")
def retrieve_audit_events(
    request_id: str = None,
    current_user=Depends(require_admin),
):
    events = get_audit_events(request_id)

    return {
        "total": len(events),
        "events": events,
    }


@router.get("/verify")
def check_audit_integrity(
    current_user=Depends(require_admin),
):
    is_valid = verify_audit_chain()

    return {
        "integrity": "valid" if is_valid else "tampered",
        "verified": is_valid,
    }
