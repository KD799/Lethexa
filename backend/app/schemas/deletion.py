
from fastapi import APIRouter, HTTPException

from app.services.deletion_plan import (
    generate_deletion_plan,
    get_deletion_plan
)

router = APIRouter(
    prefix="/deletion",
    tags=["Deletion Plan"]
)


@router.post("/{request_id}/preview")
def create_deletion_preview(request_id: str):

    plan, error = generate_deletion_plan(request_id)

    if error:
        status_code = 404 if error == "Request not found" else 400

        raise HTTPException(
            status_code=status_code,
            detail=error
        )

    return {
        "message": "Deletion preview generated successfully",
        "data": plan
    }


@router.get("/{request_id}/preview")
def retrieve_deletion_preview(request_id: str):

    plan = get_deletion_plan(request_id)

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Deletion plan not found"
        )

    return plan
