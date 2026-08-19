"""Authorization decorators.

These are the **only** line of defense between a customer and an
owner-only resource (per §5 and §6 of the spec):

    * ``@owner_required`` -> owner login for anonymous callers, 403 for customers.
    * ``@customer_required`` -> redirect to /login if not a logged-in customer.

Never rely on hiding buttons in the HTML. The server enforces it.
"""
from __future__ import annotations

from functools import wraps

from flask import abort, redirect, request, session, url_for


def _is_owner() -> bool:
    return session.get("role") == "owner" and session.get("owner_id") is not None


def _is_customer() -> bool:
    return session.get("role") == "customer" and session.get("user_id") is not None


def owner_required(view):
    """Require the single authorized owner for an owner-only resource."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _is_owner():
            if _is_customer():
                abort(403)
            return redirect(url_for("owner.owner_login"))
        return view(*args, **kwargs)

    return wrapped


def customer_required(view):
    """Require a logged-in customer. Otherwise redirect to /login."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _is_customer():
            next_url = request.path if request.method == "GET" else None
            return redirect(url_for("customer_login", next=next_url))
        return view(*args, **kwargs)

    return wrapped
