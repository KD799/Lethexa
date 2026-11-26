
import secrets
import hmac
import hashlib

from datetime import datetime, timedelta, timezone

from app.core.config import JWT_SECRET

from app.services.dsr_engine import get_request_by_id
from app.services.audit_logger import record_audit_event

from app.services.persistence import (
    save_verification,
    get_verification,
    record_verification_attempt,
    set_verification_status,
    update_request_status,
)
from app.services.email_service import (
    send_otp_email,
    EmailDeliveryError,
)

OTP_EXPIRY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
MAX_OTP_RESENDS_PER_HOUR = 3


def _hash_otp(code: str) -> str:
    return hmac.new(
        JWT_SECRET.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_otp(request_id: str):
    request_record = get_request_by_id(request_id)

    if request_record is None:
        raise ValueError("Request not found")

    if request_record.get("status") != "received":
        raise ValueError("Request is not eligible for verification")

    existing = get_verification(request_id)
    existing_data = (
        existing.get("verification_data", {})
        if existing else {}
    )

    now = datetime.now(timezone.utc)

    if existing and existing.get("status") == "verified":
        raise ValueError("Request is already verified")

    if existing and existing.get("status") == "pending":
        last_sent = existing_data.get("last_sent_at")

        if last_sent:
            last_sent_at = datetime.fromisoformat(
                last_sent.replace("Z", "+00:00")
            )

            if (now - last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
                raise ValueError("Please wait before requesting another OTP")

            created_at = existing_data.get("created_at")
            resend_count = existing_data.get("resend_count", 0)

            if created_at:
                created = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                )

                if now - created < timedelta(hours=1):
                    if resend_count >= MAX_OTP_RESENDS_PER_HOUR:
                        raise ValueError("Maximum OTP resend limit reached")

    code = str(secrets.randbelow(900000) + 100000)
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

    created_at = existing_data.get("created_at", now.isoformat())
    resend_count = existing_data.get("resend_count", 0)

    if existing and existing.get("status") == "pending":
        resend_count += 1
    else:
        resend_count = 0
        created_at = now.isoformat()

    verification_data = {
        "otp_hash": _hash_otp(code),
        "created_at": created_at,
        "last_sent_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
        "resend_count": resend_count,
    }

    save_verification(
        request_id,
        {
            "status": "pending",
            **verification_data,
        },
    )
    try:
        send_otp_email(
            request_record["email"],
            code,
        )
    except EmailDeliveryError:
        set_verification_status(
            request_id,
            "delivery_failed",
        )
        raise
    # Return the code internally for a future email/SMS delivery service.
    # Never expose this value through an API response.
    return True


def verify_otp(request_id: str, submitted_code: str):
    request_record = get_request_by_id(request_id)

    if request_record is None:
        return False, "Request not found"

    verification = get_verification(request_id)

    if not verification:
        return False, "No active verification session. Start verification again."

    if verification.get("status") == "verified":
        return False, "Request is already verified"

    if verification.get("status") != "pending":
        return False, "Verification session is no longer active"

    verification_data = verification.get("verification_data", {})

    expires_at = datetime.fromisoformat(
        verification_data["expires_at"].replace("Z", "+00:00")
    )

    if datetime.now(timezone.utc) > expires_at:
        set_verification_status(request_id, "expired")
        return False, "OTP has expired. Generate a new OTP."

    attempt_record = record_verification_attempt(request_id)

    if attempt_record is None:
        latest = get_verification(request_id)

        if latest and latest.get("status") == "pending":
            latest_data = latest.get("verification_data", {})

            if latest_data.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
                set_verification_status(request_id, "locked")
                return False, "Maximum verification attempts exceeded"

        return False, "Verification session expired or is no longer active"

    updated_data = attempt_record["verification_data"]

    submitted_hash = _hash_otp(str(submitted_code).strip())

    if not hmac.compare_digest(
        submitted_hash,
        updated_data["otp_hash"],
    ):
        if updated_data.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
            set_verification_status(request_id, "locked")
            return False, "Maximum verification attempts exceeded"

        return False, "Invalid OTP"

    updated_data["verified_at"] = datetime.now(timezone.utc).isoformat()
    updated_data.pop("otp_hash", None)

    updated = set_verification_status(
        request_id,
        "verified",
        updated_data,
    )

    if updated == 0:
        return False, "Verification session is no longer active"

    update_request_status(request_id, "verified")

    record_audit_event(
        request_id=request_id,
        action="IDENTITY_VERIFIED",
        actor="system",
        details="Identity verification completed successfully",
    )

    return True, "Identity verified successfully"


def get_verification_status(request_id: str):
    record = get_verification(request_id)

    if not record:
        return None

    data = record.get("verification_data", {})

    # Never expose the OTP hash or internal verification secrets.
    safe_data = {
        key: value
        for key, value in data.items()
        if key not in ("otp_hash",)
    }

    return {
        "request_id": str(request_id),
        "status": record.get("status"),
        "verification_data": safe_data,
    }
