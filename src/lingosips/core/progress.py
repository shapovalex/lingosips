"""Dashboard stats and session summary aggregation.

Uses indexed queries on reviews.reviewed_at and reviews.session_id.
No direct FastAPI imports. Takes AsyncSession, returns dataclasses.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import distinct as sa_distinct
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.db.models import Card, PracticeSession, Review

logger = structlog.get_logger(__name__)


def _utc_isoformat(dt: datetime) -> str:
    """Return an ISO 8601 UTC string with +00:00 offset.

    SQLite stores datetimes without timezone info; SQLModel reads them back as
    naive datetimes.  Calling .isoformat() on a naive datetime produces a string
    with no UTC offset (e.g. "2026-05-02T10:00:00"), which violates the ISO 8601
    contract clients expect.  This helper ensures the offset is always present.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


@dataclass
class DailyReviewCount:
    date: str  # "YYYY-MM-DD" UTC
    count: int


@dataclass
class DashboardStats:
    total_cards: int
    learned_cards: int  # rated Good (3) or Easy (4) at least once
    review_count_by_day: list[DailyReviewCount]  # last 30 days
    overall_recall_rate: float  # 0.0–1.0; 0.0 if no reviews


@dataclass
class PerCardRating:
    card_id: int
    rating: int


@dataclass
class SessionStats:
    session_id: int
    cards_reviewed: int
    per_card_ratings: list[PerCardRating]
    recall_rate: float  # 0.0–1.0
    time_spent_seconds: int  # 0 if fewer than 2 reviews
    started_at: str  # ISO 8601 UTC
    ended_at: str | None  # ISO 8601 UTC; null if session never had a rating


async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
    """Aggregate dashboard stats from the reviews + cards tables.

    Uses ix_reviews_reviewed_at for date range scan.
    Uses ix_cards_due (cards table) for total_cards count.
    """
    # 1. Total cards in collection
    total_result = await db.execute(select(func.count(Card.id)))
    total_cards: int = total_result.scalar_one() or 0

    # 2. Learned cards — distinct card_ids that received rating >= 3 at least once
    learned_result = await db.execute(
        select(func.count(sa_distinct(Review.card_id))).where(Review.rating >= 3)
    )
    learned_cards: int = learned_result.scalar_one() or 0

    # 3. Review count by day — last 30 days (uses ix_reviews_reviewed_at)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    daily_result = await db.execute(
        select(
            func.date(Review.reviewed_at).label("review_date"),
            func.count(Review.id).label("count"),
        )
        .where(Review.reviewed_at >= thirty_days_ago)
        .group_by(func.date(Review.reviewed_at))
        .order_by(func.date(Review.reviewed_at))
    )
    review_count_by_day = [
        DailyReviewCount(date=str(row.review_date), count=row.count) for row in daily_result
    ]

    # 4. Overall recall rate (rating >= 3 = correct)
    total_reviews_result = await db.execute(select(func.count(Review.id)))
    total_reviews: int = total_reviews_result.scalar_one() or 0
    correct_reviews_result = await db.execute(
        select(func.count(Review.id)).where(Review.rating >= 3)
    )
    correct_reviews: int = correct_reviews_result.scalar_one() or 0
    overall_recall_rate = correct_reviews / total_reviews if total_reviews > 0 else 0.0

    return DashboardStats(
        total_cards=total_cards,
        learned_cards=learned_cards,
        review_count_by_day=review_count_by_day,
        overall_recall_rate=overall_recall_rate,
    )


async def get_session_stats(db: AsyncSession, session_id: int) -> SessionStats | None:
    """Return per-session stats from the reviews table.

    Returns None if session_id does not exist in practice_sessions.
    time_spent_seconds = max(reviewed_at) - min(reviewed_at) for the session.
    """
    ps = await db.get(PracticeSession, session_id)
    if ps is None:
        return None

    reviews_result = await db.execute(
        select(Review).where(Review.session_id == session_id).order_by(Review.reviewed_at)
    )
    reviews = reviews_result.scalars().all()

    if not reviews:
        return SessionStats(
            session_id=session_id,
            cards_reviewed=0,
            per_card_ratings=[],
            recall_rate=0.0,
            time_spent_seconds=0,
            started_at=_utc_isoformat(ps.started_at),
            ended_at=_utc_isoformat(ps.ended_at) if ps.ended_at else None,
        )

    per_card_ratings = [PerCardRating(card_id=r.card_id, rating=r.rating) for r in reviews]
    correct = sum(1 for r in reviews if r.rating >= 3)
    recall_rate = correct / len(reviews)

    # Ensure UTC-aware datetimes for subtraction
    first_dt = reviews[0].reviewed_at
    last_dt = reviews[-1].reviewed_at
    if first_dt.tzinfo is None:
        first_dt = first_dt.replace(tzinfo=UTC)
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)
    time_spent_seconds = max(int((last_dt - first_dt).total_seconds()), 0)

    return SessionStats(
        session_id=session_id,
        cards_reviewed=len(reviews),
        per_card_ratings=per_card_ratings,
        recall_rate=recall_rate,
        time_spent_seconds=time_spent_seconds,
        started_at=_utc_isoformat(ps.started_at),
        ended_at=_utc_isoformat(ps.ended_at) if ps.ended_at else None,
    )
