import pytest

from connectors import PostgresConfig, PostgresConnector

S3_BUCKET = "lethexa-test"
S3_FILES = {
    "data/customers.csv": (
        "name,email,phone\n"
        "Asha,asha@example.com,9876543210\n"
        "Ravi,ravi@example.com,9123456780\n"
    ),
    "data/events.jsonl": (
        '{"id": 1, "contact": "asha@example.com"}\n'
        '{"id": 2, "contact": "ravi@example.com"}\n'
    ),
    "data/notes.txt": "hello",
    "data/empty.csv": "",
}


@pytest.fixture(scope="module")
def db():
    try:
        connector = PostgresConnector(PostgresConfig.from_env())
        connector.connect()
    except Exception as e:  # DB not running locally or in CI
        pytest.skip(f"Source database not available: {e}")
    yield connector
    connector.close()


@pytest.fixture
def s3():
    """Mock S3 (moto) seeded with small files. Skipped if boto3 or moto is missing."""
    pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")
    from moto import mock_aws

    from connectors import S3Config, S3Connector

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1",
                              aws_access_key_id="test", aws_secret_access_key="test")
        client.create_bucket(Bucket=S3_BUCKET)
        for key, body in S3_FILES.items():
            client.put_object(Bucket=S3_BUCKET, Key=key, Body=body.encode())
        config = S3Config(bucket=S3_BUCKET, prefix="data/",
                          access_key_id="test", secret_access_key="test")
        with S3Connector(config) as connector:
            yield connector