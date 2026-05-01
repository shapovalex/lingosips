"""FastAPI router for practice queue — GET /practice/queue.

Router only — no business logic.
Full FSRS session management added in Story 3.1.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import settings as core_settings
from lingosips.db.models import Card
from lingosips.db.session import get_session

router = APIRouter()


class QueueCard(BaseModel):
    id: int
    target_word: str
    translation: str | None
    target_language: str
    due: datetime
    fsrs_state: str
    stability: float
    difficulty: float
    reps: int
    lapses: int

    model_config = {"from_attributes": True}


@router.get("/queue", response_model=list[QueueCard])
async def get_practice_queue(
    session: AsyncSession = Depends(get_session),
) -> list[QueueCard]:
    """Return all due cards ordered by due date ascending.

    Filters by active_target_language from Settings.
    Returns [] (never null) when no cards are due.
    Full FSRS state per card + session management added in Story 3.1.
    """
    settings = await core_settings.get_or_create_settings(session)
    active_lang = settings.active_target_language
    now = datetime.now(UTC)

    result = await session.execute(
        select(Card)
        .where(Card.due <= now, Card.target_language == active_lang)
        .order_by(Card.due.asc())
    )
    cards = result.scalars().all()
    return [QueueCard.model_validate(c) for c in cards]
