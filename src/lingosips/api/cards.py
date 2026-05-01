"""FastAPI router for card creation — POST /cards/stream and GET /cards/{card_id}/audio.

Router only — no business logic. Delegates to core.cards.create_card_stream().
"""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import cards as core_cards
from lingosips.core import settings as core_settings
from lingosips.core.cards import AUDIO_DIR, CardCreateRequest
from lingosips.db.session import get_session
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_llm_provider, get_speech_provider
from lingosips.services.speech.base import AbstractSpeechProvider

router = APIRouter()


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
