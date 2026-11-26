

from datetime import datetime, timezone
from uuid import uuid4

from psycopg import Error as PostgresError, sql

from app.services.persistence import (
    get_request as get_persisted_request,
    get_verification as get_persisted_verification,
    get_deletion_plan as get_persisted_plan,
    get_approval as get_persisted_approval,
    get_execution as get_persisted_execution,
    save_execution_once,
)

from app.services.audit_logger import record_audit_event
from app.connectors.executor import connect_executor


PRIMARY_KEYS = {
    "order_items": ["item_id"],
    "payments": ["payment_id"],
    "delivery_logs": ["log_id"],
    "addresses": ["address_id"],
    "support_tickets": ["ticket_id"],
    "app_logs": ["log_id"],
    "orders": ["order_id"],
    "customers": ["customer_id"],
}


def _get_json_record(row, field):
    if not row:
        return None
    value = row.get(field)
    return value if isinstance(value, dict) else None


def get_execution(request_id: str):
    persisted = get_persisted_execution(request_id)
    if persisted is None:
        return None
    return _get_json_record(persisted, "execution_data")


def execute_deletion(request_id: str, dry_run: bool = True):

    if dry_run is not True and dry_run is not False:
        return None, "Invalid execution mode"

    conn = None

    try:
        # 1. Request validation
        request_row = get_persisted_request(request_id)

        if not request_row:
            return None, "Request not found"

        request_record = (
            _get_json_record(request_row, "request_data")
            or request_row
        )

        if request_record.get("request_type") != "deletion":
            return None, "Only deletion requests can be executed"

        if request_row.get("status") != "approved":
            return None, "Request must be approved before execution"

        # 2. Identity verification
        verification = get_persisted_verification(request_id)

        if not verification or verification.get("status") != "verified":
            return None, "Identity verification is not complete"

        # 3. Admin approval
        approval_row = get_persisted_approval(request_id)

        if not approval_row:
            return None, "Admin approval record not found"

        approval = (
            _get_json_record(approval_row, "approval_data") or {}
        )

        if approval_row.get("decision") != "approved":
            return None, "An approved admin decision is required"

        reviewer_role = (
            approval_row.get("reviewer_role")
            or approval.get("reviewer_role")
        )

        if reviewer_role != "admin":
            return None, "Approval must come from an administrator"

        reviewer_id = (
            approval_row.get("reviewer_id")
            or approval.get("reviewer_id")
        )

        requester_email = request_row.get("email", "")

        if (
            reviewer_id
            and requester_email
            and str(reviewer_id).strip().lower()
            == str(requester_email).strip().lower()
        ):
            return None, "Requester cannot approve their own deletion"

        # 4. Deletion plan
        plan_row = get_persisted_plan(request_id)

        if not plan_row:
            return None, "Deletion plan not found"

        plan = _get_json_record(plan_row, "plan_data")

        if not plan:
            return None, "Invalid deletion plan"

        if plan_row.get("status") != "preview":
            return None, "A valid deletion preview is required"

        if plan.get("dry_run") is not True:
            return None, "Invalid deletion preview"

        # 5. Duplicate execution protection
                # 5. Duplicate execution protection
        existing_execution = get_persisted_execution(request_id)

        if existing_execution:
            existing_data = (
                _get_json_record(
                    existing_execution,
                    "execution_data"
                ) or {}
            )

            existing_status = existing_execution.get("status")

            if existing_status == "permanently_deleted":
                return None, "Permanent deletion has already been executed."

            if not dry_run and existing_status != "dry_run_rolled_back":
                return None, "A successful dry-run is required."

            if dry_run:
                return None, "A dry-run execution record already exists."

        elif not dry_run:
            return None, "Run a successful dry-run before permanent deletion."
        # 6. Validate records
        records = plan.get("records", [])

        if not isinstance(records, list) or not records:
            return None, "No records available for deletion"

        for record in records:
            if not isinstance(record, dict):
                return None, "Invalid deletion-plan record"

            table = record.get("table")
            reference = record.get("record_reference")
            order = record.get("deletion_order")

            if table not in PRIMARY_KEYS:
                return None, f"Table is not allowed: {table}"

            if not isinstance(reference, dict):
                return None, "Invalid record reference"

            key = PRIMARY_KEYS[table][0]

            if set(reference.keys()) != {key}:
                return None, f"Invalid primary-key reference for {table}"

            if reference[key] is None:
                return None, f"Missing primary key for {table}"

            if (
                isinstance(order, bool)
                or not isinstance(order, int)
                or order < 0
                or record.get("proposed_action") != "DELETE"
            ):
                return None, "Invalid deletion plan"

        # 7. Execute transaction
        conn = connect_executor()
        cursor = conn.cursor()

        ordered_records = sorted(
            records,
            key=lambda item: item["deletion_order"],
        )

        table_counts = {}
        total_records = 0

        try:
            for record in ordered_records:
                table = record["table"]
                key = PRIMARY_KEYS[table][0]
                value = record["record_reference"][key]

                query = sql.SQL(
                    "DELETE FROM public.{} WHERE {} = %s"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(key),
                )

                cursor.execute(query, (value,))

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        f"Expected one row in {table}; "
                        f"found {cursor.rowcount}"
                    )

                table_counts[table] = table_counts.get(table, 0) + 1
                total_records += 1

            if dry_run:
                conn.rollback()
                status = "dry_run_rolled_back"
                message = (
                    "Deletion statements executed successfully "
                    "and rolled back. No records were permanently deleted."
                )
            else:
                conn.commit()
                status = "permanently_deleted"
                message = (
                    "Approved deletion completed and committed successfully."
                )

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()

        execution_record = {
            "execution_id": str(uuid4()),
            "request_id": request_id,
            "status": status,
            "dry_run": dry_run,
            "records_validated": total_records,
            "records_deleted": 0 if dry_run else total_records,
            "table_counts": table_counts,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }

        # 8. Save execution evidence
        saved = save_execution_once(request_id, execution_record)

        if not saved:
            return None, (
                "Execution evidence could not be saved or "
                "an execution record already exists."
            )

        # 9. Audit event
        record_audit_event(
            request_id=request_id,
            action=(
                "DELETION_DRY_RUN_COMPLETED"
                if dry_run else "PERMANENT_DELETION_COMPLETED"
            ),
            actor="deletion-service",
            details=(
                f"{total_records} records processed; "
                f"status={status}"
            ),
        )

        return execution_record, None

    except (ValueError, RuntimeError) as error:
        if conn:
            conn.rollback()
        return None, str(error)

    except PostgresError:
        if conn:
            conn.rollback()
        return None, "Database operation failed. Transaction rolled back."

    except Exception as error:
        if conn:
            conn.rollback()
        return None, f"Execution failed: {str(error)}"

    finally:
        if conn:
            conn.close()
