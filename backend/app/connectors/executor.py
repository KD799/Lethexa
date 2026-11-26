
import os
import psycopg

from dotenv import load_dotenv


ALLOWED_DELETE_TABLES = {
    "order_items",
    "payments",
    "delivery_logs",
    "addresses",
    "support_tickets",
    "app_logs",
    "orders",
    "customers",
}


def connect_executor():
    load_dotenv()

    database = os.environ.get("SOURCE_DB")
    expected_user = os.environ.get("EXECUTOR_USER")

    if database != "lethexa_source":
        raise RuntimeError(
            "Deletion executor is restricted to lethexa_source."
        )

    if not expected_user:
        raise RuntimeError("EXECUTOR_USER is not configured.")

    conn = psycopg.connect(
        host=os.environ["SOURCE_HOST"],
        port=int(os.environ["SOURCE_PORT"]),
        dbname=database,
        user=expected_user,
        password=os.environ["EXECUTOR_PASSWORD"],
        connect_timeout=5,
        options=(
            "-c statement_timeout=10000 "
            "-c lock_timeout=3000 "
            "-c search_path=public"
        ),
    )

    try:
        identity = conn.execute(
            """
            SELECT
                current_database(),
                current_user,
                r.rolsuper,
                r.rolcreaterole,
                r.rolcreatedb
            FROM pg_roles r
            WHERE r.rolname = current_user
            """
        ).fetchone()

        if identity is None:
            raise RuntimeError("Unable to verify executor identity.")

        db_name, db_user, is_superuser, can_create_role, can_create_db = identity

        if db_name != "lethexa_source":
            raise RuntimeError("Unexpected database connection.")

        if db_user != expected_user:
            raise RuntimeError("Unexpected database executor user.")

        if is_superuser or can_create_role or can_create_db:
            raise RuntimeError("Executor has unsafe elevated privileges.")

        for table in ALLOWED_DELETE_TABLES:
            permissions = conn.execute(
                """
                SELECT
                    has_table_privilege(current_user, %s, 'DELETE'),
                    has_table_privilege(current_user, %s, 'TRUNCATE'),
                    has_table_privilege(current_user, %s, 'INSERT'),
                    has_table_privilege(current_user, %s, 'UPDATE')
                """,
                (
                    f"public.{table}",
                    f"public.{table}",
                    f"public.{table}",
                    f"public.{table}",
                ),
            ).fetchone()

            if permissions is None or not permissions[0]:
                raise RuntimeError(
                    f"Executor lacks DELETE permission on {table}."
                )

            if any(permissions[1:]):
                raise RuntimeError(
                    f"Executor has excessive write permissions on {table}."
                )

        return conn

    except Exception:
        conn.close()
        raise
