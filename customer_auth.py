"""Customer signup / login + profile management."""
from __future__ import annotations

import datetime
import re
import sqlite3

from typing import Optional

from auth import hash_password, verify_password
from db import execute, query, query_one


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_MOBILE_RE = re.compile(r"^\d{10}$")
_PIN_RE = re.compile(r"^\d{6}$")


def _validate_signup(data: dict) -> tuple[bool, str]:
    for k in (
        "full_name", "username", "email", "mobile", "address", "pincode",
        "password", "confirm",
    ):
        if not str(data.get(k, "")).strip():
            return False, f"{k.replace('_', ' ').title()} is required."

    if not _EMAIL_RE.match(data["email"].strip()):
        return False, "Please enter a valid email address."
    if not _MOBILE_RE.match(data["mobile"].strip()):
        return False, "Mobile number must be exactly 10 digits."
    if not _PIN_RE.match(data["pincode"].strip()):
        return False, "Pincode must be exactly 6 digits."
    if len(data["password"]) < 6:
        return False, "Password must be at least 6 characters long."
    if data["password"] != data["confirm"]:
        return False, "Passwords do not match."
    return True, ""


def register_customer(data: dict) -> tuple[bool, str, Optional[sqlite3.Row]]:
    """Create a customer account. Returns (ok, message, row)."""
    ok, msg = _validate_signup(data)
    if not ok:
        return False, msg, None

    try:
        cid = execute(
            "INSERT INTO customers "
            "(full_name, username, email, mobile, address, pincode, "
            "password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["full_name"].strip(),
                data["username"].strip().lower(),
                data["email"].strip().lower(),
                data["mobile"].strip(),
                data["address"].strip(),
                data["pincode"].strip(),
                hash_password(data["password"]),
                datetime.datetime.now().isoformat(),
            ),
        )
    except sqlite3.IntegrityError:
        return False, "That username, email or mobile number is already registered.", None

    row = query_one("SELECT * FROM customers WHERE id = ?", (cid,))
    return True, "Account created.", row


def authenticate_customer(identifier: str, password: str) -> Optional[sqlite3.Row]:
    """Login by username OR email + password."""
    row = query_one(
        "SELECT * FROM customers WHERE username = ? OR email = ? LIMIT 1",
        (identifier.strip().lower(), identifier.strip().lower()),
    )
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return row


def get_customer(customer_id: int) -> Optional[sqlite3.Row]:
    return query_one("SELECT * FROM customers WHERE id = ?", (customer_id,))


def update_customer_address(customer_id: int, address: str, pincode: str) -> None:
    execute(
        "UPDATE customers SET address = ?, pincode = ? WHERE id = ?",
        (address.strip(), pincode.strip(), customer_id),
    )


def customer_orders_count(customer_id: int) -> int:
    return len(query("SELECT id FROM orders WHERE customer_id = ?", (customer_id,)))



