import io
import re

from django.conf import settings
from PIL import Image, UnidentifiedImageError

from .errors import ValidationError

ALLOWED_CARRIER_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/svg+xml",
}
MAX_FILENAME_LENGTH = 240
SVG_SIGNATURE = re.compile(br"^\s*(?:<\?xml[^>]*>\s*)?<svg(?:\s|>)", re.IGNORECASE)


def read_limited(uploaded_file, maximum: int | None = None) -> bytes:
    maximum = maximum or settings.PIXELVAULT_MAX_UPLOAD_BYTES
    chunks = []
    total = 0
    for chunk in uploaded_file.chunks():
        total += len(chunk)
        if total > maximum:
            raise ValidationError("file exceeds the configured upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


def validate_filename(name: str) -> str:
    name = name.replace("\\", "/")
    if not name or len(name) > MAX_FILENAME_LENGTH or name.startswith("/") or "\x00" in name:
        raise ValidationError("invalid filename")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValidationError("invalid filename")
    return "/".join(parts)


def validate_carrier(content: bytes, filename: str, content_type: str | None) -> None:
    validate_filename(filename)
    if content_type not in ALLOWED_CARRIER_TYPES:
        raise ValidationError("unsupported carrier image type")
    if not content:
        raise ValidationError("carrier image is empty")
    if content_type == "image/svg+xml":
        if len(content) > 10 * 1024 * 1024 or not SVG_SIGNATURE.search(content[:4096]):
            raise ValidationError("invalid SVG carrier")
        return
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise ValidationError("carrier image signature is invalid") from error


def validate_payload(name: str, content: bytes) -> None:
    validate_filename(name)
    if not content:
        raise ValidationError(f"file is empty: {name}")
