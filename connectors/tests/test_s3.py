import boto3
import pytest

from connectors import S3Config, S3Connector
from connectors.s3 import is_supported_key


def _creds(**extra):
    return dict(access_key_id="test", secret_access_key="test", **extra)


def test_connection_ok(s3):
    assert s3.test_connection().ok


def test_connection_to_missing_bucket_fails(s3):
    with S3Connector(S3Config(bucket="does-not-exist", **_creds())) as other:
        assert not other.test_connection().ok


def test_list_objects_uses_prefix(s3):
    assert {o.key for o in s3.list_objects()} == {
        "data/customers.csv", "data/events.jsonl", "data/notes.txt", "data/empty.csv",
    }
    assert s3.list_objects(prefix="nothing/") == []


def test_sample_csv(s3):
    sample = s3.sample_object("data/customers.csv")
    assert sample.columns == ["name", "email", "phone"]
    assert len(sample.rows) == 2


def test_sample_jsonl(s3):
    sample = s3.sample_object("data/events.jsonl")
    assert sample.columns == ["id", "contact"]
    assert len(sample.rows) == 2


def test_empty_csv_gives_no_columns(s3):
    sample = s3.sample_object("data/empty.csv")
    assert sample.columns == [] and sample.rows == []


def test_unsupported_and_unknown_objects_rejected(s3):
    with pytest.raises(ValueError):
        s3.sample_object("data/notes.txt")
    with pytest.raises(ValueError):
        s3.sample_object("data/missing.csv")


def test_sample_limit_is_capped(s3):
    big = "id,email\n" + "".join(f"{i},user{i}@example.com\n" for i in range(500))
    boto3.client("s3", region_name="us-east-1", aws_access_key_id="test",
                 aws_secret_access_key="test").put_object(
        Bucket="lethexa-test", Key="data/big.csv", Body=big.encode())
    assert len(s3.sample_object("data/big.csv", limit=10_000).rows) <= 100


def test_partial_last_row_is_dropped_when_truncated(s3):
    small = S3Config(bucket="lethexa-test", prefix="data/", **_creds(max_bytes=60))
    with S3Connector(small) as limited:
        assert len(limited.sample_object("data/customers.csv").rows) == 1


def test_reads_do_not_modify_the_bucket(s3):
    before = [(o.key, o.size, o.last_modified) for o in s3.list_objects()]
    for obj in s3.list_objects():
        if is_supported_key(obj.key):
            s3.sample_object(obj.key)
    assert before == [(o.key, o.size, o.last_modified) for o in s3.list_objects()]