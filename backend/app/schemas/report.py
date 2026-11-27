
from pydantic import BaseModel
from typing import List, Optional


class ReportRequestInfo(BaseModel):
    request_id: str
    request_type: str
    status: str
    created_at: str


class ReportVerificationInfo(BaseModel):
    verified: bool
    message: str


class ReportApprovalInfo(BaseModel):
    decision: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None


class ReportAuditInfo(BaseModel):
    total_events: int
    integrity: str
    actions: List[str]


class EvidenceReport(BaseModel):
    report_id: str
    generated_at: str
    request: ReportRequestInfo
    verification: ReportVerificationInfo
    approval: ReportApprovalInfo
    audit: ReportAuditInfo
