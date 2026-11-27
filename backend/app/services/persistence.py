
import json
from uuid import UUID
from datetime import datetime
from psycopg.types.json import Jsonb

from app.database import get_app_connection


def _uuid(value):
    """Normalize an identifier into a PostgreSQL UUID."""
    return str(UUID(str(value)))


def _json(value):
    """Convert Python data into JSONB safely."""
    return Jsonb(value, dumps=lambda obj: json.dumps(obj, default=str))


def _fetch_one(query, params=()):
    with get_app_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def _fetch_all(query, params=()):
    with get_app_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


def _execute(query, params=()):
    with get_app_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount


# ==========================================
# 1. DSR REQUESTS
# ==========================================

def save_request(request_id, record):
    query = """
        INSERT INTO dsr_requests (
            request_id, full_name, email,
            request_type, status, created_at, request_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (request_id)
        DO UPDATE SET
            full_name = EXCLUDED.full_name,
            email = EXCLUDED.email,
            request_type = EXCLUDED.request_type,
            status = EXCLUDED.status,
            request_data = EXCLUDED.request_data;
    """

    return _execute(query, (
        _uuid(request_id),
        record.get("full_name", ""),
        record.get("email", ""),
        record.get("request_type", "deletion"),
        record.get("status", "pending"),
        record.get("created_at"),
        _json(record),
    ))


def get_request(request_id):
    return _fetch_one(
        """
        SELECT *
        FROM dsr_requests
        WHERE request_id = %s;
        """,
        (_uuid(request_id),),
    )


def update_request_status(request_id, status):
    return _execute(
        """
        UPDATE dsr_requests
        SET status = %s
        WHERE request_id = %s;
        """,
        (status, _uuid(request_id)),
    )


# ==========================================
# 2. IDENTITY VERIFICATION
# ==========================================

def save_verification(request_id, record):
    query = """
        INSERT INTO dsr_verifications (
            request_id, status, verification_data, updated_at
        )
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (request_id)
        DO UPDATE SET
            status = EXCLUDED.status,
            verification_data = EXCLUDED.verification_data,
            updated_at = NOW();
    """

    return _execute(query, (
        _uuid(request_id),
        record.get("status", "pending"),
        _json(record),
    ))


def get_verification(request_id):
    return _fetch_one(
        """
        SELECT *
        FROM dsr_verifications
        WHERE request_id = %s;
        """,
        (_uuid(request_id),),
    )


# ==========================================
# 3. DELETION PLANS
# ==========================================

def save_deletion_plan(request_id, plan):
    query = """
        INSERT INTO dsr_deletion_plans (
            request_id, status, plan_data
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (request_id)
        DO UPDATE SET
            status = EXCLUDED.status,
            plan_data = EXCLUDED.plan_data,
            created_at = NOW();
    """

    return _execute(query, (
        _uuid(request_id),
        plan.get("status", "preview"),
        _json(plan),
    ))


def get_deletion_plan(request_id):
    return _fetch_one(
        """
        SELECT *
        FROM dsr_deletion_plans
        WHERE request_id = %s;
        """,
        (_uuid(request_id),),
    )


# ==========================================
# 4. ADMIN APPROVALS
# ==========================================

def save_approval(request_id, approval):
    query = """
        INSERT INTO dsr_approvals (
            request_id, decision, reviewer_id,
            reviewer_role, approval_data, reviewed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (request_id)
        DO UPDATE SET
            decision = EXCLUDED.decision,
            reviewer_id = EXCLUDED.reviewer_id,
            reviewer_role = EXCLUDED.reviewer_role,
            approval_data = EXCLUDED.approval_data,
            reviewed_at = EXCLUDED.reviewed_at;
    """

    return _execute(query, (
        _uuid(request_id),
        approval.get("decision", "pending"),
        approval.get("reviewer_id", "unknown"),
        approval.get("reviewer_role"),
        _json(approval),
        approval.get("reviewed_at"),
    ))


def get_approval(request_id):
    return _fetch_one(
        """
        SELECT *
        FROM dsr_approvals
        WHERE request_id = %s;
        """,
        (_uuid(request_id),),
    )


# ==========================================
# 5. DELETION EXECUTIONS
# ==========================================

