"""FastAPI router for progress stats — GET /progress/dashboard, GET /progress/sessions/{session_id}.

Router only — no business logic. Business logic delegated to core/progress.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import progress as core_progress
from lingosips.db.session import get_session

router = APIRouter()


class DailyReviewCountResponse(BaseModel):
    date: str  # "YYYY-MM-DD"
    count: int


class DashboardResponse(BaseModel):
    total_cards: int
    learned_cards: int
    review_count_by_day: list[DailyReviewCountResponse]
    overall_recall_rate: float


class PerCardRatingResponse(BaseModel):
    card_id: int
    rating: int


class SessionStatsResponse(BaseModel):
    session_id: int
    cards_reviewed: int
    per_card_ratings: list[PerCardRatingResponse]
    recall_rate: float
    time_spent_seconds: int
    started_at: str
    ended_at: str | None


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Return aggregate progress stats.

    Aggregates from reviews + cards tables using indexed queries.
    Returns zeroes (not null) when no reviews exist.
    """
    stats = await core_progress.get_dashboard_stats(session)
    return DashboardResponse(
        total_cards=stats.total_cards,
        learned_cards=stats.learned_cards,
        review_count_by_day=[
            DailyReviewCountResponse(date=d.date, count=d.count) for d in stats.review_count_by_day
        ],
        overall_recall_rate=stats.overall_recall_rate,
    )


@router.get("/sessions/{session_id}", response_model=SessionStatsResponse)
async def get_session_stats(
    session_id: int,
    session: AsyncSession = Depends(get_session),
) -> SessionStatsResponse:
    """Return per-session stats from the reviews table.

    Raises:
        404: session_id does not exist (RFC 7807 body)
    """
    stats = await core_progress.get_session_stats(session, session_id)
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "/errors/session-not-found",
                "title": "Session not found",
                "detail": f"Practice session {session_id} does not exist",
            },
        )
    return SessionStatsResponse(
        session_id=stats.session_id,
        cards_reviewed=stats.cards_reviewed,
        per_card_ratings=[
            PerCardRatingResponse(card_id=r.card_id, rating=r.rating)
            for r in stats.per_card_ratings
        ],
        recall_rate=stats.recall_rate,
        time_spent_seconds=stats.time_spent_seconds,
        started_at=stats.started_at,
        ended_at=stats.ended_at,
    )
