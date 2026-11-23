"""
Tests for data/generate_synthetic.py and data/values.py

Run from the repo root:
    python -m unittest discover -s data/tests -t . -v
"""

import json
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from data import values as v
from data.generate_synthetic import (
    ALL_LABELS,
    DETECTABLE,
    build_dataset,
    labels_for,
    to_sql,
    write_files,
)
from detectors.column_classifier import classify_column
from detectors.rules import detect, luhn_valid, verhoeff_valid


def column_values(table, column_name):
    index = [c.name for c in table.columns].index(column_name)
    return [row[index] for row in table.rows]


class ValueGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(1)

    def test_phone_is_detected(self):
        for _ in range(200):
            self.assertIn("PHONE", [m.category for m in detect(v.phone(self.rng))])

    def test_pan_is_detected_with_high_confidence(self):
        for _ in range(200):
            match = detect(v.pan(self.rng, "S"))[0]
            self.assertEqual(match.category, "PAN")
            self.assertGreaterEqual(match.confidence, 0.9)

    def test_aadhaar_passes_checksum(self):
        for _ in range(200):
            digits = v.aadhaar(self.rng).replace(" ", "")
            self.assertEqual(len(digits), 12)
            self.assertTrue(verhoeff_valid(digits))

    def test_credit_card_passes_luhn(self):
        for _ in range(200):
            digits = v.credit_card(self.rng).replace(" ", "")
            self.assertEqual(len(digits), 16)
            self.assertTrue(luhn_valid(digits))

    def test_luhn_check_digit_known_value(self):
        self.assertEqual(v.luhn_check_digit("411111111111111"), "1")   # 4111111111111111

    def test_email_uses_reserved_example_domains(self):
        for _ in range(50):
            domain = v.email("priya", "sharma", 1, self.rng).split("@")[1]
            self.assertTrue(domain.startswith("example."))

    def test_ip_addresses_are_documentation_ranges(self):
        for _ in range(50):
            ip = v.ip_address(self.rng)
            self.assertTrue(ip.startswith(("203.0.113.", "198.51.100.", "192.0.2.")))


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = build_dataset()
        cls.by_name = {t.name: t for t in cls.tables}

    def test_has_ten_expected_tables(self):
        self.assertEqual(
            [t.name for t in self.tables],
            ["customers", "addresses", "products", "orders", "order_items",
             "payments", "support_tickets", "delivery_logs", "employees", "app_logs"],
        )

    def test_every_table_has_rows(self):
        for table in self.tables:
            with self.subTest(table=table.name):
                self.assertGreater(len(table.rows), 0)

    def test_rows_match_column_count(self):
        for table in self.tables:
            for row in table.rows:
                self.assertEqual(len(row), len(table.columns), table.name)

    def test_same_seed_gives_same_data(self):
        again = build_dataset()
        self.assertEqual([t.rows for t in self.tables], [t.rows for t in again])

    def test_different_seed_gives_different_data(self):
        other = build_dataset(seed=7)
        self.assertNotEqual(self.by_name["customers"].rows, other[0].rows)

    def test_all_labels_are_valid(self):
        for key, label in labels_for(self.tables).items():
            self.assertIn(label, ALL_LABELS, key)

    def test_customer_email_and_phone_appear_in_other_tables(self):
        """A deletion request must find the same person in several tables."""
        customers = self.by_name["customers"]
        email, mobile = customers.rows[0][2], customers.rows[0][3]
        customer_id = customers.rows[0][0]
        orders_for_customer = [r for r in self.by_name["orders"].rows if r[1] == customer_id]
        tickets_for_customer = [r for r in self.by_name["support_tickets"].rows if r[1] == customer_id]
        # Pick any customer that has an order and a ticket, if the first one doesn't.
        if not orders_for_customer or not tickets_for_customer:
            for row in customers.rows:
                cid = row[0]
                orders_for_customer = [r for r in self.by_name["orders"].rows if r[1] == cid]
                tickets_for_customer = [r for r in self.by_name["support_tickets"].rows if r[1] == cid]
                if orders_for_customer and tickets_for_customer:
                    email, mobile = row[2], row[3]
                    break
        self.assertTrue(orders_for_customer and tickets_for_customer)
        self.assertIn(mobile, [r[5] for r in orders_for_customer])           # orders.shipping_phone
        self.assertIn(email, [r[2] for r in tickets_for_customer])           # support_tickets.contact_email

    def test_detectors_find_real_pii_and_leave_clean_columns_alone(self):
        """The generator and the detectors should agree with the labels."""
        labels = labels_for(self.tables)
        for table in self.tables:
            for column in table.columns:
                label = labels[f"{table.name}.{column.name}"]
                found = {f.category for f in classify_column(column.name, column_values(table, column.name))}
                with self.subTest(column=f"{table.name}.{column.name}", label=label):
                    if label in DETECTABLE:
                        self.assertIn(label, found)
                    else:
                        self.assertEqual(found, set())

    def test_lookalike_columns_are_not_flagged(self):
        """tracking_number and payment_ref look like Aadhaar / card numbers but are not PII."""
        self.assertEqual(classify_column("tracking_number", column_values(self.by_name["delivery_logs"], "tracking_number")), [])
        self.assertEqual(classify_column("payment_ref", column_values(self.by_name["payments"], "payment_ref")), [])


class OutputFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = build_dataset(n_customers=40)

    def test_sql_loads_into_a_database_with_foreign_keys_on(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(to_sql(self.tables))
        for table in self.tables:
            with self.subTest(table=table.name):
                count = connection.execute(f"SELECT COUNT(*) FROM {table.name}").fetchone()[0]
                self.assertEqual(count, len(table.rows))
        connection.close()

    def test_apostrophes_are_escaped(self):
        from data.generate_synthetic import _sql_literal
        self.assertEqual(_sql_literal("O'Neil"), "'O''Neil'")
        self.assertEqual(_sql_literal(None), "NULL")
        self.assertEqual(_sql_literal(12), "12")

    def test_write_files_creates_sql_and_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            write_files(self.tables, Path(folder))
            self.assertTrue((Path(folder) / "synthetic.sql").exists())
            labels = json.loads((Path(folder) / "labels.json").read_text(encoding="utf-8"))
        expected_keys = {f"{t.name}.{c.name}" for t in self.tables for c in t.columns}
        self.assertEqual(set(labels), expected_keys)


if __name__ == "__main__":
    unittest.main()
