"""FastAPI router for practice queue — GET /practice/queue, POST /practice/session/start,
GET /practice/next-due, POST /practice/cards/{card_id}/rate, and
POST /practice/cards/{card_id}/evaluate.

Router only — no business logic. Business logic delegated to core/fsrs.py and core/practice.py.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import fsrs as core_fsrs
from lingosips.core import practice as core_practice
from lingosips.core import settings as core_settings
from lingosips.db.models import Card, PracticeSession
from lingosips.db.session import get_session
from lingosips.services.llm.base import AbstractLLMProvider
from lingosips.services.registry import get_llm_provider

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
    card_type: str = "word"  # "word" | "sentence" | "collocation"
    forms: str | None = None  # JSON string — contains register_context for sentence/collocation
    example_sentences: str | None = None  # JSON string — list of example sentences

    model_config = {"from_attributes": True}


class SessionStartResponse(BaseModel):
    session_id: int
    cards: list[QueueCard]


class RateCardRequest(BaseModel):
    rating: int  # 1=Again, 2=Hard, 3=Good, 4=Easy
    session_id: int | None = None  # links review to practice session

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


class NextDueResponse(BaseModel):
    next_due: datetime | None = None


@router.post("/session/start", response_model=SessionStartResponse)
async def start_session(
    session: AsyncSession = Depends(get_session),
) -> SessionStartResponse:
    """Create a practice session, return session_id and due cards.

    Creates a PracticeSession row for session stats tracking.
    Respects active_target_language and cards_per_session from Settings.
    Returns session_id=<id>, cards=[] when nothing is due.
    """
    settings = await core_settings.get_or_create_settings(session)
    active_lang = settings.active_target_language
    limit = settings.cards_per_session  # default: 20
    now = datetime.now(UTC)

    result = await session.execute(
        select(Card)
        .where(Card.due <= now, Card.target_language == active_lang)
        .order_by(Card.due.asc())
        .limit(limit)
    )
    cards = result.scalars().all()

    # Create practice session record BEFORE returning cards
    practice_session = PracticeSession()
    session.add(practice_session)
    await session.commit()
    await session.refresh(practice_session)

    return SessionStartResponse(
        session_id=practice_session.id,
        cards=[QueueCard.model_validate(c) for c in cards],
    )


@router.get("/next-due", response_model=NextDueResponse)
async def get_next_due(
    session: AsyncSession = Depends(get_session),
) -> NextDueResponse:
    """Return the earliest due date across ALL cards for the active language.

    Includes cards due in the past (already overdue) and future.
    Returns {"next_due": null} if no cards exist.
    """
    settings = await core_settings.get_or_create_settings(session)
    active_lang = settings.active_target_language

    result = await session.execute(
        select(func.min(Card.due)).where(Card.target_language == active_lang)
    )
    min_due = result.scalar()
    return NextDueResponse(next_due=min_due)


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
    updated_card = await core_fsrs.rate_card(card, request.rating, session, request.session_id)
    return RatedCardResponse.model_validate(updated_card)


# ── Evaluate endpoint ─────────────────────────────────────────────────────────


class EvaluateAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)

    @field_validator("answer")
    @classmethod
    def not_whitespace_only(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be whitespace only")
        return stripped  # normalise: core layer receives already-stripped value


class CharHighlightSchema(BaseModel):
    char: str
    correct: bool


class EvaluationResponse(BaseModel):
    is_correct: bool
    highlighted_chars: list[CharHighlightSchema]
    correct_value: str
    explanation: str | None
    suggested_rating: int  # 3=Good (correct), 1=Again (wrong)


@router.post("/cards/{card_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_card_answer(
    card_id: int,
    request: EvaluateAnswerRequest,
    llm: AbstractLLMProvider = Depends(get_llm_provider),
    session: AsyncSession = Depends(get_session),
) -> EvaluationResponse:
    """Evaluate a written answer against the card's correct value with AI feedback.

    Correct: exact match (case-insensitive, stripped) — no LLM call, suggested_rating=3.
    Wrong: character diff + LLM explanation (timeout=10s) — suggested_rating=1.
    LLM timeout/error: explanation=None silently; session continues.

    Raises:
        404: Card not found (RFC 7807 body)
        422: Missing/blank answer, or card has no translation (write mode requires one)
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
    if not card.translation or not card.translation.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/card-missing-translation",
                "title": "Card has no translation",
                "detail": (
                    f"Card {card_id} has no translation — write mode requires a known translation"
                ),
            },
        )
    result = await core_practice.evaluate_answer(card, request.answer, llm)
    return EvaluationResponse(
        is_correct=result.is_correct,
        highlighted_chars=[
            CharHighlightSchema(char=h.char, correct=h.correct) for h in result.highlighted_chars
        ],
        correct_value=result.correct_value,
        explanation=result.explanation,
        suggested_rating=result.suggested_rating,
    )