def save_execution_once(request_id, execution):
    """
    Allow one successful dry-run followed by one permanent execution.
    Prevent duplicate dry-runs and duplicate permanent executions.
    """

    query = """
        INSERT INTO dsr_executions (
            execution_id,
            request_id,
            status,
            dry_run,
            execution_data,
            executed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s);
    """

    status = execution.get("status")
    dry_run = execution.get("dry_run")

    if status not in ("dry_run_rolled_back", "permanently_deleted"):
        return False

    if dry_run is not (status == "dry_run_rolled_back"):
        return False

    executed_at = execution.get("executed_at")

    if isinstance(executed_at, str):
        executed_at = datetime.fromisoformat(
            executed_at.replace("Z", "+00:00")
        )

    with get_app_connection() as conn:
        with conn.cursor() as cursor:

            # Lock the parent request to prevent concurrent executions.
            cursor.execute(
                """
                SELECT request_id
                FROM dsr_requests
                WHERE request_id = %s
                FOR UPDATE;
                """,
                (_uuid(request_id),),
            )

            if cursor.fetchone() is None:
                return False

            cursor.execute(
                """
                SELECT status, dry_run
                FROM dsr_executions
                WHERE request_id = %s;
                """,
                (_uuid(request_id),),
            )

            existing_records = cursor.fetchall()

            has_dry_run = any(
                row["status"] == "dry_run_rolled_back"
                and row["dry_run"] is True
                for row in existing_records
            )

            has_permanent = any(
                row["status"] == "permanently_deleted"
                and row["dry_run"] is False
                for row in existing_records
            )

            if dry_run:
                if existing_records:
                    return False
            else:
                if not has_dry_run or has_permanent:
                    return False

            cursor.execute(
                query,
                (
                    _uuid(execution["execution_id"]),
                    _uuid(request_id),
                    status,
                    dry_run,
                    _json(execution),
                    executed_at,
                ),
            )

            return cursor.rowcount == 1


def get_execution(request_id):
    return _fetch_one(
        """
        SELECT *
        FROM dsr_executions
        WHERE request_id = %s
        ORDER BY executed_at DESC
        LIMIT 1;
        """,
        (_uuid(request_id),),
    )


# ==========================================
# 6. AUDIT EVENTS
# ==========================================

def save_audit_event(event):
    query = """
        INSERT INTO dsr_audit_events (
            event_id,
            request_id,
            action,
            actor,
            details,
            event_timestamp,
            previous_hash,
            event_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id) DO NOTHING;
    """

    return _execute(query, (
        _uuid(event["event_id"]),
        _uuid(event["request_id"]),
        event["action"],
        event.get("actor"),
        _json(event.get("details", {})),
        event.get("timestamp"),
        event.get("previous_hash"),
        event["event_hash"],
    ))


def get_persisted_audit_events(request_id=None):

    if request_id is not None:
        return _fetch_all(
            """
            SELECT *
            FROM dsr_audit_events
            WHERE request_id = %s
            ORDER BY event_timestamp ASC, event_id ASC;
            """,
            (_uuid(request_id),),
        )

    return _fetch_all(
        """
        SELECT *
        FROM dsr_audit_events
        ORDER BY event_timestamp ASC, event_id ASC;
        """
    )

def record_verification_attempt(request_id: str):
    """Increment OTP attempts and return the updated verification record."""
    record = get_verification(request_id)

    if not record or record.get("status") != "pending":
        return None

    verification_data = record.get("verification_data", {})
    attempts = int(verification_data.get("attempts", 0))

    if attempts >= 5:
        return None

    verification_data["attempts"] = attempts + 1

    save_verification(
        request_id,
        {
            "status": "pending",
            **verification_data,
        },
    )

    return get_verification(request_id)



def set_verification_status(
    request_id: str,
    status: str,
    verification_data: dict | None = None,
):
    """Update verification status and optionally its stored data."""
    record = get_verification(request_id)

    if not record:
        return 0

    current_data = record.get("verification_data", {})

    if verification_data is not None:
        current_data = verification_data

    # Ensure the requested status cannot be overwritten by old JSON data.
    updated_record = {
        **current_data,
        "status": status,
    }

    save_verification(request_id, updated_record)

    return 1