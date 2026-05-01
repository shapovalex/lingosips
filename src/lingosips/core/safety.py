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
