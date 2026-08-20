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