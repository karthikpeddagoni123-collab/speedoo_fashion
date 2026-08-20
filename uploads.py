from __future__ import annotations

import os
import secrets

from vercel.blob import put

from config import ALLOWED_IMAGE_EXTENSIONS, MAX_UPLOAD_BYTES


# Detect image type from file signature.
_ALLOWED_IMGHDR = {"jpeg", "png", "webp"}


def _detect_image_kind(header: bytes) -> str | None:
    """Return a simple image kind for a small file header."""

    if len(header) >= 8 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"

    if (
        len(header) >= 12
        and header[:4] == b"RIFF"
        and header[8:12] == b"WEBP"
    ):
        return "webp"

    return None


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def is_allowed_extension(filename: str) -> bool:
    """Check whether the file extension is allowed."""

    if not filename:
        return False

    return _ext(filename) in ALLOWED_IMAGE_EXTENSIONS


def validate_image(file_storage) -> tuple[bool, str]:
    """Validate an uploaded image."""

    if file_storage is None or file_storage.filename == "":
        return False, "Please choose an image file to upload."

    if not is_allowed_extension(file_storage.filename):
        return False, (
            "Only .jpg, .jpeg, .png, and .webp images are allowed."
        )

    # Check file size
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    if size <= 0:
        return False, "The uploaded file is empty."

    if size > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES / (1024 * 1024)
        return False, (
            f"Image is too large. Maximum allowed size is {mb:.0f} MB."
        )

    # Check actual image signature
    header = file_storage.read(32)
    file_storage.seek(0)

    kind = _detect_image_kind(header)

    if kind not in _ALLOWED_IMGHDR:
        return False, "The file does not look like a valid image."

    return True, ""


def save_image(file_storage) -> str:
    """
    Validate and upload product image to Vercel Blob.

    Returns the public Blob URL.
    """

    ok, msg = validate_image(file_storage)

    if not ok:
        raise ValueError(msg)

    extension = _ext(file_storage.filename)

    # Create a unique filename.
    filename = (
        f"products/{secrets.token_hex(16)}{extension}"
    )

    # Read the uploaded image.
    file_storage.seek(0)
    image_data = file_storage.read()

    try:
        result = put(
            filename,
            image_data,
            access="public",
            content_type=file_storage.content_type or "application/octet-stream",
        )

        # Vercel Blob returns the public URL.
        return result.url

    except Exception as exc:
        raise ValueError(
            f"Unable to upload image to Vercel Blob: {exc}"
        ) from exc


def delete_image(image_url: str | None) -> None:
    """
    Delete an image from Vercel Blob.

    Deletion is currently skipped because the installed
    Vercel Python SDK does not expose Blob deletion.
    """

    # We intentionally do nothing here for now.
    # The image remains safely stored in Vercel Blob.
    return
