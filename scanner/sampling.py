from typing import Iterator

from connectors import PostgresConnector, SampleResult, SchemaInfo

DEFAULT_SAMPLE_SIZE = 100


def sample_tables(
    db: PostgresConnector,
    schema: SchemaInfo,
    limit: int = DEFAULT_SAMPLE_SIZE,
) -> Iterator[SampleResult]:
    """Yield one SampleResult per table.

    The rows hold REAL values, so they must stay in memory and never be
    printed, logged or stored. The scanner keeps only the findings.
    """
    for table in schema.tables:
        yield db.sample_rows(table.name, limit=limit, schema=schema.schema)


def main() -> None:
    from connectors import PostgresConfig

    from .targets import targets_from_schema

    with PostgresConnector(PostgresConfig.from_env()) as db:
        schema = db.get_schema()
        total_cols = len(targets_from_schema(schema))
        print(f"Sampling {len(schema.tables)} tables ({total_cols} columns)\n")
        for sample in sample_tables(db, schema, limit=20):
            # Counts only, never values.
            print(f"  {sample.table}: {len(sample.rows)} rows, {len(sample.columns)} columns")


if __name__ == "__main__":
    main()