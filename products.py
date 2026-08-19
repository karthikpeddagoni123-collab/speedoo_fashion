"""Product data access for the single-owner store.

There is no ``seller_id`` / ``vendor_id`` / ``merchant_id`` column on
products. Every product in the store belongs to the Speedoo Fashion
owner. The owner is the only role that can use this module's
write functions, enforced at the route level by ``@owner_required``.
"""
from __future__ import annotations

import datetime
from typing import Any, Iterable

from db import execute, query, query_one


# ---------- Reads ----------

def list_products(category: str | None = None, search: str | None = None) -> list[sqlite3.Row]:  # type: ignore[name-defined]
    """Return products, optionally filtered by category and search text."""
    sql = "SELECT * FROM products WHERE 1=1"
    params: list[Any] = []
    if category and category != "All":
        sql += " AND category = ?"
        params.append(category)
    if search:
        like = f"%{search.strip()}%"
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([like, like])
    sql += " ORDER BY created_at DESC"
    return query(sql, params)


def get_product(product_id: int) -> sqlite3.Row | None:  # type: ignore[name-defined]
    return query_one("SELECT * FROM products WHERE id = ?", (product_id,))


def list_sizes(product_id: int) -> list[sqlite3.Row]:  # type: ignore[name-defined]
    return query(
        "SELECT * FROM product_sizes WHERE product_id = ? ORDER BY id",
        (product_id,),
    )


def get_size(product_id: int, size: str) -> sqlite3.Row | None:  # type: ignore[name-defined]
    return query_one(
        "SELECT * FROM product_sizes WHERE product_id = ? AND size = ?",
        (product_id, size),
    )


def total_stock(product_id: int) -> int:
    row = query_one(
        "SELECT COALESCE(SUM(stock), 0) AS total FROM product_sizes WHERE product_id = ?",
        (product_id,),
    )
    return int(row["total"] or 0)


# ---------- Writes (owner-only — routes enforce this) ----------

def create_product(
    name: str,
    category: str,
    price: float,
    description: str,
    image_file: str,
    sizes: list[tuple[str, int]],
) -> int:
    """Insert a product and its size rows. Returns the new product id."""
    now = datetime.datetime.now().isoformat()
    pid = execute(
        "INSERT INTO products (name, category, description, price, image_file, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, category, description, price, image_file, now, now),
    )
    for size, stock in sizes:
        execute(
            "INSERT INTO product_sizes (product_id, size, stock) VALUES (?, ?, ?)",
            (pid, size, stock),
        )
    return pid


def update_product(
    product_id: int,
    *,
    name: str | None = None,
    category: str | None = None,
    description: str | None = None,
    price: float | None = None,
    image_file: str | None = None,
) -> None:
    """Update mutable fields on an existing product."""
    sets = []
    params: list[Any] = []
    for col, val in (
        ("name", name),
        ("category", category),
        ("description", description),
        ("price", price),
        ("image_file", image_file),
    ):
        if val is not None:
            sets.append(f"{col} = ?")
            params.append(val)
    if not sets:
        return
    sets.append("updated_at = ?")
    params.append(datetime.datetime.now().isoformat())
    params.append(product_id)
    execute(
        f"UPDATE products SET {', '.join(sets)} WHERE id = ?",
        params,
    )


def replace_sizes(product_id: int, sizes: list[tuple[str, int]]) -> None:
    """Replace all sizes for a product in one shot."""
    execute("DELETE FROM product_sizes WHERE product_id = ?", (product_id,))
    for size, stock in sizes:
        execute(
            "INSERT INTO product_sizes (product_id, size, stock) VALUES (?, ?, ?)",
            (product_id, size, stock),
        )


def set_size_stock(product_id: int, size: str, stock: int) -> None:
    """Update the stock of a single (product, size) pair."""
    execute(
        "UPDATE product_sizes SET stock = ? WHERE product_id = ? AND size = ?",
        (stock, product_id, size),
    )


def delete_product(product_id: int) -> None:
    """Delete a product and its size rows.

    Order items referencing this product are kept (with product_name
    snapshot) so historical orders remain meaningful.
    """
    execute("DELETE FROM products WHERE id = ?", (product_id,))


# ---------- Wishlist helpers ----------

def add_to_wishlist(customer_id: int, product_id: int) -> None:
    execute(
        "INSERT OR IGNORE INTO wishlist (customer_id, product_id, created_at) "
        "VALUES (?, ?, ?)",
        (customer_id, product_id, datetime.datetime.now().isoformat()),
    )


def remove_from_wishlist(customer_id: int, product_id: int) -> None:
    execute(
        "DELETE FROM wishlist WHERE customer_id = ? AND product_id = ?",
        (customer_id, product_id),
    )


def list_wishlist(customer_id: int) -> list[sqlite3.Row]:  # type: ignore[name-defined]
    return query(
        "SELECT p.* FROM wishlist w JOIN products p ON p.id = w.product_id "
        "WHERE w.customer_id = ? ORDER BY w.created_at DESC",
        (customer_id,),
    )


def in_wishlist(customer_id: int, product_id: int) -> bool:
    return (
        query_one(
            "SELECT 1 FROM wishlist WHERE customer_id = ? AND product_id = ?",
            (customer_id, product_id),
        )
        is not None
    )
