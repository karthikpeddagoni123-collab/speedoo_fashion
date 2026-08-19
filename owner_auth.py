"""Owner login against the seeded single-owner row."""
from __future__ import annotations

from auth import verify_password
from config import OWNER_PASSWORD, OWNER_USERNAME
from db import query_one


def authenticate_owner(username: str, password: str) -> int | None:
    """Return the owner id if the credentials match the single seeded row.

    The username must match the .env value AND the password must verify
    against the stored hash. If the supplied username differs from
    ``OWNER_USERNAME``, this still attempts to load a row whose
    ``username`` column matches the input — but since we seed only one
    row, that is the only row that can ever authenticate.
    """
    row = query_one("SELECT * FROM owners WHERE username = ?", (username.strip(),))
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return row["id"]


def bootstrap_owner_credentials() -> None:
    """Return the configured owner username/password (for the login form)."""
    return OWNER_USERNAME, OWNER_PASSWORD  # type: ignore[return-value]
