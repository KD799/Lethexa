"""Create the read-only scanning user on the test source database.

Run once after `docker compose up -d`:
    python -m connectors.setup_readonly
"""
import os

import psycopg
from dotenv import load_dotenv
from psycopg import sql


def main() -> None:
    load_dotenv()
    reader = os.environ["SOURCE_READER_USER"]
    password = os.environ["SOURCE_READER_PASSWORD"]
    db = os.environ["SOURCE_DB"]
    r = sql.Identifier(reader)

    with psycopg.connect(
        host=os.environ["SOURCE_HOST"],
        port=os.environ["SOURCE_PORT"],
        dbname=db,
        user=os.environ["SOURCE_ADMIN_USER"],
        password=os.environ["SOURCE_ADMIN_PASSWORD"],
        autocommit=True,
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (reader,)
        ).fetchone()
        verb = "ALTER" if exists else "CREATE"
        conn.execute(
            sql.SQL("{} ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.SQL(verb), r, sql.Literal(password)
            )
        )
        statements = [
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(r),
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), r),
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(r),
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(r),
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}"
            ).format(r),
        ]
        for stmt in statements:
            conn.execute(stmt)
    print(f"Read-only role '{reader}' is ready on database '{db}'.")


if __name__ == "__main__":
    main()