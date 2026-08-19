"""Image upload validation for owner product photos (§8).

Only the owner can upload product images, and only these types are
permitted::

    .jpg  .jpeg  .png  .webp

Anything else (including executables renamed with one of those
extensions) is rejected before reaching disk.
"""
from __future__ import annotations

import os
import secrets

from flask import current_app

from config import ALLOWED_IMAGE_EXTENSIONS, MAX_UPLOAD_BYTES


# Detect image type from file signature instead of the removed stdlib imghdr.
_ALLOWED_IMGHDR = {"jpeg", "png", "webp"}


def _detect_image_kind(header: bytes) -> str | None:
    """Return a simple image kind for a small file header."""
    if len(header) >= 8 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def _upload_dir() -> str:
    d = current_app.config.get("UPLOAD_DIR", "static/uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def is_allowed_extension(filename: str) -> bool:
    """True iff the file name's extension is in the whitelist."""
    if not filename:
        return False
    return _ext(filename) in ALLOWED_IMAGE_EXTENSIONS


def validate_image(file_storage) -> tuple[bool, str]:
    """Validate a Werkzeug ``FileStorage`` object.

    Returns ``(ok, message)``. On error, ``ok=False`` and ``message`` is
    a human-readable reason.
    """
    if file_storage is None or file_storage.filename == "":
        return False, "Please choose an image file to upload."

    if not is_allowed_extension(file_storage.filename):
        return False, (
            "Only .jpg, .jpeg, .png, and .webp images are allowed."
        )

    # ---- Size check ----
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size <= 0:
        return False, "The uploaded file is empty."
    if size > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES / (1024 * 1024)
        return False, f"Image is too large. Maximum allowed size is {mb:.0f} MB."

    # ---- Signature sniff ----
    header = file_storage.read(32)
    file_storage.seek(0)
    kind = _detect_image_kind(header)
    if kind not in _ALLOWED_IMGHDR:
        return False, "The file does not look like a valid image."

    return True, ""


def save_image(file_storage) -> str:
    """Validate and persist a product image, returning the stored file name.

    The on-disk filename is a random hex token; the original filename is
    discarded to prevent path traversal.
    """
    ok, msg = validate_image(file_storage)
    if not ok:
        raise ValueError(msg)

    extension = _ext(file_storage.filename)
    stored = secrets.token_hex(16) + extension
    path = os.path.join(_upload_dir(), stored)

    file_storage.save(path)
    return stored


def delete_image(filename: str | None) -> None:
    """Best-effort delete of an uploaded image. Errors are swallowed."""
    if not filename:
        return
    path = os.path.join(_upload_dir(), filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
