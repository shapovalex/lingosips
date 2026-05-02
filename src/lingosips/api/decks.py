"""FastAPI router for deck CRUD — /decks endpoints.

Router only — no business logic. Delegates to core.decks.*().
All error handling converts ValueError from core into RFC 7807 HTTPException.
"""

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import decks as core_decks
from lingosips.core import settings as core_settings
from lingosips.db.session import get_session

router = APIRouter()


class DeckResponse(BaseModel):
    """Full deck response — returned by all deck endpoints."""

    id: int
    name: str
    target_language: str
    card_count: int
    due_card_count: int
    settings_overrides: dict | None = None  # deck-level defaults (None = use system defaults)
    created_at: datetime
    updated_at: datetime


class DeckCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_language: str | None = None  # defaults to active_target_language if omitted


_VALID_OVERRIDE_KEYS = frozenset(
    {"auto_generate_audio", "auto_generate_images", "default_practice_mode", "cards_per_session"}
)
_VALID_PRACTICE_MODES = frozenset({"self_assess", "write", "speak"})


class DeckUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    settings_overrides: dict | None = None  # deck-level defaults override

    @field_validator("settings_overrides")
    @classmethod
    def validate_override_keys(cls, v: dict | None) -> dict | None:
        """Reject unknown keys and invalid value types in settings_overrides."""
        if v is None:
            return v
        invalid = set(v.keys()) - _VALID_OVERRIDE_KEYS
        if invalid:
            raise ValueError(
                f"Invalid settings_overrides keys: {invalid}. Allowed: {_VALID_OVERRIDE_KEYS}"
            )
        # Validate value types for each known key
        if "auto_generate_audio" in v and not isinstance(v["auto_generate_audio"], bool):
            raise ValueError("auto_generate_audio must be a boolean")
        if "auto_generate_images" in v and not isinstance(v["auto_generate_images"], bool):
            raise ValueError("auto_generate_images must be a boolean")
        if "default_practice_mode" in v:
            if v["default_practice_mode"] not in _VALID_PRACTICE_MODES:
                raise ValueError(f"default_practice_mode must be one of: {_VALID_PRACTICE_MODES}")
        if "cards_per_session" in v:
            val = v["cards_per_session"]
            if not isinstance(val, int) or isinstance(val, bool):
                raise ValueError("cards_per_session must be an integer")
            if not (1 <= val <= 100):
                raise ValueError("cards_per_session must be between 1 and 100")
        return v


