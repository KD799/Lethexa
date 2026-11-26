
import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


# Load Backend/.env
load_dotenv()


def get_app_connection():
    """
    Connect exclusively to the Lethexa application database.

    This database stores DSR workflow information.
    It does not connect to the synthetic customer database.
    """

    database_name = os.getenv("APP_DB_NAME", "lethexa_app")

    # Safety restriction: prevent accidental connection
    # to the synthetic PII source database.
    if database_name != "lethexa_app":
        raise RuntimeError(
            "Invalid application database. "
            "Expected lethexa_app."
        )

    password = os.getenv("APP_DB_PASSWORD")

    if not password:
        raise RuntimeError(
            "APP_DB_PASSWORD is missing from Backend/.env"
        )

    connection = psycopg.connect(
        host=os.getenv("APP_DB_HOST", "localhost"),
        port=int(os.getenv("APP_DB_PORT", "5432")),
        dbname=database_name,
        user=os.getenv("APP_DB_USER", "postgres"),
        password=password,
        connect_timeout=5,
        row_factory=dict_row,
    )

    return connection


def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    Execute a database query with automatic transaction handling.

    Use parameterized queries. Never concatenate user input
    directly into SQL statements.
    """

    with get_app_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or ())

            if fetch_one:
                return cursor.fetchone()

            if fetch_all:
                return cursor.fetchall()

            return cursor.rowcount


def check_app_database():
    """
    Return basic connection information.
    """

    with get_app_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    version() AS database_version;
                """
            )

            return cursor.fetchone()
