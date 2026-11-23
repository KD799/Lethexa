from dataclasses import dataclass

from connectors import PostgresConfig, PostgresConnector, SchemaInfo


@dataclass(frozen=True)
class ScanTarget:
    """One column the scanner will check. Holds names only, never values."""
    table: str
    column: str
    data_type: str
    is_primary_key: bool


def targets_from_schema(schema: SchemaInfo) -> list[ScanTarget]:
    return [
        ScanTarget(t.name, c.name, c.data_type, c.is_primary_key)
        for t in schema.tables
        for c in t.columns
    ]


def main() -> None:
    with PostgresConnector(PostgresConfig.from_env()) as db:
        schema = db.get_schema()
    targets = targets_from_schema(schema)
    print(f"{len(schema.tables)} tables, {len(targets)} columns to scan\n")
    for t in targets:
        pk = " (PK)" if t.is_primary_key else ""
        print(f"  {t.table}.{t.column}: {t.data_type}{pk}")


if __name__ == "__main__":
    main()