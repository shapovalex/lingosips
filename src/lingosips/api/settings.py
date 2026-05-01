"""FastAPI router for GET /settings and PUT /settings.

Delegates all business logic to lingosips.core.settings.
No business logic lives here — routers only validate input, call core, and
return shaped responses.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import settings as core_settings
from lingosips.db.session import get_session

router = APIRouter()


class SettingsResponse(BaseModel):
    id: int
    native_language: str
    target_languages: str  # JSON string: '["es"]'
    active_target_language: str
    auto_generate_audio: bool
    auto_generate_images: bool
    default_practice_mode: str
    cards_per_session: int
    onboarding_completed: bool


class SettingsUpdateRequest(BaseModel):
    native_language: str | None = None
    active_target_language: str | None = None
    onboarding_completed: bool | None = None
    auto_generate_audio: bool | None = None
    auto_generate_images: bool | None = None
    default_practice_mode: str | None = None
    cards_per_session: int | None = Field(default=None, ge=1, le=100)


@router.get("", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Return the singleton Settings row, creating defaults if none exists."""
    s = await core_settings.get_or_create_settings(session)
    return SettingsResponse.model_validate(s, from_attributes=True)


def _raise_invalid_language(code: str) -> None:
    """Raise a 422 RFC 7807 Problem Detail for an unsupported language code.

    Extracted to eliminate duplicate try/except blocks in the PUT handler.
    Called only after validate_language_code raises ValueError.
    """
    raise HTTPException(
        status_code=422,
        detail={
            "type": "/errors/invalid-language",
            "title": "Invalid language code",
            "detail": f"'{code}' is not a supported language code.",
            "status": 422,
        },
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Partially update the singleton Settings row.

    Validates language codes before any DB work.
    Returns RFC 7807 Problem Detail on invalid language code (422).
    """
    # Validate language codes before any DB work
    if body.native_language is not None:
        try:
            core_settings.validate_language_code(body.native_language)
        except ValueError:
            _raise_invalid_language(body.native_language)
    if body.active_target_language is not None:
        try:
            core_settings.validate_language_code(body.active_target_language)
        except ValueError:
            _raise_invalid_language(body.active_target_language)
    # Exclude None fields — partial update semantics.
    # Note: False and 0 are NOT None, so boolean flags (e.g. onboarding_completed=False)
    # are correctly included. Only truly-absent optional fields (None) are excluded.
    updates = body.model_dump(exclude_none=True)
    s = await core_settings.update_settings(session, **updates)
    return SettingsResponse.model_validate(s, from_attributes=True)
