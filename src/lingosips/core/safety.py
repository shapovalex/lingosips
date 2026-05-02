"""Content safety filter for AI-generated card fields.

MVP implementation: keyword/pattern blocklist only.
No external API, no ML model — adequate safety posture for a single-user
local app where the user controls which AI service is called.
Post-MVP: replace with local content moderation model.
"""

import structlog

logger = structlog.get_logger(__name__)

# MVP keyword blocklist — lowercase for case-insensitive matching
BLOCKED_TERMS: list[str] = [
    # Add words here as needed for MVP
    # Keep this list minimal — false positives break card creation
]


def check_text(text: str) -> tuple[bool, str | None]:
    """Check whether text is safe to display.

    Returns:
        (True, None) if text passes the safety filter
        (False, matched_term) if text contains a blocked term

    Empty text is always safe (returns True, None).
    Matching is case-insensitive.
    """
    if not text:
        return True, None

    lower_text = text.lower()
    for term in BLOCKED_TERMS:
        if term in lower_text:
            logger.warning("safety.blocked_term_detected", term=term)
            return False, term

    return True, None


# ── Image safety ──────────────────────────────────────────────────────────────

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic byte signatures for supported image formats.
# Each entry: (prefix_bytes, secondary_bytes_or_None, secondary_offset_or_None, content_type)
_IMAGE_MAGIC: list[tuple[bytes, bytes | None, int | None, str]] = [
    (b"\x89PNG\r\n\x1a\n", None, None, "image/png"),
    (b"\xff\xd8", None, None, "image/jpeg"),
    (b"GIF87a", None, None, "image/gif"),
    (b"GIF89a", None, None, "image/gif"),
    (b"RIFF", b"WEBP", 8, "image/webp"),
]


def detect_image_content_type(data: bytes) -> str | None:
    """Detect image content-type from magic bytes. Returns None if unrecognized."""
    for prefix, secondary_bytes, secondary_offset, content_type in _IMAGE_MAGIC:
        if data[: len(prefix)] == prefix:
            if secondary_bytes is not None and secondary_offset is not None:
                # Secondary check required (e.g. WebP: RIFF + WEBP at offset 8)
                sec_end = secondary_offset + len(secondary_bytes)
                if data[secondary_offset:sec_end] == secondary_bytes:
                    return content_type
                continue  # Primary prefix matched but secondary check failed
            return content_type
    return None


def check_image(content_type: str, size_bytes: int) -> tuple[bool, str | None]:
    """Check whether image data is safe to display.

    Returns:
        (True, None) if image passes all safety checks
        (False, reason) if image fails any check

    Note: content_type should be detected from magic bytes (not HTTP headers)
    using detect_image_content_type() before calling this function.
    The text keyword/pattern blocklist does NOT apply to image binaries.
    """
    if not content_type.startswith("image/"):
        logger.warning("safety.image_invalid_content_type", content_type=content_type)
        return False, "content-type must be image/*"
    if size_bytes > MAX_IMAGE_SIZE_BYTES:
        logger.warning("safety.image_too_large", size_bytes=size_bytes)
        return False, f"image exceeds 10 MB ({size_bytes} bytes)"
    return True, None
