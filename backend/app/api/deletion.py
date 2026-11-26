
from fastapi import APIRouter, HTTPException, Depends

from app.core.security import require_admin

from app.services.deletion_plan import (
    generate_deletion_plan,
    get_deletion_plan,
)

from app.services.deletion_execution import (
    execute_deletion,
    get_execution,
)

router = APIRouter(
    prefix="/deletion",
    tags=["Deletion Plan"],
)


@router.post("/{request_id}/preview")
def create_deletion_preview(
    request_id: str,
    current_user=Depends(require_admin),
):
    plan, error = generate_deletion_plan(request_id)

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {
        "message": "Deletion preview generated",
        "data": plan,
    }


@router.get("/{request_id}/preview")
def retrieve_deletion_preview(
    request_id: str,
    current_user=Depends(require_admin),
):
    plan = get_deletion_plan(request_id)

    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Deletion plan not found",
        )

    return plan


@router.post("/{request_id}/execute")
def run_deletion(
    request_id: str,
    dry_run: bool = True,
    current_user=Depends(require_admin),
):
    if dry_run is not True:
        raise HTTPException(
            status_code=400,
            detail="Use the permanent deletion endpoint for permanent deletion.",
        )

    result, error = execute_deletion(request_id, dry_run=True)

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {
        "message": "Dry-run completed",
        "data": result,
    }


@router.post("/{request_id}/execute-permanent")
def run_permanent_deletion(
    request_id: str,
    confirm_permanent: bool = False,
    current_user=Depends(require_admin),
):
    if confirm_permanent is not True:
        raise HTTPException(
            status_code=400,
            detail="Explicit permanent deletion confirmation is required.",
        )

    result, error = execute_deletion(
        request_id=request_id,
        dry_run=False,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {
        "message": "Permanent deletion completed",
        "data": result,
    }


@router.get("/{request_id}/execution")
def retrieve_execution(
    request_id: str,
    current_user=Depends(require_admin),
):
    result = get_execution(request_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Execution record not found",
        )

    return result
