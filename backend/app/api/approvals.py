from fastapi import APIRouter, HTTPException, Depends

from app.schemas.approval import ApprovalSubmit
from app.services.approval import (
    process_approval,
    get_approval
)
from app.core.security import require_admin

router = APIRouter(
    prefix="/approvals",
    tags=["Approval Workflow"]
)


@router.post("/{request_id}")
def submit_approval(
    request_id: str,
    approval_data: ApprovalSubmit,
    current_user=Depends(require_admin)
):

    approval, error = process_approval(
        request_id,
        approval_data,
        current_user
    )

    if error:
        if error == "Request not found":
            status_code = 404
        else:
            status_code = 400

        raise HTTPException(
            status_code=status_code,
            detail=error
        )

    return {
        "message": "Approval decision recorded successfully",
        "data": approval
    }


@router.get("/{request_id}")
def retrieve_approval(
    request_id: str,
    current_user=Depends(require_admin)
):

    approval = get_approval(request_id)

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval record not found"
        )

    return approval