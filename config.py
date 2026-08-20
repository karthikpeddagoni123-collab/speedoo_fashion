"""Configuration loaded from .env via python-dotenv."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# ---------- Flask ----------
FLASK_SECRET: str = os.getenv(
    "FLASK_SECRET",
    "change_this_flask_secret"
)

# ---------- Password hashing pepper ----------
SECRET_KEY: str = os.getenv(
    "SECRET_KEY",
    "change_this_app_secret"
)

# ---------- Owner credentials ----------
OWNER_USERNAME: str = os.getenv(
    "OWNER_USERNAME",
    "admin"
)

OWNER_PASSWORD: str = os.getenv(
    "OWNER_PASSWORD",
    "admin123"
)


# ---------- Storage ----------
# Vercel serverless functions cannot use the deployed project
# directory as persistent writable storage.
# ---------- Storage ----------
if os.getenv("VERCEL"):
    DB_PATH: str = os.getenv(
        "DB_PATH",
        "/tmp/speedoo.db"
    )

    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        "/tmp/speedoo_uploads"
    )
else:
    DB_PATH: str = os.getenv(
        "DB_PATH",
        "speedoo.db"
    )

    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        "static/uploads"
    )
# ---------- Constraints ----------
MAX_UPLOAD_BYTES: int = int(
    os.getenv(
        "MAX_UPLOAD_BYTES",
        str(5 * 1024 * 1024)
    )
)


# ---------- Domain constants ----------
CATEGORIES: list[str] = [
    "Shirts",
    "Pants",
    "Casual Wear",
    "Formal Wear",
    "Occasion Wear",
]


ORDER_STATUSES: list[str] = [
    "Order Placed",
    "Payment Confirmed",
    "Processing",
    "Packed",
    "Shipped",
    "Out for Delivery",
    "Delivered",
    "Cancelled",
]


PAYMENT_METHODS: list[str] = [
    "Card",
    "UPI",
    "Cash on Delivery",
]


ALLOWED_IMAGE_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}
