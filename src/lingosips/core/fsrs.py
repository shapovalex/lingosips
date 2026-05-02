"""FSRS scheduling wrapper.

THIS IS THE ONLY MODULE THAT IMPORTS FROM THE fsrs LIBRARY.
api/practice.py calls core.fsrs.rate_card() — never imports fsrs directly.

Note on fsrs library State enum:
    The installed fsrs package has State.Learning, State.Review, State.Relearning.
    Cards in the DB start with fsrs_state="New" (our initial state marker).
    "New" maps to State.Learning for FSRS scheduling purposes —
    new cards are treated as Learning cards when first rated.
"""

from datetime import UTC, datetime

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.db.models import Card, PracticeSession, Review

# Module-level singleton — created once per process
_scheduler = Scheduler(desired_retention=0.9)

# Rating integer → Rating enum
_RATING_MAP: dict[int, Rating] = {
    1: Rating.Again,
    2: Rating.Hard,
    3: Rating.Good,
    4: Rating.Easy,
}

# State enum → DB string (fsrs_state column)
_STATE_MAP: dict[State, str] = {
    State.Learning: "Learning",
    State.Review: "Review",
    State.Relearning: "Relearning",
}

# DB string → State enum (for reconstructing fsrs.Card from DB values).
# "New" is the initial DB marker — maps to State.Learning for FSRS purposes.
# Any unrecognised state also falls back to State.Learning.
_STATE_MAP_REVERSE: dict[str, State] = {
    "New": State.Learning,
    "Learning": State.Learning,
    "Review": State.Review,
    "Relearning": State.Relearning,
}


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime loaded from SQLite, or return it unchanged if already aware.

    SQLite stores datetimes without timezone info. When a previously-rated card
    is loaded and its ``due`` / ``last_review`` values are passed back to the fsrs
    library, the library compares them against ``datetime.now(UTC)`` (timezone-aware).
    Passing a naive datetime at that point raises ``TypeError: can't subtract
    offset-naive and offset-aware datetimes``.  Attaching UTC is safe — all
    datetimes in this application are UTC by convention.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def build_fsrs_card(db_card: Card) -> FsrsCard:
    """Reconstruct an fsrs.Card from DB model values.

    Restores scheduling state (stability, difficulty, state, due, last_review) so
    the FSRS algorithm continues from where it left off.

    Note: The installed fsrs library Card does NOT have reps/lapses fields.
    Those are tracked manually in our DB and updated in rate_card().
    """
    fsrs_state = _STATE_MAP_REVERSE.get(db_card.fsrs_state, State.Learning)

    # stability and difficulty are 0.0 for brand-new cards — pass None for
    # those so the FSRS scheduler initialises them correctly on first review.
    # Using `or None` handles both 0.0 (falsy) and None defensively.
    stability: float | None = db_card.stability or None
    difficulty: float | None = db_card.difficulty or None

    fsrs_card = FsrsCard(
        state=fsrs_state,
        stability=stability,
        difficulty=difficulty,
        # Attach UTC to naive datetimes loaded from SQLite (see _ensure_utc docstring).
        due=_ensure_utc(db_card.due),
        last_review=_ensure_utc(db_card.last_review),
    )
    return fsrs_card


async def rate_card(
    db_card: Card,
    rating: int,
    session: AsyncSession,
    session_id: int | None = None,
) -> Card:
    """Apply an FSRS rating to a card, update the DB, and insert a review row.

    Steps:
    1. Rebuild fsrs.Card from current DB state
    2. Call scheduler.review_card() to get new scheduling values
    3. Update db_card fields: stability, difficulty, due, last_review, reps, lapses, fsrs_state
    4. Insert a Review row (post-review FSRS snapshot) with optional session_id
    5. Update PracticeSession.ended_at if session_id is provided
    6. session.add(review) + await session.commit()
    7. await session.refresh(db_card)
    8. Return updated db_card

    Args:
        db_card: The Card ORM instance to rate (must already be persisted).
        rating: Integer 1–4 (Again=1, Hard=2, Good=3, Easy=4).
        session: Async SQLAlchemy session — caller owns lifecycle.
        session_id: Optional PracticeSession.id to link this review to a session.

    Raises:
        ValueError: If rating is not in the range 1–4.

    Returns:
        The same Card instance, refreshed with updated scheduling values.
    """
    if rating not in _RATING_MAP:
        raise ValueError(f"rating must be 1, 2, 3, or 4; got {rating}")
    rating_enum = _RATING_MAP[rating]

    # Capture pre-review state for lapse tracking
    was_in_review = db_card.fsrs_state == "Review"

    # Reconstruct fsrs.Card from current DB state
    fsrs_card = build_fsrs_card(db_card)

    # Call FSRS scheduler (synchronous — safe inside async handlers)
    fsrs_card, _review_log = _scheduler.review_card(fsrs_card, rating_enum)

    new_state = _STATE_MAP.get(fsrs_card.state, "Learning")

    # Update card with new FSRS scheduling values
    db_card.stability = fsrs_card.stability if fsrs_card.stability is not None else 0.0
    db_card.difficulty = fsrs_card.difficulty if fsrs_card.difficulty is not None else 0.0
    db_card.due = fsrs_card.due
    db_card.last_review = fsrs_card.last_review
    db_card.fsrs_state = new_state
    now = datetime.now(UTC)
    db_card.updated_at = now

    # reps: increment on every review (tracked manually — fsrs Card has no reps field)
    db_card.reps = db_card.reps + 1

    # lapses: increment when a Review card gets Again (moved to Relearning)
    if was_in_review and rating == 1:  # Again = 1
        db_card.lapses = db_card.lapses + 1

    # Insert review row — snapshot of post-review FSRS state.
    # Use the same `now` timestamp as updated_at to keep audit trail consistent.
    review = Review(
        card_id=db_card.id,
        rating=rating,
        reviewed_at=now,
        stability_after=db_card.stability,
        difficulty_after=db_card.difficulty,
        fsrs_state_after=db_card.fsrs_state,
        reps_after=db_card.reps,
        lapses_after=db_card.lapses,
        session_id=session_id,
    )

    # db_card is already tracked by the session (loaded via session.get) — no re-add needed.
    session.add(review)

    # Update PracticeSession.ended_at so session stats know the last review time.
    if session_id is not None:
        ps = await session.get(PracticeSession, session_id)
        if ps is not None:
            ps.ended_at = now
            session.add(ps)

    await session.commit()
    await session.refresh(db_card)

    return db_card
