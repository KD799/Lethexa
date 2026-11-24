from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .models import ConnectionTestResult, ObjectInfo, SampleResult

MAX_SAMPLE_ROWS = 100
DEFAULT_MAX_BYTES = 1_000_000
SUPPORTED_SUFFIXES = (".csv", ".json", ".jsonl", ".ndjson")


def is_supported_key(key: str) -> bool:
    return key.lower().endswith(SUPPORTED_SUFFIXES)


@dataclass(frozen=True)
class S3Config:
    bucket: str
    region: str = "us-east-1"
    prefix: str = ""
    access_key_id: str | None = None
    secret_access_key: str | None = field(default=None, repr=False)  # never printed
    endpoint_url: str | None = None  # only for a local mock S3
    connect_timeout: int = 5
    max_bytes: int = DEFAULT_MAX_BYTES  # read at most this much of any object

    @classmethod
    def from_env(cls) -> "S3Config":
        load_dotenv()
        return cls(
            bucket=os.environ["S3_BUCKET"],
            region=os.environ.get("S3_REGION", "us-east-1"),
            prefix=os.environ.get("S3_PREFIX", ""),
            access_key_id=os.environ.get("S3_ACCESS_KEY_ID") or None,
            secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY") or None,
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
        )


def _error_code(error) -> str:
    return error.response.get("Error", {}).get("Code", "Unknown")


def _cell(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value)


def _parse_csv(text: str, limit: int) -> tuple[list[str], list[tuple]]:
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return [], []
    columns = [h.strip() for h in header]
    rows: list[tuple] = []
    for row in reader:
        if not row:
            continue
        rows.append(tuple((row + [""] * len(columns))[: len(columns)]))
        if len(rows) >= limit:
            break
    return columns, rows


def _parse_json(text: str, suffix: str, limit: int, truncated: bool) -> tuple[list[str], list[tuple]]:
    records: list = []
    if suffix in (".jsonl", ".ndjson"):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
            if len(records) >= limit:
                break
    else:
        if truncated:
            raise ValueError("JSON file is larger than the sample limit; use .jsonl or raise max_bytes")
        try:
            data = json.loads(text)
        except ValueError:
            raise ValueError("Not valid JSON") from None  # no file content in the message
        records = (data if isinstance(data, list) else [data])[:limit]
    dicts = [r for r in records if isinstance(r, dict)]
    columns = list(dict.fromkeys(k for r in dicts for k in r))
    return columns, [tuple(_cell(r.get(k)) for k in columns) for r in dicts]


class S3Connector:
    """Read-only S3 connector: test, list objects, sample rows from CSV and JSON files.

    Only list and get calls are made. Use an IAM user with s3:ListBucket and
    s3:GetObject and nothing else.
    """

    def __init__(self, config: S3Config):
        self._config = config
        self._client = None

    @property
    def bucket(self) -> str:
        return self._config.bucket

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise RuntimeError("boto3 is not installed: pip install -r requirements-connectors.txt") from None
        c = self._config
        self._client = boto3.client(
            "s3",
            region_name=c.region,
            endpoint_url=c.endpoint_url,
            aws_access_key_id=c.access_key_id,
            aws_secret_access_key=c.secret_access_key,
            config=Config(
                connect_timeout=c.connect_timeout,
                read_timeout=10,
                retries={"max_attempts": 2},
                s3={"addressing_style": "path"} if c.endpoint_url else None,
            ),
        )

    def close(self) -> None:
        self._client = None

    def __enter__(self) -> "S3Connector":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _require_client(self):
        self.connect()
        assert self._client is not None
        return self._client

    def test_connection(self) -> ConnectionTestResult:
        from botocore.exceptions import BotoCoreError, ClientError

        c = self._config
        try:
            client = self._require_client()
            client.head_bucket(Bucket=c.bucket)
            client.list_objects_v2(Bucket=c.bucket, Prefix=c.prefix, MaxKeys=1)
        except ClientError as e:
            return ConnectionTestResult(ok=False, message=f"Connection failed: {_error_code(e)}")
        except BotoCoreError as e:
            return ConnectionTestResult(ok=False, message=f"Connection failed: {type(e).__name__}")
        return ConnectionTestResult(
            ok=True,
            message=("Connected. Read-only cannot be verified from the client side: "
                     "use an IAM user with s3:ListBucket and s3:GetObject only."),
            read_only_verified=False,
        )

    def list_objects(self, prefix: str | None = None, max_objects: int = 1000) -> list[ObjectInfo]:
        client = self._require_client()
        prefix = self._config.prefix if prefix is None else prefix
        found: list[ObjectInfo] = []
        pages = client.get_paginator("list_objects_v2").paginate(
            Bucket=self._config.bucket, Prefix=prefix,
            PaginationConfig={"MaxItems": max_objects},
        )
        for page in pages:
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue
                found.append(ObjectInfo(obj["Key"], obj["Size"], obj.get("LastModified")))
        return found

    def sample_object(self, key: str, limit: int = 50) -> SampleResult:
        """Sample rows from a CSV or JSON file. Rows hold REAL values: memory only, never store them."""
        from botocore.exceptions import ClientError

        if not is_supported_key(key):
            raise ValueError(f"Unsupported file type: {key}")
        limit = max(1, min(int(limit), MAX_SAMPLE_ROWS))
        c = self._config
        client = self._require_client()
        try:
            response = client.get_object(Bucket=c.bucket, Key=key, Range=f"bytes=0-{c.max_bytes - 1}")
            body = response["Body"].read()
        except ClientError as e:
            code = _error_code(e)
            if code in ("NoSuchKey", "404"):
                raise ValueError(f"Unknown object: {key}") from None
            if code == "InvalidRange":  # zero-byte file
                body = b""
            else:
                raise

        text = body.decode("utf-8-sig", errors="replace")
        truncated = len(body) >= c.max_bytes
        if truncated and "\n" in text:
            text = text.rsplit("\n", 1)[0]  # drop the partial last line
        suffix = "." + key.lower().rsplit(".", 1)[-1]
        if suffix == ".csv":
            columns, rows = _parse_csv(text, limit)
        else:
            columns, rows = _parse_json(text, suffix, limit, truncated)
        return SampleResult(table=key, columns=columns, rows=rows)