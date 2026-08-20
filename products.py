from __future__ import annotations

import datetime
import sqlite3
from typing import Any

from db import execute, query, query_one

# ---------- READ ----------

def list_products(category: str | None = None, search: str | None = None):
    sql = "SELECT * FROM products WHERE 1=1"
    params = []

    if category and category != "All":
        sql += " AND category = ?"
        params.append(category)

    if search:
        like = f"%{search.strip()}%"
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([like, like])

    sql += " ORDER BY created_at DESC"
    return query(sql, tuple(params))


def get_product(product_id: int):
    return query_one("SELECT * FROM products WHERE id = ?", (product_id,))


def list_sizes(product_id: int):
    return query(
        "SELECT * FROM product_sizes WHERE product_id = ? ORDER BY id",
        (product_id,),
    )


def get_size(product_id: int, size: str):
    return query_one(
        "SELECT * FROM product_sizes WHERE product_id = ? AND size = ?",
        (product_id, size),
    )


def total_stock(product_id: int):
    row = query_one(
        "SELECT COALESCE(SUM(stock),0) AS total FROM product_sizes WHERE product_id=?",
        (product_id,),
    )
    return int(row["total"] or 0)

# ---------- OWNER WRITE ----------

def create_product(name, category, price, description, image_file, sizes):
    now = datetime.datetime.now().isoformat()

    pid = execute(
        """
        INSERT INTO products
        (name, category, description, price, image_file, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, category, description, price, image_file, now, now),
    )

    for size, stock in sizes:
        execute(
            "INSERT INTO product_sizes (product_id,size,stock) VALUES (?,?,?)",
            (pid, size, stock),
        )

    return pid


def update_product(
    product_id,
    *,
    name=None,
    category=None,
    description=None,
    price=None,
    image_file=None,
):
    sets = []
    params = []

    for col, val in (
        ("name", name),
        ("category", category),
        ("description", description),
        ("price", price),
        ("image_file", image_file),
    ):
        if val is not None:
            sets.append(f"{col}=?")
            params.append(val)

    if not sets:
        return

    sets.append("updated_at=?")
    params.append(datetime.datetime.now().isoformat())
    params.append(product_id)

    execute(
        f"UPDATE products SET {', '.join(sets)} WHERE id=?",
        tuple(params),
    )


def replace_sizes(product_id, sizes):
    execute("DELETE FROM product_sizes WHERE product_id=?", (product_id,))
    for size, stock in sizes:
        execute(
            "INSERT INTO product_sizes (product_id,size,stock) VALUES (?,?,?)",
            (product_id, size, stock),
        )


def set_size_stock(product_id, size, stock):
    execute(
        "UPDATE product_sizes SET stock=? WHERE product_id=? AND size=?",
        (stock, product_id, size),
    )


def delete_product(product_id):
    execute("DELETE FROM products WHERE id=?", (product_id,))

# ---------- WISHLIST ----------

def add_to_wishlist(customer_id, product_id):
    execute(
        """
        INSERT OR IGNORE INTO wishlist
        (customer_id,product_id,created_at)
        VALUES (?,?,?)
        """,
        (customer_id, product_id, datetime.datetime.now().isoformat()),
    )


def remove_from_wishlist(customer_id, product_id):
    execute(
        "DELETE FROM wishlist WHERE customer_id=? AND product_id=?",
        (customer_id, product_id),
    )


def list_wishlist(customer_id):
    return query(
        """
        SELECT p.*
        FROM wishlist w
        JOIN products p ON p.id=w.product_id
        WHERE w.customer_id=?
        ORDER BY w.created_at DESC
        """,
        (customer_id,),
    )


def in_wishlist(customer_id, product_id):
    return (
        query_one(
            "SELECT 1 FROM wishlist WHERE customer_id=? AND product_id=?",
            (customer_id, product_id),
        )
        is not None
    )