import pytest

from connectors import PostgresConfig, PostgresConnector


@pytest.fixture(scope="module")
def db():
    try:
        connector = PostgresConnector(PostgresConfig.from_env())
        connector.connect()
    except Exception as e:  # DB not running locally or in CI
        pytest.skip(f"Source database not available: {e}")
    yield connector
    connector.close()