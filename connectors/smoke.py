from . import PostgresConfig, PostgresConnector


def main() -> None:
    with PostgresConnector(PostgresConfig.from_env()) as db:
        print(db.test_connection())
        schema = db.get_schema()
        print(f"\n{len(schema.tables)} tables, {len(schema.foreign_keys)} foreign keys")
        for t in schema.tables[:5]:
            print(f"  {t.name}: {[c.name for c in t.columns]}")
        first = schema.tables[0].name
        sample = db.sample_rows(first, limit=3)
        print(f"\nSample of {first}: {sample.columns}")
        for row in sample.rows:
            print("  ", row)  # synthetic data only


if __name__ == "__main__":
    main()