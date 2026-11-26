\
from fastapi import APIRouter, HTTPException, Depends

from app.core.security import require_admin

from app.services.report_generator import generate_evidence_report

router = APIRouter(
    prefix="/reports",
    tags=["Evidence Reports"],
)


@router.get("/{request_id}")
def get_evidence_report(
    request_id: str,
    current_user=Depends(require_admin),
):
    report, error = generate_evidence_report(request_id)

    if error:
        raise HTTPException(
            status_code=404,
            detail=error,
        )

    return report
