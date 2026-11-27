
import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()


def get_app_connection():
    """
    Connect exclusively to the Lethexa application database.
    """

    database_name = os.getenv("APP_DB_NAME", "lethexa_app")

    if database_name != "lethexa_app":
        raise RuntimeError(
            "Invalid application database. Expected lethexa_app."
        )

    password = os.getenv("APP_DB_PASSWORD")

    if not password:
        raise RuntimeError("APP_DB_PASSWORD is missing from Backend/.env")

    return psycopg.connect(
        host=os.getenv("APP_DB_HOST", "localhost"),
        port=int(os.getenv("APP_DB_PORT", "5432")),
        dbname=database_name,
        user=os.getenv("APP_DB_USER", "postgres"),
        password=password,
        connect_timeout=5,
        row_factory=dict_row,
    )


def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    with get_app_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or ())

            if fetch_one:
                return cursor.fetchone()

            if fetch_all:
                return cursor.fetchall()

            return cursor.rowcount


def check_app_database():
    with get_app_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    version() AS database_version;
            """)
            return cursor.fetchone()
