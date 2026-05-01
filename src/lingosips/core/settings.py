"""Core settings business logic for lingosips.

No FastAPI imports — pure business logic only.
The API layer (api/settings.py) delegates to these functions.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from lingosips.db.models import Settings

logger = structlog.get_logger(__name__)

# Authoritative language list — mirrored in frontend SUPPORTED_LANGUAGES_FRONTEND constant.
# BCP 47 code → display name.
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese (Simplified)",
    "ko": "Korean",
    "ar": "Arabic",
    "tr": "Turkish",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "cs": "Czech",
    "uk": "Ukrainian",
}

DEFAULT_NATIVE_LANGUAGE = "en"
DEFAULT_TARGET_LANGUAGE = "es"


def validate_language_code(code: str) -> None:
    """Raise ValueError if code is not in SUPPORTED_LANGUAGES.

    Called by the API layer before any DB work to ensure only valid language
    codes are persisted.
    """
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"'{code}' is not a supported language code. "
            f"Supported codes: {', '.join(SUPPORTED_LANGUAGES)}"
        )


async def get_or_create_settings(session: AsyncSession) -> Settings:
    """Return the singleton Settings row, creating defaults on first call.

    Uses select().limit(1) to enforce the singleton pattern. If no row exists,
    inserts a default row and commits so subsequent calls within the same test
    session find the existing row (idempotent per T4.4).

    Uses session.execute() (SQLAlchemy AsyncSession API) — not session.exec()
    which is SQLModel-only.
    """
    result = await session.execute(select(Settings).limit(1))
    settings = result.scalars().first()
    if settings is None:
        settings = Settings(
            native_language=DEFAULT_NATIVE_LANGUAGE,
            active_target_language=DEFAULT_TARGET_LANGUAGE,
            target_languages=f'["{DEFAULT_TARGET_LANGUAGE}"]',
            onboarding_completed=False,
        )
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
        logger.info("settings.created_defaults")
    return settings


async def update_settings(session: AsyncSession, **kwargs: Any) -> Settings:
    """Apply partial updates to the singleton Settings row.

    Only fields present in kwargs are updated; all others remain unchanged.
    Language code validation must be performed by the API layer BEFORE calling
    this function — this function does not validate.
    """
    settings = await get_or_create_settings(session)
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    settings.updated_at = datetime.now(UTC)
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings
