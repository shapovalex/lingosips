"""Tests for core/progress.py — dashboard stats and session aggregation.

TDD: written before implementation.
AC: 1, 2, 4, 5 (Story 3.5)
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from lingosips.core.progress import get_dashboard_stats, get_session_stats


@pytest.mark.anyio
class TestGetDashboardStats:
    """Tests for get_dashboard_stats() — AC: 1, 2, 5."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    async def test_empty_db_returns_all_zeroes(self, session) -> None:
        """Empty DB → all stats are zero, review_count_by_day is []."""
        stats = await get_dashboard_stats(session)
        assert stats.total_cards == 0
        assert stats.learned_cards == 0
        assert stats.review_count_by_day == []
        assert stats.overall_recall_rate == 0.0

    async def test_total_cards_counts_all_cards(self, session) -> None:
        """total_cards reflects all cards in the DB."""
        from lingosips.db.models import Card

        for i in range(3):
            card = Card(target_word=f"word{i}", target_language="es")
            session.add(card)
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert stats.total_cards == 3

    async def test_learned_cards_counts_distinct_cards_rated_good_or_easy(self, session) -> None:
        """learned_cards counts distinct cards with rating >= 3 (Good or Easy)."""
        from lingosips.db.models import Card, Review

        card1 = Card(target_word="one", target_language="es")
        card2 = Card(target_word="two", target_language="es")
        session.add(card1)
        session.add(card2)
        await session.commit()
        await session.refresh(card1)
        await session.refresh(card2)

        # card1: rated Good (3) — learned
        # card2: rated Easy (4) — learned
        session.add(
            Review(
                card_id=card1.id,
                rating=3,
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        session.add(
            Review(
                card_id=card2.id,
                rating=4,
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert stats.learned_cards == 2

    async def test_learned_cards_does_not_double_count_multiple_good_ratings(self, session) -> None:
        """Multiple Good/Easy ratings for the same card count as 1 learned card."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="one", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # Rate same card Good twice
        for _ in range(2):
            session.add(
                Review(
                    card_id=card.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=1.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert stats.learned_cards == 1

    async def test_again_and_hard_ratings_not_counted_as_learned(self, session) -> None:
        """Cards rated only Again (1) or Hard (2) are not counted as learned."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="again", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        session.add(
            Review(
                card_id=card.id,
                rating=1,
                stability_after=0.1,
                difficulty_after=5.0,
                fsrs_state_after="Learning",
                reps_after=1,
                lapses_after=1,
            )
        )
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert stats.learned_cards == 0

    async def test_review_count_by_day_last_30_days_only(self, session) -> None:
        """review_count_by_day aggregates reviews from the last 30 days only."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="card", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        now = datetime.now(UTC)
        # Recent review — within 30 days
        session.add(
            Review(
                card_id=card.id,
                rating=3,
                reviewed_at=now - timedelta(days=5),
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert len(stats.review_count_by_day) == 1
        assert stats.review_count_by_day[0].count == 1

    async def test_review_count_by_day_excludes_older_reviews(self, session) -> None:
        """Reviews older than 30 days are excluded from review_count_by_day."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="old", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        now = datetime.now(UTC)
        # Old review — 31 days ago
        session.add(
            Review(
                card_id=card.id,
                rating=3,
                reviewed_at=now - timedelta(days=31),
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert stats.review_count_by_day == []

    async def test_recall_rate_is_fraction_of_rating_gte_3(self, session) -> None:
        """overall_recall_rate = correct (rating>=3) / total reviews."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="recall", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # 3 reviews: 2 Good (3), 1 Again (1) → 2/3
        for rating in [3, 3, 1]:
            session.add(
                Review(
                    card_id=card.id,
                    rating=rating,
                    stability_after=1.0,
                    difficulty_after=1.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        stats = await get_dashboard_stats(session)
        assert abs(stats.overall_recall_rate - 2 / 3) < 0.001

    async def test_recall_rate_zero_when_no_reviews(self, session) -> None:
        """overall_recall_rate is 0.0 when no reviews exist."""
        stats = await get_dashboard_stats(session)
        assert stats.overall_recall_rate == 0.0


@pytest.mark.anyio
class TestGetSessionStats:
    """Tests for get_session_stats() — AC: 4."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    @pytest.fixture
    async def practice_session(self, session):
        from lingosips.db.models import PracticeSession

        ps = PracticeSession()
        session.add(ps)
        await session.commit()
        await session.refresh(ps)
        return ps

    async def test_returns_none_for_nonexistent_session_id(self, session) -> None:
        """get_session_stats returns None for a session_id that does not exist."""
        result = await get_session_stats(session, 99999)
        assert result is None

    async def test_returns_zero_cards_reviewed_for_empty_session(
        self, session, practice_session
    ) -> None:
        """Session with no reviews → cards_reviewed=0, per_card_ratings=[], recall_rate=0."""
        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert stats.cards_reviewed == 0
        assert stats.per_card_ratings == []
        assert stats.recall_rate == 0.0
        assert stats.time_spent_seconds == 0

    async def test_cards_reviewed_matches_review_count_for_session(
        self, session, practice_session
    ) -> None:
        """cards_reviewed matches the number of reviews for the session."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="test", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        for _ in range(3):
            session.add(
                Review(
                    card_id=card.id,
                    rating=3,
                    session_id=practice_session.id,
                    stability_after=1.0,
                    difficulty_after=1.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert stats.cards_reviewed == 3

    async def test_per_card_ratings_correct(self, session, practice_session) -> None:
        """per_card_ratings contains card_id + rating for each review."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="rated", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        session.add(
            Review(
                card_id=card.id,
                rating=4,
                session_id=practice_session.id,
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert len(stats.per_card_ratings) == 1
        assert stats.per_card_ratings[0].card_id == card.id
        assert stats.per_card_ratings[0].rating == 4

    async def test_recall_rate_correct(self, session, practice_session) -> None:
        """recall_rate = correct (rating>=3) / total for session."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="rate", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        for rating in [3, 1, 4]:  # 2/3 correct
            session.add(
                Review(
                    card_id=card.id,
                    rating=rating,
                    session_id=practice_session.id,
                    stability_after=1.0,
                    difficulty_after=1.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert abs(stats.recall_rate - 2 / 3) < 0.001

    async def test_time_spent_seconds_is_delta_between_first_and_last_review(
        self, session, practice_session
    ) -> None:
        """time_spent_seconds = (last reviewed_at - first reviewed_at).total_seconds()."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="time", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        now = datetime.now(UTC)
        session.add(
            Review(
                card_id=card.id,
                rating=3,
                session_id=practice_session.id,
                reviewed_at=now - timedelta(seconds=120),
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        session.add(
            Review(
                card_id=card.id,
                rating=4,
                session_id=practice_session.id,
                reviewed_at=now,
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=2,
                lapses_after=0,
            )
        )
        await session.commit()

        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert stats.time_spent_seconds == 120

    async def test_time_spent_zero_for_single_review(self, session, practice_session) -> None:
        """Single review → time_spent_seconds = 0 (no delta)."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="single", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        session.add(
            Review(
                card_id=card.id,
                rating=3,
                session_id=practice_session.id,
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert stats.time_spent_seconds == 0

    async def test_started_at_from_practice_session_record(self, session, practice_session) -> None:
        """started_at in stats comes from PracticeSession.started_at."""
        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert stats.started_at is not None
        assert isinstance(stats.started_at, str)

    async def test_ended_at_null_when_no_cards_rated(self, session, practice_session) -> None:
        """ended_at is None when PracticeSession.ended_at is None (no ratings yet)."""
        stats = await get_session_stats(session, practice_session.id)
        assert stats is not None
        assert stats.ended_at is None
