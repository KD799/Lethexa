import json
from dataclasses import asdict, dataclass
from pathlib import Path

from connectors import PostgresConfig, PostgresConnector, SchemaInfo
from detectors.column_classifier import classify_column

from .sampling import sample_tables


@dataclass(frozen=True)
class Finding:
    """One PII finding in the data map. No raw values, by design."""
    table: str
    column: str
    category: str
    confidence: float
    reason: str
    sample_size: int
    matched_count: int


def scan_database(
    db: PostgresConnector,
    schema: SchemaInfo | None = None,
    sample_size: int = 100,
) -> list[Finding]:
    """Sample every table, classify every column, keep only the findings."""
    schema = schema or db.get_schema()
    findings: list[Finding] = []
    for sample in sample_tables(db, schema, limit=sample_size):
        for column in sample.columns:
            for f in classify_column(column, sample.column_values(column)):
                findings.append(
                    Finding(
                        table=sample.table,
                        column=f.column,
                        category=f.category,
                        confidence=f.confidence,
                        reason=f.reason,
                        sample_size=f.sample_size,
                        matched_count=f.matched_count,
                    )
                )
        del sample  # drop the raw values before moving to the next table
    return findings


def save_data_map(findings: list[Finding], path: str = "data_map.json") -> None:
    Path(path).write_text(
        json.dumps([asdict(f) for f in findings], indent=2), encoding="utf-8"
    )


def main() -> None:
    with PostgresConnector(PostgresConfig.from_env()) as db:
        schema = db.get_schema()
        findings = scan_database(db, schema)

    total_cols = sum(len(t.columns) for t in schema.tables)
    flagged = {(f.table, f.column) for f in findings}
    print(f"{len(schema.tables)} tables, {total_cols} columns scanned, "
          f"{len(flagged)} columns flagged\n")

    for f in sorted(findings, key=lambda f: (f.table, f.column)):
        print(f"  {f.table}.{f.column:<18} {f.category:<12} {f.confidence:.2f}")

    save_data_map(findings)
    print("\nSaved data_map.json (findings only, no raw values)")


if __name__ == "__main__":
    main()