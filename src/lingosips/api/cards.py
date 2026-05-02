"""FastAPI router for card CRUD — GET/PATCH/DELETE /cards/{card_id} + POST /cards/stream.

Router only — no business logic. Delegates to core.cards.*().
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import cards as core_cards
from lingosips.core import settings as core_settings
from lingosips.core.cards import AUDIO_DIR, IMAGE_DIR, CardCreateRequest
from lingosips.db.models import Card
from lingosips.db.session import get_session
from lingosips.services.image import ImageService
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_image_service, get_llm_provider, get_speech_provider
from lingosips.services.speech.base import AbstractSpeechProvider

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────


class CardFormsData(BaseModel):
    """Grammatical forms for a card — parsed from DB JSON string."""

    gender: str | None = None
    article: str | None = None
    plural: str | None = None
    conjugations: dict = Field(default_factory=dict)


class CardResponse(BaseModel):
    """Full card response shape — returned by GET and PATCH /cards/{card_id}."""

    id: int
    target_word: str
    translation: str | None
    forms: CardFormsData | None
    example_sentences: list[str]
    audio_url: str | None
    personal_note: str | None
    image_url: str | None
    image_skipped: bool
    card_type: str
    deck_id: int | None
    target_language: str
    fsrs_state: str
    due: datetime
    stability: float
    difficulty: float
    reps: int
    lapses: int
    last_review: datetime | None
    created_at: datetime
    updated_at: datetime


class CardUpdateRequest(BaseModel):
    """Partial update request for PATCH /cards/{card_id}.

    Only fields present in the request body are updated (checked via model_fields_set).
    """

    translation: str | None = Field(default=None, min_length=1, max_length=2000)
    forms: CardFormsData | None = None
    example_sentences: list[str] | None = None
    personal_note: str | None = Field(default=None, max_length=5000)
    deck_id: int | None = None
    image_skipped: bool | None = None


# ── Response conversion helper ────────────────────────────────────────────────


def _card_to_response(card: Card) -> CardResponse:
    """Convert a Card ORM instance to a CardResponse, parsing JSON fields."""
    forms: CardFormsData | None = None
    if card.forms:
        try:
            forms = CardFormsData(**json.loads(card.forms))
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
            pass  # Return None if forms JSON is malformed

    example_sentences: list[str] = []
    if card.example_sentences:
        try:
            parsed = json.loads(card.example_sentences)
            if isinstance(parsed, list):
                example_sentences = [str(s) for s in parsed]
        except (json.JSONDecodeError, TypeError):
            pass

    return CardResponse(
        id=card.id,
        target_word=card.target_word,
        translation=card.translation,
        forms=forms,
        example_sentences=example_sentences,
        audio_url=card.audio_url,
        personal_note=card.personal_note,
        image_url=card.image_url,
        image_skipped=card.image_skipped,
        card_type=card.card_type,
        deck_id=card.deck_id,
        target_language=card.target_language,
        fsrs_state=card.fsrs_state,
        due=card.due,
        stability=card.stability,
        difficulty=card.difficulty,
        reps=card.reps,
        lapses=card.lapses,
        last_review=card.last_review,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/stream")
async def create_card_stream(
    request: CardCreateRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
    speech: AbstractSpeechProvider = Depends(get_speech_provider),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream AI-generated card fields as SSE events.

    422 is returned by FastAPI BEFORE this function runs if target_word is
    empty or whitespace-only — the Pydantic validator in CardCreateRequest handles this.
    """
    # Fetch active target language from settings — pass as parameter to core (not fetched in core)
    settings = await core_settings.get_or_create_settings(session)
    target_language = settings.active_target_language

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in core_cards.create_card_stream(
            request=request,
            llm=llm,
            session=session,
            target_language=target_language,
            speech=speech,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: int,
    session: AsyncSession = Depends(get_session),
) -> CardResponse:
    """Fetch full card details by ID.

    Returns CardResponse with all fields, including forms/example_sentences
    parsed from their DB JSON string representation.
    404 RFC 7807 if card does not exist.
    """
    try:
        card = await core_cards.get_card(card_id, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/card-not-found",
                "title": "Card not found",
                "status": 404,
                "detail": f"Card {card_id} does not exist",
            },
        )
    return _card_to_response(card)


