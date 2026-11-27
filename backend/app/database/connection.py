
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_source_connection():
    try:
        connection = psycopg.connect(
            host=os.getenv("SOURCE_HOST"),
            port=os.getenv("SOURCE_PORT", "5432"),
            dbname=os.getenv("SOURCE_DB"),
            user=os.getenv("SOURCE_READER_USER"),
            password=os.getenv("SOURCE_READER_PASSWORD"),
            connect_timeout=5
        )
        return connection

    except psycopg.Error as error:
        raise ConnectionError(
            f"PostgreSQL connection failed: {error}"
        ) from error


def test_source_connection():
    connection = get_source_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), current_user;"
            )
            result = cursor.fetchone()

        return {
            "connected": True,
            "database": result[0],
            "user": result[1]
        }

    finally:
        connection.close()
