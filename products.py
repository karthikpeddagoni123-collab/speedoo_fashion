from __future__ import annotations

import datetime
import sqlite3
from typing import Any

from db import execute, query, query_one
def list_products(category: str | None = None, search: str | None = None):
    """Return products, optionally filtered by category and search text."""

    sql = """
        SELECT id, name, category, description,
               price, image_file, created_at, updated_at
        FROM products
        WHERE 1=1
    """

    params = []

    if category and category != "All":
        sql += " AND category = ?"
        params.append(category)

    if search:
        like = f"%{search.strip()}%"
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([like, like])

    sql += " ORDER BY created_at DESC"

    rows = query(sql, tuple(params))
    return rows