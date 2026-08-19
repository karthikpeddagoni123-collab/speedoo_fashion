"""Password hashing helpers for Speedoo Fashion.

The owner password and customer passwords are hashed the same way:

    sha256( salt + password + SECRET_KEY )

The salt is a 16-byte hex string; the stored value is the concatenation
of the hex digest and the salt so a column has all it needs to verify.
"""
from __future__ import annotations

import hashlib
import os
import secrets

from config import SECRET_KEY


def _pepper() -> str:
    """Return the configured app pepper (falls back to a constant)."""
    return os.getenv("SECRET_KEY", SECRET_KEY)


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password and return ``<sha256><16-char salt>``."""
    if salt is None:
        salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + password + _pepper()).encode()).hexdigest()
    return digest + salt


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of a password against the stored value."""
    if not stored or len(stored) < 16:
        return False
    salt = stored[-16:]
    expected = stored[:-16]
    candidate = hashlib.sha256((salt + password + _pepper()).encode()).hexdigest()
    return secrets.compare_digest(expected, candidate)
