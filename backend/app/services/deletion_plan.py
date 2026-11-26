
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg import Error as PostgresError

from app.services.dsr_engine import (
    requests_store,
    get_request_by_id,
)

from app.services.audit_logger import record_audit_event

from app.services.persistence import (
    save_deletion_plan,
    get_deletion_plan as get_persisted_deletion_plan,
    update_request_status,
)


# ==========================================
# BACKEND LATEST CONFIGURATION
# ==========================================

LATEST_BACKEND = Path(__file__).resolve().parents[3] / "Backend_latest"

if str(LATEST_BACKEND) not in sys.path:
    sys.path.insert(0, str(LATEST_BACKEND))

load_dotenv(LATEST_BACKEND / ".env", override=True)


from connectors.config import PostgresConfig
from connectors.postgres import PostgresConnector
from connectors.executor import connect_executor
from connectors.dependency import expand_deletion_records

from scanner.scan import scan_database
from scanner.locate import locate_subject


# Temporary cache.
# PostgreSQL stores the permanent deletion previews.
deletion_plans_store = {}

MAX_DIRECT_KEYS = 5000


# ==========================================
# GENERATE DELETION PREVIEW
# ==========================================

def generate_deletion_plan(request_id: str):
    """
    Generate a dependency-aware deletion preview.

    This function:
    1. Retrieves the DSR request.
    2. Scans the synthetic database using read-only access.
    3. Locates matching PII records.
    4. Expands foreign-key dependencies.
    5. Saves the preview in PostgreSQL.

    No permanent deletion occurs here.
    """

    # Step 1: Retrieve request from PostgreSQL.
    request_record = get_request_by_id(request_id)

    if request_record is None:
        return None, "Request not found"

    if request_record.get("request_type") != "deletion":
        return None, "Only deletion requests can generate a preview"

    if request_record.get("status") not in ("verified", "located"):
        return None, "Identity verification is required first"

    direct_records = []

    try:

        # ======================================
        # STEP 2: LOCATE DIRECT MATCHES
        # ======================================

        # Use the read-only database account.
        with PostgresConnector(PostgresConfig.from_env()) as db:

            findings = scan_database(db)

            result = locate_subject(
                db=db,
                findings=findings,
                identifier=request_record["email"],
                category="EMAIL",
                max_keys=MAX_DIRECT_KEYS,
            )

            for match in result.matches:

                for key in match.keys:

                    reference = {
                        column: value
                        for column, value in zip(
                            match.key_columns,
                            key,
                        )
                    }

                    direct_records.append({
                        "table": match.table,
                        "record_reference": reference,
                    })

        # ======================================
        # STEP 3: REMOVE DUPLICATE REFERENCES
        # ======================================

        unique_records = {}

        for record in direct_records:

            key = (
                record["table"],
                tuple(
                    sorted(
                        record["record_reference"].items()
                    )
                ),
            )

            unique_records[key] = record

        direct_records = list(unique_records.values())

        if not direct_records:
            return None, (
                "No matching records were found for this request"
            )

        # ======================================
        # STEP 4: CHECK SCANNER SAFETY LIMIT
        # ======================================

        if any(
            len(match.keys) >= MAX_DIRECT_KEYS
            for match in result.matches
        ):
            return None, (
                "The number of matching records reached the safety limit. "
                "The preview was not created because it may be incomplete."
            )

        # ======================================
        # STEP 5: EXPAND FK DEPENDENCIES
        # ======================================

        # The executor account only has restricted
        # key-reading and DELETE permissions.
        # No permanent deletion is performed here.

        conn = connect_executor()

        try:

            expanded_records = expand_deletion_records(
                conn,
                direct_records,
            )

        finally:

            conn.rollback()
            conn.close()

        if not expanded_records:
            return None, (
                "Dependency discovery returned no records"
            )

        # ======================================
        # STEP 6: BUILD DELETION PREVIEW
        # ======================================

        preview_records = []

        for record in expanded_records:

            preview_records.append({
                "system": "PostgreSQL",
                "table": record["table"],
                "record_reference": record["record_reference"],
                "related_record": record["related_record"],
                "deletion_order": record["deletion_order"],
                "proposed_action": "DELETE",
            })

        deletion_plan = {
            "request_id": request_id,
            "status": "preview",
            "direct_matching_rows": result.total_rows,
            "total_records_to_delete": len(preview_records),
            "previewed_records": len(preview_records),
            "records_truncated": False,
            "records": preview_records,
            "dry_run": True,
            "message": (
                "Dependency-aware preview generated. "
                "No database records have been deleted."
            ),
        }

        # ======================================
        # STEP 7: SAVE PREVIEW TO POSTGRESQL
        # ======================================

        # PostgreSQL save happens before updating
        # the temporary cache.

        save_deletion_plan(
            request_id,
            deletion_plan,
        )

        # Refresh temporary cache.
        deletion_plans_store[request_id] = deletion_plan

        # ======================================
        # STEP 8: UPDATE REQUEST STATUS
        # ======================================

        # Persist the status change.
        update_request_status(
            request_id,
            "located",
        )

        # Update local request cache.
        request_record["status"] = "located"
        requests_store[request_id] = request_record

        # ======================================
        # STEP 9: AUDIT LOGGING
        # ======================================

        record_audit_event(
            request_id=request_id,
            action="PII_RECORDS_LOCATED",
            actor="locator-service",
            details=(
                f"Located {result.total_rows} direct matching rows "
                f"across {result.columns_searched} flagged columns"
            ),
        )

        record_audit_event(
            request_id=request_id,
            action="DELETION_PREVIEW_CREATED",
            actor="deletion-service",
            details=(
                f"Dependency-aware preview contains "
                f"{len(preview_records)} record references"
            ),
        )

        return deletion_plan, None

    except (ValueError, RuntimeError) as error:

        return None, str(error)

    except PostgresError:

        return None, (
            "A PostgreSQL operation failed while generating the preview"
        )


# ==========================================
# RETRIEVE DELETION PREVIEW
# ==========================================

def get_deletion_plan(request_id: str):
    """
    Retrieve a deletion preview from PostgreSQL.

    This allows the preview to remain available
    after a FastAPI restart.
    """

    persisted_record = get_persisted_deletion_plan(request_id)

    if persisted_record is None:
        deletion_plans_store.pop(request_id, None)
        return None

    deletion_plan = persisted_record.get("plan_data")

    if deletion_plan is None:
        return None

    # Refresh temporary cache.
    deletion_plans_store[request_id] = deletion_plan

    return deletion_plan
