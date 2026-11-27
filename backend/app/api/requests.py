
from fastapi import APIRouter, HTTPException, Depends

from app.core.security import require_admin

from app.schemas.request import RequestCreate
from app.services.dsr_engine import (
    create_request,
    get_all_requests,
    get_request_by_id,
)

router = APIRouter(
    prefix="/requests",
    tags=["DSR Requests"],
)


# Public endpoint: users can submit privacy requests.
@router.post("/")
def submit_request(request_data: RequestCreate):
    try:
        new_request = create_request(request_data)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to create DSR request",
        )

    return {
        "message": "DSR request submitted successfully",
        "data": new_request,
    }


# Administrator-only endpoint.
@router.get("/")
def list_requests(
    current_user=Depends(require_admin),
):
    requests = get_all_requests()

    return {
        "total": len(requests),
        "requests": requests,
    }


# Administrator-only endpoint.
@router.get("/{request_id}")
def retrieve_request(
    request_id: str,
    current_user=Depends(require_admin),
):
    try:
        request = get_request_by_id(request_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid request ID",
        )

    if request is None:
        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    return request
