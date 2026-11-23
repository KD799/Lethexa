from __future__ import annotations

import psycopg
from psycopg import sql

from .config import PostgresConfig
from .models import (
    ColumnInfo, ConnectionTestResult, ForeignKey,
    SampleResult, SchemaInfo, TableInfo,
)

MAX_SAMPLE_ROWS = 100


class PostgresConnector:
    """Read-only PostgreSQL connector: test, schema, sample rows."""

    def __init__(self, config: PostgresConfig):
        self._config = config
        self._conn: psycopg.Connection | None = None

    # ---------- connection ----------
    def connect(self) -> None:
        if self._conn is not None and not self._conn.closed:
            return
        c = self._config
        self._conn = psycopg.connect(
            host=c.host, port=c.port, dbname=c.dbname,
            user=c.user, password=c.password,
            connect_timeout=c.connect_timeout,
            # Defence in depth: the session itself refuses writes,
            # on top of the DB role having SELECT-only grants.
            options=(
                "-c default_transaction_read_only=on "
                f"-c statement_timeout={c.statement_timeout_ms}"
            ),
            autocommit=True,
        )

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None

    def __enter__(self) -> "PostgresConnector":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _require_conn(self) -> psycopg.Connection:
        self.connect()
        assert self._conn is not None
        return self._conn

    # ---------- F-1: test connection ----------
    def test_connection(self, schema: str = "public") -> ConnectionTestResult:
        try:
            conn = self._require_conn()
            version = conn.execute("SHOW server_version").fetchone()[0]
            writable = self.tables_with_write_access(schema)
            is_super = conn.execute(
                "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
            ).fetchone()[0]
            if is_super or writable:
                detail = "superuser" if is_super else f"write access on {writable}"
                return ConnectionTestResult(
                    ok=True,
                    message=f"Connected, but NOT read-only ({detail}). Use a read-only user.",
                    server_version=version,
                    read_only_verified=False,
                )
            return ConnectionTestResult(
                ok=True, message="Connected with a read-only user.",
                server_version=version, read_only_verified=True,
            )
        except psycopg.Error as e:
            return ConnectionTestResult(ok=False, message=f"Connection failed: {e}")

    def tables_with_write_access(self, schema: str = "public") -> list[str]:
        rows = self._require_conn().execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
              AND has_table_privilege(
                    current_user,
                    quote_ident(table_schema) || '.' || quote_ident(table_name),
                    'INSERT,UPDATE,DELETE,TRUNCATE')
            """,
            (schema,),
        ).fetchall()
        return [r[0] for r in rows]

    # ---------- F-3: schema ----------
    def get_schema(self, schema: str = "public") -> SchemaInfo:
        conn = self._require_conn()

        pk = {
            (t, c) for t, c in conn.execute(
                """
                SELECT kcu.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s
                """,
                (schema,),
            ).fetchall()
        }

        est = dict(conn.execute(
            """
            SELECT c.relname, GREATEST(c.reltuples, 0)::bigint
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = %s
            """,
            (schema,),
        ).fetchall())

        columns: dict[str, list[ColumnInfo]] = {}
        for table, col, dtype, nullable in conn.execute(
            """
            SELECT c.table_name, c.column_name, c.data_type, c.is_nullable
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema = %s AND t.table_type = 'BASE TABLE'
            ORDER BY c.table_name, c.ordinal_position
            """,
            (schema,),
        ).fetchall():
            columns.setdefault(table, []).append(
                ColumnInfo(col, dtype, nullable == "YES", (table, col) in pk)
            )

        fks = [
            ForeignKey(*row) for row in conn.execute(
                """
                SELECT c.conname, cl.relname, a.attname, rcl.relname, ra.attname
                FROM pg_constraint c
                JOIN pg_class cl  ON cl.oid  = c.conrelid
                JOIN pg_namespace n ON n.oid = cl.relnamespace
                JOIN pg_class rcl ON rcl.oid = c.confrelid
                CROSS JOIN LATERAL unnest(c.conkey, c.confkey) AS k(attnum, refattnum)
                JOIN pg_attribute a  ON a.attrelid  = c.conrelid  AND a.attnum  = k.attnum
                JOIN pg_attribute ra ON ra.attrelid = c.confrelid AND ra.attnum = k.refattnum
                WHERE c.contype = 'f' AND n.nspname = %s
                ORDER BY cl.relname, c.conname
                """,
                (schema,),
            ).fetchall()
        ]

        tables = [
            TableInfo(name=t, columns=cols, estimated_rows=int(est.get(t, 0)))
            for t, cols in sorted(columns.items())
        ]
        return SchemaInfo(schema=schema, tables=tables, foreign_keys=fks)

    # ---------- F-6: sample rows ----------
    def sample_rows(self, table: str, limit: int = 50, schema: str = "public") -> SampleResult:
        limit = max(1, min(int(limit), MAX_SAMPLE_ROWS))
        conn = self._require_conn()

        # Only allow tables that really exist, so no arbitrary names reach the query.
        exists = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'
            """,
            (schema, table),
        ).fetchone()
        if not exists:
            raise ValueError(f"Unknown table: {schema}.{table}")

        query = sql.SQL("SELECT * FROM {}.{} LIMIT {}").format(
            sql.Identifier(schema), sql.Identifier(table), sql.Literal(limit)
        )
        with conn.cursor() as cur:
            cur.execute(query)
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
        return SampleResult(table=table, columns=cols, rows=rows)