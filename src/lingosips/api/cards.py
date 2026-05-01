"""FastAPI router for card creation — POST /cards/stream.

Router only — no business logic. Delegates to core.cards.create_card_stream().
"""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import cards as core_cards
from lingosips.core import settings as core_settings
from lingosips.core.cards import CardCreateRequest
from lingosips.db.session import get_session
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_llm_provider

router = APIRouter()


@router.post("/stream")
async def create_card_stream(
    request: CardCreateRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
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