def _parse_deck_overrides(raw: str | None) -> dict | None:
    """Safe JSON parse for Deck.settings_overrides — never raises.

    Deck.settings_overrides is stored as a JSON string in SQLite.
    Returns None on malformed data rather than crashing.
    """
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _deck_row_to_response(row: dict) -> DeckResponse:
    """Convert a dict from list_decks() to DeckResponse.

    Row keys: 'deck' (ORM object), 'card_count', 'due_card_count'.
    """
    deck = row["deck"]
    return DeckResponse(
        id=deck.id,
        name=deck.name,
        target_language=deck.target_language,
        card_count=row["card_count"],
        due_card_count=row["due_card_count"],
        settings_overrides=_parse_deck_overrides(deck.settings_overrides),
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


def _deck_to_response(deck, card_count: int = 0, due_card_count: int = 0) -> DeckResponse:
    """Convert a Deck ORM instance to DeckResponse — used by create/patch endpoints."""
    return DeckResponse(
        id=deck.id,
        name=deck.name,
        target_language=deck.target_language,
        card_count=card_count,
        due_card_count=due_card_count,
        settings_overrides=_parse_deck_overrides(deck.settings_overrides),
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


@router.get("/{deck_id}", response_model=DeckResponse)
async def get_deck(
    deck_id: int,
    session: AsyncSession = Depends(get_session),
) -> DeckResponse:
    """Fetch a single deck by ID with card and due counts.

    Returns 404 if deck not found.
    """
    try:
        row = await core_decks.get_deck_with_counts(deck_id, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/deck-not-found",
                "title": "Deck not found",
                "status": 404,
                "detail": f"Deck {deck_id} does not exist",
            },
        )
    return _deck_row_to_response(row)


@router.get("", response_model=list[DeckResponse])
async def list_decks(
    target_language: str = Query(
        ...,
        min_length=2,
        max_length=10,
        description="BCP 47 language code — required",
    ),
    session: AsyncSession = Depends(get_session),
) -> list[DeckResponse]:
    """List all decks for a target language, with card and due counts.

    target_language is required (422 if absent) — no concept of all languages at once.
    Returns [] when no decks exist — never null.
    """
    rows = await core_decks.list_decks(session, target_language)
    return [_deck_row_to_response(r) for r in rows]


@router.post("", response_model=DeckResponse, status_code=201)
async def create_deck(
    request: DeckCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> DeckResponse:
    """Create a new deck. Defaults target_language to active_target_language if omitted.

    Returns 409 Conflict (RFC 7807) if a deck with the same name already exists
    for the same target language.
    """
    target_language = request.target_language
    if target_language is None:
        settings = await core_settings.get_or_create_settings(session)
        target_language = settings.active_target_language

    name = request.name.strip()
    try:
        deck = await core_decks.create_deck(name, target_language, session)
    except ValueError as exc:
        if "conflict" in str(exc):
            raise HTTPException(
                status_code=409,
                detail={
                    "type": "/errors/deck-name-conflict",
                    "title": "Deck name already exists",
                    "status": 409,
                    "detail": (
                        f"A deck named '{name}' already exists for language '{target_language}'"
                    ),
                },
            )
        raise
    return _deck_to_response(deck)


@router.get("/{deck_id}/export")
async def export_deck(
    deck_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Export a deck as a .lingosips ZIP archive (deck.json + audio/ folder).

    Returns the ZIP as a streaming download with Content-Disposition attachment header.
    Returns 404 if deck not found.
    """
    try:
        zip_bytes, deck_name = await core_decks.export_deck_to_zip(deck_id, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/deck-not-found",
                "title": "Deck not found",
                "status": 404,
                "detail": f"Deck {deck_id} does not exist",
            },
        )
    safe_name = re.sub(r"[^\w\-. ]", "_", deck_name).strip()
    return StreamingResponse(
        zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.lingosips"'},
    )


@router.patch("/{deck_id}", response_model=DeckResponse)
async def patch_deck(
    deck_id: int,
    request: DeckUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> DeckResponse:
    """Rename a deck. Only fields present in the request body are changed.

    Returns 404 if deck not found, 409 if new name conflicts with existing deck.
    """
    update_data: dict = {}
    if "name" in request.model_fields_set and request.name is not None:
        update_data["name"] = request.name.strip()
    if "settings_overrides" in request.model_fields_set:
        # None is a valid explicit value (clears overrides) — use model_fields_set not None check
        update_data["settings_overrides"] = request.settings_overrides

    try:
        deck = await core_decks.update_deck(deck_id, update_data, session)
    except ValueError as exc:
        if "conflict" in str(exc):
            raise HTTPException(
                status_code=409,
                detail={
                    "type": "/errors/deck-name-conflict",
                    "title": "Deck name already exists",
                    "status": 409,
                    "detail": (
                        f"A deck named '{update_data.get('name')}' already exists for this language"
                    ),
                },
            )
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/deck-not-found",
                "title": "Deck not found",
                "status": 404,
                "detail": f"Deck {deck_id} does not exist",
            },
        )
    return _deck_to_response(deck)


@router.delete("/{deck_id}", status_code=204)
async def delete_deck(
    deck_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a deck. Cards belonging to it have deck_id nulled — not deleted.

    Returns 204 No Content on success, 404 if deck not found.
    """
    try:
        await core_decks.delete_deck(deck_id, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/deck-not-found",
                "title": "Deck not found",
                "status": 404,
                "detail": f"Deck {deck_id} does not exist",
            },
        )
    return Response(status_code=204)
