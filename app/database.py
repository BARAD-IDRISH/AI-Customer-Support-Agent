
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "support.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db():
    """Create tables and safely migrate existing databases."""

    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                delivered_at TEXT,
                expected_delivery TEXT,
                amount REAL NOT NULL CHECK (amount >= 0),
                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                order_id TEXT,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id),
                FOREIGN KEY (order_id)
                    REFERENCES orders(order_id)
            );
        """)

        # Migration: add the idempotency key to existing databases.
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(tickets)"
            ).fetchall()
        }

        if "request_id" not in columns:
            conn.execute(
                "ALTER TABLE tickets ADD COLUMN request_id TEXT"
            )

        # Existing tickets retain NULL request IDs.
        # Non-NULL request IDs must be unique.
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_tickets_request_id
            ON tickets(request_id)
            WHERE request_id IS NOT NULL
        """)

        conn.executemany(
            """
            INSERT OR IGNORE INTO customers
                (customer_id, name, email)
            VALUES (?, ?, ?)
            """,
            [
                ("CUST1001", "Maya Patel", "maya@example.com"),
                ("CUST1002", "Arjun Shah", "arjun@example.com"),
            ],
        )

        conn.executemany(
            """
            INSERT OR IGNORE INTO orders (
                order_id, customer_id, product_name,
                order_date, status, delivered_at,
                expected_delivery, amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "ORD1001", "CUST1001",
                    "Wireless Headphones", "2026-10-06",
                    "shipped", None, "2026-10-14", 2499.00
                ),
                (
                    "ORD1002", "CUST1002",
                    "Laptop", "2026-09-20",
                    "delivered", "2026-09-25", None, 52999.00
                ),
                (
                    "ORD1003", "CUST1001",
                    "Desk Lamp", "2026-08-10",
                    "delivered", "2026-08-15", None, 1299.00
                ),
            ],
        )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")
