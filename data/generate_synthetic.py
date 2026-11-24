"""
Lethexa synthetic dataset (Step 3).

Builds a FAKE customer database with 10 tables, writes it as SQL, and writes a
labels file saying which columns really hold PII (the "answer key" we use to
measure detector accuracy in Step 4).

Run from the repo root:
    python -m data.generate_synthetic

It creates:
    data/synthetic.sql   load into PostgreSQL:  psql -d <database> -f data/synthetic.sql
    data/labels.json     ground truth, e.g. {"customers.email": "EMAIL", ...}

The same seed always produces the same data, so the whole team gets an
identical database. No real personal data is used anywhere.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from data import values as v

DEFAULT_SEED = 2026
DEFAULT_CUSTOMERS = 200

# Labels. DETECTABLE ones are what our rule-based detectors can find today.
# OTHER_PII are real personal data that need the NLP classifier (stretch goal).
DETECTABLE = ("EMAIL", "PHONE", "PAN", "AADHAAR", "CREDIT_CARD", "IP_ADDRESS", "DATE_OF_BIRTH")
OTHER_PII = ("NAME", "ADDRESS")
ALL_LABELS = DETECTABLE + OTHER_PII + ("NONE",)

START = date(2023, 1, 1)
END = date(2026, 11, 20)


@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str
    label: str = "NONE"          # what this column REALLY contains
    primary_key: bool = False
    references: str | None = None


@dataclass
class Table:
    name: str
    columns: list[Column]
    rows: list[tuple] = field(default_factory=list)


def _tables() -> dict[str, Table]:
    """Define the 10 tables (structure only), in the order they must be created."""
    C = Column
    defs = [
        Table("customers", [
            C("customer_id", "INTEGER", primary_key=True),
            C("full_name", "TEXT", "NAME"),
            C("email", "TEXT", "EMAIL"),
            C("mobile", "TEXT", "PHONE"),
            C("pan_number", "TEXT", "PAN"),
            C("aadhaar_number", "TEXT", "AADHAAR"),
            C("date_of_birth", "DATE", "DATE_OF_BIRTH"),
            C("city", "TEXT"),
            C("state", "TEXT"),
            C("created_at", "TIMESTAMP"),
        ]),
        Table("addresses", [
            C("address_id", "INTEGER", primary_key=True),
            C("customer_id", "INTEGER", references="customers(customer_id)"),
            C("address_line", "TEXT", "ADDRESS"),
            C("city", "TEXT"),
            C("state", "TEXT"),
            C("pincode", "TEXT"),
        ]),
        Table("products", [
            C("product_id", "INTEGER", primary_key=True),
            C("name", "TEXT"),
            C("sku", "TEXT"),
            C("price", "NUMERIC(10,2)"),
        ]),
        Table("orders", [
            C("order_id", "INTEGER", primary_key=True),
            C("customer_id", "INTEGER", references="customers(customer_id)"),
            C("order_number", "TEXT"),
            C("total_amount", "NUMERIC(10,2)"),
            C("status", "TEXT"),
            C("shipping_phone", "TEXT", "PHONE"),
            C("created_at", "TIMESTAMP"),
        ]),
        Table("order_items", [
            C("item_id", "INTEGER", primary_key=True),
            C("order_id", "INTEGER", references="orders(order_id)"),
            C("product_id", "INTEGER", references="products(product_id)"),
            C("quantity", "INTEGER"),
            C("unit_price", "NUMERIC(10,2)"),
        ]),
        Table("payments", [
            C("payment_id", "INTEGER", primary_key=True),
            C("order_id", "INTEGER", references="orders(order_id)"),
            C("card_number", "TEXT", "CREDIT_CARD"),
            C("payment_ref", "TEXT"),          # 16 random digits: looks like a card but is NOT one
            C("amount", "NUMERIC(10,2)"),
            C("paid_at", "TIMESTAMP"),
        ]),
        Table("support_tickets", [
            C("ticket_id", "INTEGER", primary_key=True),
            C("customer_id", "INTEGER", references="customers(customer_id)"),
            C("contact_email", "TEXT", "EMAIL"),
            C("subject", "TEXT"),
            C("status", "TEXT"),
            C("created_at", "TIMESTAMP"),
        ]),
        Table("delivery_logs", [
            C("log_id", "INTEGER", primary_key=True),
            C("order_id", "INTEGER", references="orders(order_id)"),
            C("recipient_phone", "TEXT", "PHONE"),   # the "old log table" a careless deletion would miss
            C("tracking_number", "TEXT"),            # 12 random digits: looks like Aadhaar but is NOT one
            C("status", "TEXT"),
            C("delivered_at", "TIMESTAMP"),
        ]),
        Table("employees", [
            C("employee_id", "INTEGER", primary_key=True),
            C("full_name", "TEXT", "NAME"),
            C("work_email", "TEXT", "EMAIL"),
            C("phone", "TEXT", "PHONE"),
            C("pan_number", "TEXT", "PAN"),
            C("department", "TEXT"),
            C("joined_on", "DATE"),
        ]),
        Table("app_logs", [
            C("log_id", "INTEGER", primary_key=True),
            C("customer_id", "INTEGER", references="customers(customer_id)"),
            C("action", "TEXT"),
            C("ip_address", "TEXT", "IP_ADDRESS"),
            C("logged_at", "TIMESTAMP"),
        ]),
    ]
    return {t.name: t for t in defs}


PRODUCT_NAMES = [
    "Cotton Kurta", "Running Shoes", "Steel Water Bottle", "Bluetooth Speaker",
    "Notebook Pack", "Backpack", "Desk Lamp", "Phone Cover", "Wireless Mouse",
    "Yoga Mat", "Coffee Beans 500g", "Green Tea Box", "Table Fan", "Cooking Pan",
    "Wall Clock", "Study Chair", "Headphones", "Power Bank", "Bed Sheet", "Umbrella",
]
TICKET_SUBJECTS = ["Order delayed", "Wrong item received", "Refund status",
                   "Change delivery address", "Payment failed", "Product query"]
ORDER_STATUSES = ["Placed", "Shipped", "Delivered", "Cancelled"]
ACTIONS = ["login", "view_product", "add_to_cart", "checkout", "logout"]
DEPARTMENTS = ["Engineering", "Support", "Sales", "Finance", "Operations"]


def build_dataset(seed: int = DEFAULT_SEED, n_customers: int = DEFAULT_CUSTOMERS) -> list[Table]:
    """Create all tables with fake rows. Same seed -> same data."""
    rng = random.Random(seed)
    tables = _tables()

    # --- customers (the same email and phone are reused in other tables on purpose,
    #     so a deletion request has to find them everywhere) --------------------------
    customers = []
    for customer_id in range(1, n_customers + 1):
        first, last = v.person_name(rng)
        city, state = rng.choice(v.CITIES)
        customer = {
            "id": customer_id,
            "email": v.email(first, last, customer_id, rng),
            "mobile": v.phone(rng),
            "city": city,
            "state": state,
        }
        customers.append(customer)
        tables["customers"].rows.append((
            customer_id,
            f"{first} {last}",
            customer["email"],
            customer["mobile"],
            v.pan(rng, last[0]) if rng.random() < 0.6 else None,
            v.aadhaar(rng) if rng.random() < 0.5 else None,
            str(v.random_date(rng, date(1960, 1, 1), date(2005, 12, 31))),
            city,
            state,
            v.random_timestamp(rng, START, END),
        ))

    # --- addresses: 1 or 2 per customer ---------------------------------------------
    address_id = 0
    for c in customers:
        for _ in range(rng.choice([1, 1, 2])):
            address_id += 1
            tables["addresses"].rows.append((
                address_id, c["id"], v.street_address(rng), c["city"], c["state"], v.pincode(rng),
            ))

    # --- products ------------------------------------------------------------------------
    prices = {}
    for product_id, name in enumerate(PRODUCT_NAMES, start=1):
        prices[product_id] = round(rng.uniform(99, 4999), 2)
        tables["products"].rows.append((product_id, name, f"SKU-{product_id:04d}", prices[product_id]))

    # --- orders, items, payments, delivery logs -----------------------------------
    order_id = item_id = payment_id = log_id = 0
    for c in customers:
        for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
            order_id += 1
            created = v.random_timestamp(rng, START, END)
            total = 0.0
            for _ in range(rng.randint(1, 3)):
                item_id += 1
                product_id = rng.randint(1, len(PRODUCT_NAMES))
                quantity = rng.randint(1, 3)
                total += prices[product_id] * quantity
                tables["order_items"].rows.append((item_id, order_id, product_id, quantity, prices[product_id]))
            total = round(total, 2)
            status = rng.choice(ORDER_STATUSES)

            tables["orders"].rows.append((
                order_id, c["id"], f"ORD-{created[:4]}-{order_id:06d}", total, status, c["mobile"], created,
            ))

            payment_id += 1
            tables["payments"].rows.append((
                payment_id, order_id, v.credit_card(rng), v.payment_ref(rng), total, created,
            ))

            log_id += 1
            delivered = status == "Delivered"
            tables["delivery_logs"].rows.append((
                log_id, order_id, c["mobile"], v.tracking_number(rng),
                "Delivered" if delivered else "In transit",
                v.random_timestamp(rng, START, END) if delivered else None,
            ))

    # --- support tickets: about 1 in 3 customers ------------------------------------
    ticket_id = 0
    for c in customers:
        if rng.random() < 0.35:
            ticket_id += 1
            tables["support_tickets"].rows.append((
                ticket_id, c["id"], c["email"], rng.choice(TICKET_SUBJECTS),
                rng.choice(["Open", "Closed"]), v.random_timestamp(rng, START, END),
            ))

    # --- employees (a second source of PII that is NOT customer data) -------------
    for employee_id in range(1, 21):
        first, last = v.person_name(rng)
        tables["employees"].rows.append((
            employee_id, f"{first} {last}", f"{first}.{last}.emp{employee_id}@example.com".lower(),
            v.phone(rng), v.pan(rng, last[0]), rng.choice(DEPARTMENTS),
            str(v.random_date(rng, date(2018, 1, 1), END)),
        ))

    # --- app logs: lots of rows, each with an IP address -------------------------------
    for log_id in range(1, n_customers * 3 + 1):
        tables["app_logs"].rows.append((
            log_id, rng.choice(customers)["id"], rng.choice(ACTIONS), v.ip_address(rng),
            v.random_timestamp(rng, START, END),
        ))

    return list(tables.values())


# ---------------------------------------------------------------------------
# Writing the output files
# ---------------------------------------------------------------------------

def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def create_table_sql(table: Table) -> str:
    lines = []
    for col in table.columns:
        parts = [col.name, col.sql_type]
        if col.primary_key:
            parts.append("PRIMARY KEY")
        if col.references:
            parts.append(f"REFERENCES {col.references}")
        lines.append("    " + " ".join(parts))
    return f"CREATE TABLE {table.name} (\n" + ",\n".join(lines) + "\n);"


def insert_sql(table: Table, batch_size: int = 100) -> list[str]:
    names = ", ".join(c.name for c in table.columns)
    statements = []
    for start in range(0, len(table.rows), batch_size):
        batch = table.rows[start:start + batch_size]
        values = ",\n".join("    (" + ", ".join(_sql_literal(x) for x in row) + ")" for row in batch)
        statements.append(f"INSERT INTO {table.name} ({names}) VALUES\n{values};")
    return statements


def to_sql(tables: list[Table]) -> str:
    parts = ["-- Lethexa SYNTHETIC data. Every value is fake. Generated by data/generate_synthetic.py", ""]
    for table in reversed(tables):                       # drop children before parents
        parts.append(f"DROP TABLE IF EXISTS {table.name};")
    parts.append("")
    for table in tables:                                 # create parents before children
        parts.append(create_table_sql(table))
        parts.append("")
    for table in tables:
        parts.extend(insert_sql(table))
        parts.append("")
    return "\n".join(parts)


def labels_for(tables: list[Table]) -> dict[str, str]:
    return {f"{t.name}.{c.name}": c.label for t in tables for c in t.columns}


def write_files(tables: list[Table], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "synthetic.sql").write_text(to_sql(tables), encoding="utf-8")
    (out_dir / "labels.json").write_text(
        json.dumps(labels_for(tables), indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate Lethexa's synthetic dataset.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args(argv)

    tables = build_dataset(args.seed, args.customers)
    write_files(tables, args.out_dir)

    print(f"Wrote {args.out_dir / 'synthetic.sql'} and {args.out_dir / 'labels.json'}")
    for table in tables:
        print(f"  {table.name:<16}{len(table.rows):>6} rows")


if __name__ == "__main__":
    main()
