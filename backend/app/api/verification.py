
from fastapi import APIRouter, HTTPException
from app.services.email_service import EmailDeliveryError
from app.schemas.verification import VerificationSubmit

from app.services.verification import (
    generate_otp,
    verify_otp,
    get_verification_status,
)

from app.services.dsr_engine import get_request_by_id


router = APIRouter(
    prefix="/verification",
    tags=["Identity Verification"],
)


@router.post("/{request_id}/start")
def start_verification(request_id: str):
    request_record = get_request_by_id(request_id)

    if request_record is None:
        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    try:
        generate_otp(request_id)

    except EmailDeliveryError:
        raise HTTPException(
            status_code=503,
            detail="Unable to deliver verification email. Please try again later.",
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )
    return {
        "message": "Verification code sent to the registered email address",
        "request_id": request_id,
        "expires_in_minutes": 5,
    }

@router.post("/{request_id}/verify")
def submit_verification(
    request_id: str,
    verification_data: VerificationSubmit,
):
    request_record = get_request_by_id(request_id)

    if request_record is None:
        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    success, message = verify_otp(
        request_id,
        verification_data.code,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=message,
        )

    return {
        "message": message,
        "request_id": request_id,
        "status": "verified",
    }
