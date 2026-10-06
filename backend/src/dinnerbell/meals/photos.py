"""Household meal photos: re-encoded as WebP, resized, metadata stripped (ADR 0020).

Re-encoding is the privacy step: a phone's photo carries EXIF (often the GPS position of the
kitchen), and WebP written without `exif=` keeps none of it. The camera's rotation is applied
first, so nothing depends on the orientation tag that gets dropped.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from dinnerbell.core.errors import AppError

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
FULL_SIDE = 1600
THUMB_SIDE = 400
QUALITY = 82


@dataclass(frozen=True, slots=True)
class Encoded:
    webp: bytes
    thumb: bytes
    width: int
    height: int


def encode(data: bytes) -> Encoded:
    try:
        with Image.open(io.BytesIO(data)) as original:
            original.load()
            upright = ImageOps.exif_transpose(original)
            image = upright.convert("RGB")
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        raise AppError(
            422, "photo_unreadable", "That photo couldn't be read. Try a different one."
        ) from None
    image.thumbnail((FULL_SIDE, FULL_SIDE), Image.Resampling.LANCZOS)
    thumb = image.copy()
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
    return Encoded(_webp(image), _webp(thumb), image.width, image.height)


def _webp(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="WEBP", quality=QUALITY, method=4)
    return out.getvalue()
