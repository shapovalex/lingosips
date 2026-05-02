"""FastAPI router for practice queue — GET /practice/queue and POST /practice/cards/{card_id}/rate.

Router only — no business logic. Business logic delegated to core/fsrs.py.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import fsrs as core_fsrs
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


class RateCardRequest(BaseModel):
    rating: int  # 1=Again, 2=Hard, 3=Good, 4=Easy

    @field_validator("rating")
    @classmethod
    def rating_must_be_valid(cls, v: int) -> int:
        if v not in (1, 2, 3, 4):
            raise ValueError("rating must be 1, 2, 3, or 4")
        return v


class RatedCardResponse(QueueCard):
    last_review: datetime | None = None  # adds last_review on top of QueueCard


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


@router.post("/cards/{card_id}/rate", response_model=RatedCardResponse)
async def rate_card(
    card_id: int,
    request: RateCardRequest,
    session: AsyncSession = Depends(get_session),
) -> RatedCardResponse:
    """Rate a card using FSRS algorithm and update its scheduling state.

    Calls core/fsrs.py to compute new FSRS state, updates the card,
    and inserts a review row. Returns the updated card.

    Raises:
        404: Card not found (RFC 7807 body)
        422: Invalid rating (must be 1–4)
    """
    card = await session.get(Card, card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/card-not-found",
                "title": "Card not found",
                "detail": f"Card {card_id} does not exist",
            },
        )
    updated_card = await core_fsrs.rate_card(card, request.rating, session)
    return RatedCardResponse.model_validate(updated_card)
