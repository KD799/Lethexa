import psycopg
import pytest


def test_connection_is_read_only(db):
    result = db.test_connection()
    assert result.ok
    assert result.read_only_verified


def test_schema_has_tables_and_columns(db):
    schema = db.get_schema()
    assert len(schema.tables) > 0
    assert all(t.columns for t in schema.tables)


def test_sample_rows_respects_limit(db):
    table = db.get_schema().tables[0].name
    sample = db.sample_rows(table, limit=3)
    assert len(sample.rows) <= 3
    assert sample.columns


def test_sample_limit_is_capped(db):
    table = db.get_schema().tables[0].name
    assert len(db.sample_rows(table, limit=10_000).rows) <= 100


def test_unknown_table_rejected(db):
    with pytest.raises(ValueError):
        db.sample_rows("does_not_exist")


def test_injection_style_table_name_rejected(db):
    with pytest.raises(ValueError):
        db.sample_rows("users; DROP TABLE users;--")


def test_writes_are_blocked(db):
    table = db.get_schema().tables[0].name
    conn = db._require_conn()
    with pytest.raises(psycopg.Error):
        conn.execute(f'DELETE FROM public."{table}" WHERE false')
def test_primary_keys_are_visible_to_read_only_user(db):
    customers = next(t for t in db.get_schema().tables if t.name == "customers")
    assert "customer_id" in [c.name for c in customers.columns if c.is_primary_key]


def test_find_rows_rejects_unknown_column(db):
    with pytest.raises(ValueError):
        db.find_rows("customers", "no_such_column", "x")


def test_find_rows_rejects_injection_style_column(db):
    with pytest.raises(ValueError):
        db.find_rows("customers", 'email"; DROP TABLE customers;--', "x")


def test_find_rows_rejects_unknown_mode(db):
    with pytest.raises(ValueError):
        db.find_rows("customers", "email", "x", mode="regex")