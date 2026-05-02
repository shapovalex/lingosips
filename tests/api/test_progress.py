"""Tests for api/progress.py — GET /progress/dashboard and GET /progress/sessions/{session_id}.

TDD: written before implementation.
AC: 1, 2, 4, 6 (Story 3.5)
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.mark.anyio
class TestGetDashboard:
    """Tests for GET /progress/dashboard (AC: 1, 2, 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    async def test_empty_db_returns_zero_counts(self, client: AsyncClient) -> None:
        """GET /progress/dashboard with empty DB → all zero, no errors."""
        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["total_cards"] == 0
        assert data["learned_cards"] == 0
        assert data["overall_recall_rate"] == 0.0
        assert data["review_count_by_day"] == []

    async def test_dashboard_returns_correct_total_cards(
        self, client: AsyncClient, session
    ) -> None:
        """total_cards reflects all cards in DB."""
        from lingosips.db.models import Card

        for i in range(5):
            session.add(Card(target_word=f"word{i}", target_language="es"))
        await session.commit()

        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        assert response.json()["total_cards"] == 5

    async def test_dashboard_returns_correct_learned_count(
        self, client: AsyncClient, session
    ) -> None:
        """learned_cards counts distinct cards rated Good/Easy."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="learned", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

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

        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        assert response.json()["learned_cards"] == 1

    async def test_dashboard_returns_review_count_by_day(
        self, client: AsyncClient, session
    ) -> None:
        """review_count_by_day contains entries for days with reviews."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="recent", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        session.add(
            Review(
                card_id=card.id,
                rating=3,
                reviewed_at=datetime.now(UTC) - timedelta(days=2),
                stability_after=1.0,
                difficulty_after=1.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert len(data["review_count_by_day"]) == 1
        assert data["review_count_by_day"][0]["count"] == 1

    async def test_dashboard_returns_recall_rate(self, client: AsyncClient, session) -> None:
        """overall_recall_rate is a float between 0 and 1."""
        from lingosips.db.models import Card, Review

        card = Card(target_word="rate", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

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

        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        rate = response.json()["overall_recall_rate"]
        assert 0.0 <= rate <= 1.0
        assert rate == 1.0

    async def test_response_shape_matches_spec(self, client: AsyncClient) -> None:
        """All required fields are present in dashboard response."""
        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        data = response.json()
        for field in ["total_cards", "learned_cards", "review_count_by_day", "overall_recall_rate"]:
            assert field in data, f"Missing field: {field}"

    async def test_review_count_by_day_empty_when_no_reviews(self, client: AsyncClient) -> None:
        """review_count_by_day is [] (not null) when no reviews exist."""
        response = await client.get("/progress/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["review_count_by_day"] == []
        assert data["review_count_by_day"] is not None


@pytest.mark.anyio
class TestGetSessionStats:
    """Tests for GET /progress/sessions/{session_id} (AC: 4, 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    @pytest.fixture
    async def seeded_session(self, session):
        """Practice session with 2 reviews (1 Good, 1 Again)."""
        from lingosips.db.models import Card, PracticeSession, Review

        ps = PracticeSession()
        session.add(ps)
        card = Card(target_word="test", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(ps)
        await session.refresh(card)

        now = datetime.now(UTC)
        session.add(
            Review(
                card_id=card.id,
                rating=3,
                session_id=ps.id,
                reviewed_at=now - timedelta(seconds=60),
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
                rating=1,
                session_id=ps.id,
                reviewed_at=now,
                stability_after=0.5,
                difficulty_after=5.0,
                fsrs_state_after="Learning",
                reps_after=2,
                lapses_after=1,
            )
        )
        ps.ended_at = now
        session.add(ps)
        await session.commit()
        await session.refresh(ps)
        return ps

    @pytest.fixture
    async def empty_session(self, session):
        from lingosips.db.models import PracticeSession

        ps = PracticeSession()
        session.add(ps)
        await session.commit()
        await session.refresh(ps)
        return ps

    async def test_returns_404_for_nonexistent_session(self, client: AsyncClient) -> None:
        """GET /progress/sessions/99999 → 404 with RFC 7807 body."""
        response = await client.get("/progress/sessions/99999")
        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "/errors/session-not-found"
        assert data["title"] == "Session not found"

    async def test_returns_correct_cards_reviewed(
        self, client: AsyncClient, seeded_session
    ) -> None:
        """cards_reviewed matches number of reviews in session."""
        response = await client.get(f"/progress/sessions/{seeded_session.id}")
        assert response.status_code == 200
        assert response.json()["cards_reviewed"] == 2

    async def test_returns_correct_per_card_ratings(
        self, client: AsyncClient, seeded_session
    ) -> None:
        """per_card_ratings contains all review ratings for the session."""
        response = await client.get(f"/progress/sessions/{seeded_session.id}")
        assert response.status_code == 200
        ratings = response.json()["per_card_ratings"]
        assert len(ratings) == 2
        for entry in ratings:
            assert "card_id" in entry
            assert "rating" in entry

    async def test_returns_correct_recall_rate(self, client: AsyncClient, seeded_session) -> None:
        """recall_rate = 1/2 for session with 1 Good and 1 Again."""
        response = await client.get(f"/progress/sessions/{seeded_session.id}")
        assert response.status_code == 200
        assert abs(response.json()["recall_rate"] - 0.5) < 0.001

    async def test_returns_correct_time_spent(self, client: AsyncClient, seeded_session) -> None:
        """time_spent_seconds is delta between first and last review."""
        response = await client.get(f"/progress/sessions/{seeded_session.id}")
        assert response.status_code == 200
        assert response.json()["time_spent_seconds"] == 60

    async def test_started_at_present(self, client: AsyncClient, seeded_session) -> None:
        """started_at is present and is an ISO 8601 string."""
        response = await client.get(f"/progress/sessions/{seeded_session.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["started_at"] is not None
        assert isinstance(data["started_at"], str)

    async def test_empty_session_returns_zero_cards(
        self, client: AsyncClient, empty_session
    ) -> None:
        """Session with no reviews returns cards_reviewed=0, not an error."""
        response = await client.get(f"/progress/sessions/{empty_session.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["cards_reviewed"] == 0
        assert data["per_card_ratings"] == []
        assert data["recall_rate"] == 0.0

    async def test_404_body_is_rfc7807(self, client: AsyncClient) -> None:
        """404 body follows RFC 7807 Problem Details format."""
        response = await client.get("/progress/sessions/99999")
        assert response.status_code == 404
        data = response.json()
        assert "type" in data
        assert "title" in data
        assert "detail" in data
