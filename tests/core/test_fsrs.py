"""Tests for core/fsrs.py — FSRS scheduling wrapper.

TDD: tests written BEFORE implementation to drive core/fsrs.py.
AC: 2, 3

Note on fsrs State enum:
    The installed fsrs package has State.Learning, State.Review, State.Relearning.
    Cards with fsrs_state="New" (DB initial state) are treated as Learning for scheduling.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.anyio
class TestBuildFsrsCard:
    """Tests for build_fsrs_card() — reconstructs fsrs.Card from DB Card model."""

    def test_new_card_defaults(self) -> None:
        """A brand-new Card (fsrs_state='New') → fsrs.Card treated as Learning state."""
        from fsrs import State

        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        db_card = Card(
            target_word="test",
            target_language="es",
            stability=0.0,
            difficulty=0.0,
            reps=0,
            lapses=0,
            fsrs_state="New",
        )
        fsrs_card = build_fsrs_card(db_card)

        # "New" maps to Learning in the installed fsrs library (no State.New exists)
        assert fsrs_card.state == State.Learning
        # stability=0.0 is passed as None so FSRS can initialise it correctly
        assert fsrs_card.stability is None

    def test_existing_card_state_restored(self) -> None:
        """A card in Review state → fsrs.Card with State.Review and correct values."""
        from fsrs import State

        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        now = datetime.now(UTC)
        db_card = Card(
            target_word="test",
            target_language="es",
            stability=2.5,
            difficulty=5.0,
            reps=3,
            lapses=1,
            fsrs_state="Review",
            last_review=now - timedelta(days=1),
        )
        fsrs_card = build_fsrs_card(db_card)

        assert fsrs_card.stability == 2.5
        assert fsrs_card.difficulty == 5.0
        assert fsrs_card.state == State.Review
        # Note: reps/lapses are tracked in our DB, not in fsrs.Card

    def test_learning_state_restored(self) -> None:
        """A card in Learning state → fsrs.Card with State.Learning."""
        from fsrs import State

        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        db_card = Card(
            target_word="test",
            target_language="es",
            stability=1.0,
            difficulty=4.0,
            reps=1,
            lapses=0,
            fsrs_state="Learning",
        )
        fsrs_card = build_fsrs_card(db_card)

        assert fsrs_card.state == State.Learning

    def test_relearning_state_restored(self) -> None:
        """A card in Relearning state → fsrs.Card with State.Relearning."""
        from fsrs import State

        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        db_card = Card(
            target_word="test",
            target_language="es",
            stability=1.2,
            difficulty=6.5,
            reps=5,
            lapses=2,
            fsrs_state="Relearning",
        )
        fsrs_card = build_fsrs_card(db_card)

        assert fsrs_card.state == State.Relearning

    def test_unknown_fsrs_state_defaults_to_learning(self) -> None:
        """An unrecognised fsrs_state string → defaults to State.Learning (safe fallback)."""
        from fsrs import State

        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        db_card = Card(
            target_word="test",
            target_language="es",
            fsrs_state="Mature",  # legacy/unknown value
        )
        fsrs_card = build_fsrs_card(db_card)

        assert fsrs_card.state == State.Learning

    def test_naive_due_datetime_gets_utc_attached(self) -> None:
        """Naive ``due`` datetime from SQLite → UTC-aware after build_fsrs_card.

        Regression: SQLite strips timezone on persist.  The second rating of a
        card would crash with ``TypeError: can't subtract offset-naive and
        offset-aware datetimes`` if we pass the raw naive datetime to the fsrs
        library, which compares it against ``datetime.now(UTC)``.
        """
        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        naive_due = datetime(2026, 5, 2, 12, 0, 0)  # no tzinfo — as stored by SQLite
        naive_last_review = datetime(2026, 5, 1, 12, 0, 0)
        assert naive_due.tzinfo is None
        assert naive_last_review.tzinfo is None

        db_card = Card(
            target_word="test",
            target_language="es",
            stability=2.3,
            difficulty=2.1,
            reps=1,
            lapses=0,
            fsrs_state="Learning",
            due=naive_due,
            last_review=naive_last_review,
        )
        fsrs_card = build_fsrs_card(db_card)

        # Both timestamps must be UTC-aware so fsrs arithmetic doesn't raise TypeError
        assert fsrs_card.due is not None and fsrs_card.due.tzinfo is not None
        assert fsrs_card.last_review is not None and fsrs_card.last_review.tzinfo is not None

    def test_aware_due_datetime_passes_through_unchanged(self) -> None:
        """Already-aware ``due`` datetime is not double-wrapped."""
        from lingosips.core.fsrs import build_fsrs_card
        from lingosips.db.models import Card

        aware_due = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
        db_card = Card(
            target_word="test",
            target_language="es",
            stability=1.0,
            difficulty=4.0,
            reps=1,
            lapses=0,
            fsrs_state="Learning",
            due=aware_due,
        )
        fsrs_card = build_fsrs_card(db_card)

        assert fsrs_card.due == aware_due


@pytest.mark.anyio
class TestRateCard:
    """Tests for rate_card() — calls FSRS, updates DB card, inserts review row."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_rating_updates_fsrs_state(self, session: AsyncSession) -> None:
        """Good rating → stability populated (was None/0 on new card), reps increases."""
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        card = Card(target_word="hola", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        updated = await rate_card(card, 3, session)  # 3 = Good

        assert updated.stability > 0
        assert updated.reps == 1

    async def test_review_row_inserted(self, session: AsyncSession) -> None:
        """After rating, exactly one row is inserted into the reviews table."""
        from sqlalchemy import select

        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card, Review

        card = Card(target_word="casa", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        await rate_card(card, 3, session)  # Good

        result = await session.execute(select(Review).where(Review.card_id == card_id))
        reviews = result.scalars().all()
        assert len(reviews) == 1
        review = reviews[0]
        assert review.rating == 3
        assert review.card_id == card_id
        assert review.reviewed_at is not None

    async def test_all_four_ratings_accepted(self, session: AsyncSession) -> None:
        """Ratings 1, 2, 3, 4 all complete without error."""
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        for rating in [1, 2, 3, 4]:
            card = Card(target_word=f"word_{rating}", target_language="es")
            session.add(card)
            await session.commit()
            await session.refresh(card)

            updated = await rate_card(card, rating, session)
            assert updated is not None

    async def test_reps_increments_on_good(self, session: AsyncSession) -> None:
        """Good rating → reps goes from 0 → 1."""
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        card = Card(target_word="gato", target_language="es", reps=0)
        session.add(card)
        await session.commit()
        await session.refresh(card)

        updated = await rate_card(card, 3, session)  # Good

        assert updated.reps == 1

    async def test_lapses_increments_on_again(self, session: AsyncSession) -> None:
        """Again rating (1) on a Review card → lapses increments."""
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        # Card must be in Review state for lapses to increment on Again
        card = Card(
            target_word="perro",
            target_language="es",
            lapses=0,
            reps=3,
            fsrs_state="Review",
            stability=5.0,
            difficulty=5.0,
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        initial_lapses = card.lapses
        updated = await rate_card(card, 1, session)  # Again

        assert updated.lapses > initial_lapses

    async def test_due_date_updated_after_rating(self, session: AsyncSession) -> None:
        """After rating, the card's due date is updated to a new scheduled time."""
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        now = datetime.now(UTC)
        card = Card(target_word="libro", target_language="es", due=now)
        session.add(card)
        await session.commit()
        await session.refresh(card)

        updated = await rate_card(card, 3, session)  # Good

        # After Good rating, next due should be set by FSRS
        assert updated.due is not None

    async def test_review_snapshot_contains_post_review_state(self, session: AsyncSession) -> None:
        """Review row's snapshot fields match the updated card state."""
        from sqlalchemy import select

        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card, Review

        card = Card(target_word="amigo", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        updated = await rate_card(card, 3, session)

        result = await session.execute(select(Review).where(Review.card_id == card_id))
        review = result.scalar_one()

        assert review.stability_after == updated.stability
        assert review.difficulty_after == updated.difficulty
        assert review.fsrs_state_after == updated.fsrs_state
        assert review.reps_after == updated.reps
        assert review.lapses_after == updated.lapses

    async def test_last_review_set_on_card(self, session: AsyncSession) -> None:
        """After rating, card.last_review is populated with a recent datetime."""
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        card = Card(target_word="sol", target_language="es", last_review=None)
        session.add(card)
        await session.commit()
        await session.refresh(card)

        updated = await rate_card(card, 3, session)

        assert updated.last_review is not None

    async def test_second_rating_does_not_raise_naive_tz_error(self, session: AsyncSession) -> None:
        """Two consecutive ratings on the same card should not raise TypeError.

        Regression: SQLite strips timezone from persisted datetimes.  After the first
        rating, ``due`` and ``last_review`` are written to SQLite as aware datetimes but
        read back as naive.  Passing them as-is to the fsrs library, which internally
        compares with ``datetime.now(UTC)`` (offset-aware), raises::

            TypeError: can't subtract offset-naive and offset-aware datetimes

        The fix in ``build_fsrs_card`` attaches UTC to any naive datetime.
        """
        from lingosips.core.fsrs import rate_card
        from lingosips.db.models import Card

        card = Card(target_word="ventana", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # First rating — card is "New" (naive datetimes may come back from DB)
        card = await rate_card(card, 3, session)  # Good
        assert card.reps == 1

        # Second rating — card has stability/difficulty set; due/last_review are now
        # naive datetimes from SQLite.  Must NOT raise TypeError.
        card = await rate_card(card, 1, session)  # Again
        assert card.reps == 2
