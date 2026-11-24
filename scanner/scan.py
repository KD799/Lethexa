import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

from connectors import (
    PostgresConfig, PostgresConnector, S3Config, S3Connector,
    SampleResult, SchemaInfo,
)
from connectors.s3 import is_supported_key
from detectors.column_classifier import classify_column

from .sampling import sample_tables


@dataclass(frozen=True)
class Finding:
    """One PII finding in the data map. No raw values, by design."""
    table: str      # a table name, or s3://bucket/key for a file
    column: str
    category: str
    confidence: float
    reason: str
    sample_size: int
    matched_count: int


def _classify_sample(label: str, sample: SampleResult) -> list[Finding]:
    findings: list[Finding] = []
    for column in sample.columns:
        for f in classify_column(column, sample.column_values(column)):
            findings.append(Finding(
                table=label, column=f.column, category=f.category,
                confidence=f.confidence, reason=f.reason,
                sample_size=f.sample_size, matched_count=f.matched_count,
            ))
    return findings


def scan_database(
    db: PostgresConnector,
    schema: SchemaInfo | None = None,
    sample_size: int = 100,
) -> list[Finding]:
    """Sample every table, classify every column, keep only the findings."""
    schema = schema or db.get_schema()
    findings: list[Finding] = []
    for sample in sample_tables(db, schema, limit=sample_size):
        findings += _classify_sample(sample.table, sample)
        del sample  # drop the raw values before the next table
    return findings


def scan_s3(s3: S3Connector, sample_size: int = 100, max_objects: int = 200) -> list[Finding]:
    """Sample every CSV and JSON file under the prefix and keep only the findings."""
    findings: list[Finding] = []
    for obj in s3.list_objects(max_objects=max_objects):
        if not is_supported_key(obj.key):
            continue
        try:
            sample = s3.sample_object(obj.key, limit=sample_size)
        except ValueError:
            continue  # unreadable or oversized file: skip it, never stop the scan
        findings += _classify_sample(f"s3://{s3.bucket}/{obj.key}", sample)
        del sample
    return findings


def save_data_map(findings: list[Finding], path: str = "data_map.json") -> None:
    Path(path).write_text(json.dumps([asdict(f) for f in findings], indent=2), encoding="utf-8")


def main() -> None:
    load_dotenv()
    with PostgresConnector(PostgresConfig.from_env()) as db:
        schema = db.get_schema()
        findings = scan_database(db, schema)
    total_cols = sum(len(t.columns) for t in schema.tables)
    print(f"Postgres: {len(schema.tables)} tables, {total_cols} columns scanned")

    if os.environ.get("S3_BUCKET"):
        with S3Connector(S3Config.from_env()) as s3:
            findings += scan_s3(s3)
        print(f"S3: bucket {os.environ['S3_BUCKET']} scanned")

    flagged = {(f.table, f.column) for f in findings}
    print(f"{len(flagged)} columns flagged\n")
    for f in sorted(findings, key=lambda f: (f.table, f.column)):
        print(f"  {f.table + '.' + f.column:<48} {f.category:<14} {f.confidence:.2f}")

    save_data_map(findings)
    print("\nSaved data_map.json (findings only, no raw values)")


if __name__ == "__main__":
    main()