@router.get("/{card_id}/audio")
async def get_card_audio(card_id: int) -> FileResponse:
    """Serve WAV audio for a card.

    Returns the pre-generated WAV file from the local audio directory.
    404 RFC 7807 if no audio was generated (TTS failed or card has no audio).
    Does NOT require a DB session — audio presence is determined by file existence.
    """
    audio_path = AUDIO_DIR / f"{card_id}.wav"
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/audio-not-found",
                "title": "Audio not found",
                "detail": f"No audio file for card {card_id}",
                "status": 404,
            },
        )
    return FileResponse(audio_path, media_type="audio/wav")


@router.patch("/{card_id}", response_model=CardResponse)
async def patch_card(
    card_id: int,
    request: CardUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> CardResponse:
    """Partially update a card — only fields present in the request body are changed.

    Uses model_fields_set to detect which fields were explicitly provided.
    Returns the full updated CardResponse.
    404 if card does not exist, 422 if field validation fails.
    """
    # Build update dict from only the fields explicitly provided in the request
    update_data: dict = {}
    if "translation" in request.model_fields_set:
        update_data["translation"] = request.translation
    if "personal_note" in request.model_fields_set:
        update_data["personal_note"] = request.personal_note
    if "deck_id" in request.model_fields_set:
        update_data["deck_id"] = request.deck_id
    if "forms" in request.model_fields_set:
        update_data["forms"] = request.forms.model_dump() if request.forms else None
    if "example_sentences" in request.model_fields_set:
        update_data["example_sentences"] = request.example_sentences
    if "image_skipped" in request.model_fields_set:
        update_data["image_skipped"] = request.image_skipped

    try:
        card = await core_cards.update_card(card_id, update_data, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/card-not-found",
                "title": "Card not found",
                "status": 404,
                "detail": f"Card {card_id} does not exist",
            },
        )
    return _card_to_response(card)


@router.post("/{card_id}/generate-image", response_model=CardResponse)
async def generate_card_image_endpoint(
    card_id: int,
    session: AsyncSession = Depends(get_session),
    image_service: ImageService = Depends(get_image_service),
) -> CardResponse:
    """Trigger image generation for a card.

    422 if endpoint not configured (Depends raises before handler runs).
    422 on safety rejection, timeout, or API error.
    404 RFC 7807 if card does not exist.
    """
    try:
        card = await core_cards.generate_card_image(card_id, image_service, session)
    except ValueError as exc:
        msg = str(exc)
        if "does not exist" in msg:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "/errors/card-not-found",
                    "title": "Card not found",
                    "detail": msg,
                    "status": 404,
                },
            )
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/image-generation-failed",
                "title": "Image generation failed",
                "detail": msg,
                "status": 422,
            },
        )
    return _card_to_response(card)


@router.get("/{card_id}/image")
async def get_card_image(card_id: int) -> FileResponse:
    """Serve stored image for a card.

    Returns the image file from the local images directory.
    404 RFC 7807 if no image file exists for this card.
    Does NOT require a DB session — image presence is determined by file existence.
    """

    def _find_image_file() -> tuple[Path, str] | None:
        # Note: "jpeg" omitted — _CONTENT_TYPE_EXT always writes ".jpg", never ".jpeg"
        for ext in ("png", "jpg", "gif", "webp"):
            path = IMAGE_DIR / f"{card_id}.{ext}"
            if path.exists():
                media_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
                return path, media_type
        return None

    result = await asyncio.to_thread(_find_image_file)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/image-not-found",
                "title": "Image not found",
                "detail": f"No image file for card {card_id}",
                "status": 404,
            },
        )
    image_path, media_type = result
    return FileResponse(image_path, media_type=media_type)


@router.delete("/{card_id}", status_code=204)
async def delete_card(
    card_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a card by ID.

    Returns 204 No Content on success.
    404 RFC 7807 if card does not exist.
    """
    try:
        await core_cards.delete_card(card_id, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/card-not-found",
                "title": "Card not found",
                "status": 404,
                "detail": f"Card {card_id} does not exist",
            },
        )
    return Response(status_code=204)
