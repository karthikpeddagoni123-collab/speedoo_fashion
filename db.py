"""SQLite database setup for Speedoo Fashion.

Schema rules:

- ``owners`` has exactly ONE row, seeded from .env on first run.
- ``products`` has no ``seller_id`` / ``vendor_id`` / ``merchant_id``
  because Speedoo Fashion is a single-owner store.
- ``product_sizes`` holds per-size stock for each product.
- ``customers`` is the customer (buyer) account table.
- ``orders`` and ``order_items`` capture purchases.

The bootstrap function is idempotent — calling it on an existing DB is
a no-op.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
from typing import Any, Iterable

from config import DB_PATH, OWNER_PASSWORD, OWNER_USERNAME
from auth import hash_password


SCHEMA: str = """
CREATE TABLE IF NOT EXISTS owners (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    mobile        TEXT NOT NULL UNIQUE,
    address       TEXT NOT NULL,
    pincode       TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT,
    price       REAL NOT NULL,
    image_file  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_sizes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    size       TEXT NOT NULL,
    stock      INTEGER NOT NULL DEFAULT 0,
    UNIQUE(product_id, size)
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id       INTEGER NOT NULL REFERENCES customers(id),
    total             REAL NOT NULL,
    payment_method    TEXT NOT NULL,
    payment_status    TEXT NOT NULL DEFAULT 'Pending',
    delivery_address  TEXT NOT NULL,
    delivery_pincode  TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Order Placed',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id   INTEGER NOT NULL REFERENCES products(id),
    product_name TEXT NOT NULL,
    size         TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    price        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS wishlist (
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (customer_id, product_id)
);
"""


def get_conn() -> sqlite3.Connection:
    """Return a fresh SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    """Run a SELECT and return all rows."""
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    """Run a SELECT and return one row (or None)."""
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Run an INSERT/UPDATE/DELETE and return the last rowid (or rowcount)."""
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        conn.commit()
        return cur.lastrowid or cur.rowcount


def init_db() -> None:
    """Create the schema (idempotent) and seed the single owner row.

    The seed step is guarded by a COUNT(*) check so it never inserts a
    second row if the table already has one. This is what enforces the
    "exactly one authorized owner" invariant from §1 and §15.
    """
    with get_conn() as conn:
        conn.executescript(SCHEMA)

        # ----- Single-owner seed -----
        existing = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO owners (id, username, password_hash, created_at) "
                "VALUES (1, ?, ?, ?)",
                (
                    OWNER_USERNAME,
                    hash_password(OWNER_PASSWORD),
                    datetime.datetime.now().isoformat(),
                ),
            )
        elif existing > 1:
            # Defensive: never allow more than one owner.
            conn.execute(
                "DELETE FROM owners WHERE id NOT IN ("
                "SELECT id FROM owners ORDER BY id LIMIT 1)"
            )

        conn.commit()


if __name__ == "__main__":  # pragma: no cover
    init_db()
    print("DB initialized at", os.path.abspath(DB_PATH))
