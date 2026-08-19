"""Order data access.

Implements customer-order privacy (§12): ``load_order_for`` only returns
orders to the owning customer or the owner; everyone else gets ``None``
and a 403.
"""
from __future__ import annotations

import datetime
from typing import Any

from db import execute, query, query_one


def cart_total(cart: dict[int, dict[str, Any]]) -> float:
    """Total price of a cart (each entry: ``{"price": float, "qty": int}``)."""
    return round(sum(float(v["price"]) * int(v["qty"]) for v in cart.values()), 2)


def place_order(
    customer_id: int,
    cart: dict[int, dict[str, Any]],
    *,
    payment_method: str,
    delivery_address: str,
    delivery_pincode: str,
    payment_status: str = "Confirmed",
) -> int:
    """Persist a new order and decrement stock. Returns the new order id."""
    now = datetime.datetime.now().isoformat()
    total = cart_total(cart)
    order_id = execute(
        "INSERT INTO orders (customer_id, total, payment_method, payment_status, "
        "delivery_address, delivery_pincode, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            customer_id,
            total,
            payment_method,
            payment_status,
            delivery_address,
            delivery_pincode,
            "Order Placed",
            now,
            now,
        ),
    )

    for pid, item in cart.items():
        execute(
            "INSERT INTO order_items "
            "(order_id, product_id, product_name, size, quantity, price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                order_id,
                pid,
                item["name"],
                item["size"],
                int(item["qty"]),
                float(item["price"]),
            ),
        )
        # Decrement stock
        execute(
            "UPDATE product_sizes SET stock = stock - ? "
            "WHERE product_id = ? AND size = ?",
            (int(item["qty"]), pid, item["size"]),
        )
    return order_id


# ---------- Reads ----------

def list_orders_for_customer(customer_id: int) -> list[sqlite3.Row]:  # type: ignore[name-defined]
    return query(
        "SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC",
        (customer_id,),
    )


def list_all_orders() -> list[sqlite3.Row]:  # type: ignore[name-defined]
    return query("SELECT * FROM orders ORDER BY created_at DESC")


def get_order(order_id: int) -> sqlite3.Row | None:  # type: ignore[name-defined]
    return query_one("SELECT * FROM orders WHERE id = ?", (order_id,))


def get_order_items(order_id: int) -> list[sqlite3.Row]:  # type: ignore[name-defined]
    return query(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id",
        (order_id,),
    )


def get_order_for(order_id: int, *, role: str, customer_id: int | None) -> sqlite3.Row | None:  # type: ignore[name-defined]
    """Privacy-checked fetch.

    - Owner can load any order.
    - Customers can only load their own orders. Anyone else gets None
      and the route should respond 403.
    """
    order = get_order(order_id)
    if order is None:
        return None
    if role == "owner":
        return order
    if role == "customer" and customer_id is not None and order["customer_id"] == customer_id:
        return order
    return None


def customer_for_order(order: sqlite3.Row) -> sqlite3.Row | None:  # type: ignore[name-defined]
    return query_one("SELECT * FROM customers WHERE id = ?", (order["customer_id"],))


def list_customers() -> list[sqlite3.Row]:  # type: ignore[name-defined]
    return query("SELECT * FROM customers ORDER BY created_at DESC")


def update_order_status(order_id: int, status: str) -> None:
    """Owner updates the delivery status of one order."""
    execute(
        "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.datetime.now().isoformat(), order_id),
    )
