"""Tests for api/practice.py — practice queue, rating, and evaluate endpoints.

TDD: these tests are written BEFORE implementation.
AC: 1, 2, 3, 6
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from lingosips.api.app import app
from lingosips.services.registry import get_llm_provider, get_speech_evaluator


@pytest.mark.anyio
class TestGetPracticeQueue:
    """Tests for GET /practice/queue (AC: 6)."""

    @pytest.fixture(autouse=True)
    async def truncate_cards(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_returns_empty_list_when_no_due_cards(self, client: AsyncClient) -> None:
        """Empty DB → 200 with []."""
        response = await client.get("/practice/queue")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_due_cards_ordered_by_due_date(
        self, client: AsyncClient, session
    ) -> None:
        """Due cards returned, ordered by due date ascending."""
        from lingosips.db.models import Card, Settings

        # Set active language
        settings = Settings(active_target_language="es")
        session.add(settings)
        # Add two cards with different due dates
        now = datetime.now(UTC)
        card1 = Card(target_word="word1", target_language="es", due=now - timedelta(hours=2))
        card2 = Card(target_word="word2", target_language="es", due=now - timedelta(hours=1))
        session.add(card1)
        session.add(card2)
        await session.commit()

        response = await client.get("/practice/queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["target_word"] == "word1"  # earlier due date first
        assert data[1]["target_word"] == "word2"

    async def test_excludes_future_due_cards(self, client: AsyncClient, session) -> None:
        """Cards with future due date must NOT appear in queue."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        future_card = Card(
            target_word="future_word",
            target_language="es",
            due=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(future_card)
        await session.commit()

        response = await client.get("/practice/queue")
        assert response.status_code == 200
        assert response.json() == []

    async def test_response_has_required_fields(self, client: AsyncClient, session) -> None:
        """Queue cards include all required fields including FSRS state."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="test", target_language="es", due=datetime.now(UTC))
        session.add(card)
        await session.commit()

        response = await client.get("/practice/queue")
        data = response.json()
        assert len(data) == 1
        item = data[0]
        for field in [
            "id",
            "target_word",
            "target_language",
            "due",
            "fsrs_state",
            "stability",
            "difficulty",
            "reps",
            "lapses",
        ]:
            assert field in item, f"Missing field: {field}"

    async def test_filters_by_active_target_language(self, client: AsyncClient, session) -> None:
        """Only cards with active_target_language appear in queue."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="fr")
        session.add(settings)

        now = datetime.now(UTC)
        fr_card = Card(target_word="bonjour", target_language="fr", due=now - timedelta(hours=1))
        es_card = Card(target_word="hola", target_language="es", due=now - timedelta(hours=1))
        session.add(fr_card)
        session.add(es_card)
        await session.commit()

        response = await client.get("/practice/queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["target_word"] == "bonjour"

    async def test_returns_list_not_null_when_empty(self, client: AsyncClient) -> None:
        """Empty result must be [] — never null."""
        response = await client.get("/practice/queue")
        assert response.status_code == 200
        body = response.json()
        assert body is not None
        assert isinstance(body, list)

    async def test_translation_none_serialized_as_null(self, client: AsyncClient, session) -> None:
        """Cards with translation=None serialize correctly as null in the queue response."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(
            target_word="untranslated",
            target_language="es",
            due=datetime.now(UTC),
            translation=None,
        )
        session.add(card)
        await session.commit()

        response = await client.get("/practice/queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["target_word"] == "untranslated"
        assert data[0]["translation"] is None


@pytest.mark.anyio
class TestRateCard:
    """Tests for POST /practice/cards/{card_id}/rate (AC: 2)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_rate_card_good_returns_updated_state(self, client: AsyncClient, session) -> None:
        """POST with rating=3 (Good) → 200 with updated FSRS state."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="hola", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        response = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 3})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == card_id
        assert data["reps"] == 1
        assert data["stability"] > 0
        assert "last_review" in data
        assert data["last_review"] is not None

    async def test_rate_card_again_reschedules_sooner(self, client: AsyncClient, session) -> None:
        """POST with rating=1 (Again) → due is soon (not far in future)."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="adiós", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        response = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 1})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == card_id
        # Again should not push the card very far into the future
        from datetime import datetime, timedelta

        due = datetime.fromisoformat(data["due"])
        # Normalize to naive UTC for comparison (SQLite strips tz info)
        due_naive = due.replace(tzinfo=None) if due.tzinfo else due
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        # Again on new card → stays in Learning steps (minutes, not months)
        assert due_naive < now_naive + timedelta(days=1)

    async def test_rate_card_creates_review_row(self, client: AsyncClient, session) -> None:
        """POST with valid rating → a review row is inserted in the DB."""
        from sqlalchemy import select

        from lingosips.db.models import Card, Review, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="gracias", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        response = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 3})
        assert response.status_code == 200

        # Verify review row was inserted.
        # expire_all() clears the identity-map cache so the next query hits the DB,
        # without rolling back any committed data.
        session.expire_all()
        result = await session.execute(select(Review).where(Review.card_id == card_id))
        reviews = result.scalars().all()
        assert len(reviews) == 1
        assert reviews[0].rating == 3

    async def test_rate_card_not_found_returns_404(self, client: AsyncClient) -> None:
        """POST with non-existent card_id → 404 with RFC 7807 body."""
        response = await client.post("/practice/cards/99999/rate", json={"rating": 3})
        assert response.status_code == 404
        data = response.json()
        # FastAPI serializes HTTPException(detail={...}) as the dict directly
        assert data["type"] == "/errors/card-not-found"
        assert data["title"] == "Card not found"

    async def test_rate_card_invalid_rating_returns_422(self, client: AsyncClient, session) -> None:
        """POST with rating=5 → 422 Unprocessable Entity."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="por favor", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        response = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 5})
        assert response.status_code == 422

    async def test_rate_card_rating_0_returns_422(self, client: AsyncClient, session) -> None:
        """POST with rating=0 → 422 Unprocessable Entity."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="buenas noches", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        response = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 0})
        assert response.status_code == 422

    async def test_queue_empties_after_all_cards_rated_good(
        self, client: AsyncClient, session
    ) -> None:
        """Rate all due cards Good → subsequent GET /practice/queue returns []."""
        from datetime import UTC, datetime, timedelta

        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        now = datetime.now(UTC)
        card = Card(
            target_word="mañana",
            target_language="es",
            due=now - timedelta(hours=1),
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)
        card_id = card.id

        # Confirm card is in queue
        queue_resp = await client.get("/practice/queue")
        assert queue_resp.status_code == 200
        assert len(queue_resp.json()) == 1

        # Rate the card Good — should push due into future
        rate_resp = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 3})
        assert rate_resp.status_code == 200

        # After rating, card should no longer be in queue (due is in future)
        queue_resp2 = await client.get("/practice/queue")
        assert queue_resp2.status_code == 200
        # The queue should be empty or not contain this card
        queue_data = queue_resp2.json()
        card_ids_in_queue = [c["id"] for c in queue_data]
        assert card_id not in card_ids_in_queue


@pytest.mark.anyio
class TestSessionStart:
    """Tests for POST /practice/session/start (AC: 1)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_session_start_returns_due_cards(self, client: AsyncClient, session) -> None:
        """POST /practice/session/start → 200, SessionStartResponse with session_id + cards."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(
            target_word="hola",
            target_language="es",
            due=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(card)
        await session.commit()

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        # Response is now { session_id, cards } not a raw list
        assert "session_id" in data
        assert isinstance(data["session_id"], int)
        assert "cards" in data
        assert isinstance(data["cards"], list)
        assert len(data["cards"]) == 1
        assert data["cards"][0]["target_word"] == "hola"
        # Verify QueueCard shape
        for field in [
            "id",
            "target_word",
            "target_language",
            "due",
            "fsrs_state",
            "stability",
            "difficulty",
            "reps",
            "lapses",
        ]:
            assert field in data["cards"][0], f"Missing field: {field}"

    async def test_session_start_respects_cards_per_session(
        self, client: AsyncClient, session
    ) -> None:
        """POST returns at most cards_per_session cards (limit respected)."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es", cards_per_session=2)
        session.add(settings)
        now = datetime.now(UTC)
        for i in range(5):
            card = Card(
                target_word=f"word{i}",
                target_language="es",
                due=now - timedelta(hours=i + 1),
            )
            session.add(card)
        await session.commit()

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert len(data["cards"]) == 2

    async def test_session_start_empty_when_no_cards_due(
        self, client: AsyncClient, session
    ) -> None:
        """POST returns cards=[] (never null) when no cards are due."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        # Only future cards
        card = Card(
            target_word="futuro",
            target_language="es",
            due=datetime.now(UTC) + timedelta(days=3),
        )
        session.add(card)
        await session.commit()

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert data["cards"] == []
        assert "session_id" in data

    async def test_session_start_filters_by_active_language(
        self, client: AsyncClient, session
    ) -> None:
        """POST only returns cards matching active_target_language."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="fr")
        session.add(settings)
        now = datetime.now(UTC)
        fr_card = Card(target_word="bonjour", target_language="fr", due=now - timedelta(hours=1))
        es_card = Card(target_word="hola", target_language="es", due=now - timedelta(hours=1))
        session.add(fr_card)
        session.add(es_card)
        await session.commit()

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert len(data["cards"]) == 1
        assert data["cards"][0]["target_word"] == "bonjour"

    async def test_session_start_orders_by_due_asc(self, client: AsyncClient, session) -> None:
        """POST returns cards ordered by due date ascending (oldest first)."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        now = datetime.now(UTC)
        card_new = Card(
            target_word="nuevo",
            target_language="es",
            due=now - timedelta(hours=1),
        )
        card_old = Card(
            target_word="antiguo",
            target_language="es",
            due=now - timedelta(hours=5),
        )
        session.add(card_new)
        session.add(card_old)
        await session.commit()

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert len(data["cards"]) == 2
        assert data["cards"][0]["target_word"] == "antiguo"  # oldest due first
        assert data["cards"][1]["target_word"] == "nuevo"


@pytest.mark.anyio
class TestRateCardWithSession:
    """Tests for POST /practice/cards/{card_id}/rate persisting session_id (Story 3.5 AC: 4)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture
    async def card_fixture(self, session):
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="sesión", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        return card

    @pytest.fixture
    async def practice_session_fixture(self, session):
        from lingosips.db.models import PracticeSession

        ps = PracticeSession()
        session.add(ps)
        await session.commit()
        await session.refresh(ps)
        return ps

    async def test_review_has_session_id_when_provided(
        self, client: AsyncClient, session, card_fixture, practice_session_fixture
    ) -> None:
        """POST with session_id → review row has correct session_id."""
        from sqlalchemy import select

        from lingosips.db.models import Review

        card_id = card_fixture.id
        session_id = practice_session_fixture.id

        response = await client.post(
            f"/practice/cards/{card_id}/rate", json={"rating": 3, "session_id": session_id}
        )
        assert response.status_code == 200

        session.expire_all()
        result = await session.execute(select(Review).where(Review.card_id == card_id))
        reviews = result.scalars().all()
        assert len(reviews) == 1
        assert reviews[0].session_id == session_id

    async def test_review_has_null_session_id_when_not_provided(
        self, client: AsyncClient, session, card_fixture
    ) -> None:
        """POST without session_id → review row has session_id=None."""
        from sqlalchemy import select

        from lingosips.db.models import Review

        card_id = card_fixture.id
        response = await client.post(f"/practice/cards/{card_id}/rate", json={"rating": 3})
        assert response.status_code == 200

        session.expire_all()
        result = await session.execute(select(Review).where(Review.card_id == card_id))
        reviews = result.scalars().all()
        assert len(reviews) == 1
        assert reviews[0].session_id is None

    async def test_practice_session_ended_at_updated_on_rating(
        self, client: AsyncClient, session, card_fixture, practice_session_fixture
    ) -> None:
        """POST with session_id → PracticeSession.ended_at is updated."""
        from lingosips.db.models import PracticeSession

        card_id = card_fixture.id
        session_id = practice_session_fixture.id

        response = await client.post(
            f"/practice/cards/{card_id}/rate", json={"rating": 3, "session_id": session_id}
        )
        assert response.status_code == 200

        session.expire_all()
        ps = await session.get(PracticeSession, session_id)
        assert ps is not None
        assert ps.ended_at is not None

    async def test_invalid_session_id_accepted_gracefully(
        self, client: AsyncClient, session, card_fixture
    ) -> None:
        """POST with non-existent session_id → still succeeds (graceful null handling)."""
        card_id = card_fixture.id
        response = await client.post(
            f"/practice/cards/{card_id}/rate", json={"rating": 3, "session_id": 99999}
        )
        assert response.status_code == 200


@pytest.mark.anyio
class TestSessionStartCreatesSession:
    """Tests for POST /practice/session/start creating PracticeSession row (Story 3.5 AC: 4)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_session_start_returns_session_id(self, client: AsyncClient) -> None:
        """POST /practice/session/start → response includes session_id integer."""
        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert isinstance(data["session_id"], int)

    async def test_session_start_returns_cards_field(self, client: AsyncClient, session) -> None:
        """POST /practice/session/start → response includes cards list."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        from datetime import UTC, datetime, timedelta

        card = Card(
            target_word="hola",
            target_language="es",
            due=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(card)
        await session.commit()

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert isinstance(data["cards"], list)
        assert len(data["cards"]) == 1
        assert data["cards"][0]["target_word"] == "hola"

    async def test_session_start_creates_practice_session_row(
        self, client: AsyncClient, session
    ) -> None:
        """POST /practice/session/start creates a PracticeSession row in DB."""

        from lingosips.db.models import PracticeSession

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        session.expire_all()
        ps = await session.get(PracticeSession, session_id)
        assert ps is not None
        assert ps.started_at is not None

    async def test_session_id_is_integer(self, client: AsyncClient) -> None:
        """session_id must be a positive integer."""
        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["session_id"], int)
        assert data["session_id"] > 0

    async def test_empty_queue_still_creates_session(self, client: AsyncClient, session) -> None:
        """Empty due queue still creates a PracticeSession row and returns session_id."""
        from lingosips.db.models import PracticeSession

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["cards"] == []

        session.expire_all()
        ps = await session.get(PracticeSession, data["session_id"])
        assert ps is not None


@pytest.mark.anyio
class TestNextDue:
    """Tests for GET /practice/next-due (AC: 2)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_next_due_returns_earliest_due(self, client: AsyncClient, session) -> None:
        """GET /practice/next-due returns the earliest due datetime."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        now = datetime.now(UTC)
        card_soon = Card(
            target_word="pronto",
            target_language="es",
            due=now + timedelta(hours=2),
        )
        card_later = Card(
            target_word="despues",
            target_language="es",
            due=now + timedelta(days=2),
        )
        session.add(card_soon)
        session.add(card_later)
        await session.commit()

        response = await client.get("/practice/next-due")
        assert response.status_code == 200
        data = response.json()
        assert data["next_due"] is not None
        # The returned next_due should be the earlier one (card_soon, ~2 hours from now)
        returned_due = datetime.fromisoformat(data["next_due"].replace("Z", "+00:00"))
        # Check it's roughly 2 hours from now (within 1 minute of expected)
        now_utc = datetime.now(UTC)
        due_aware = returned_due if returned_due.tzinfo else returned_due.replace(tzinfo=UTC)
        diff = abs(due_aware - now_utc - timedelta(hours=2))
        assert diff < timedelta(minutes=1)

    async def test_next_due_null_when_no_cards(self, client: AsyncClient) -> None:
        """GET /practice/next-due returns {"next_due": null} when no cards exist."""
        response = await client.get("/practice/next-due")
        assert response.status_code == 200
        data = response.json()
        assert data["next_due"] is None

    async def test_next_due_includes_overdue_cards(self, client: AsyncClient, session) -> None:
        """GET /practice/next-due includes past-due cards (overdue = valid next_due)."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        overdue_card = Card(
            target_word="atrasado",
            target_language="es",
            due=datetime.now(UTC) - timedelta(days=2),
        )
        session.add(overdue_card)
        await session.commit()

        response = await client.get("/practice/next-due")
        assert response.status_code == 200
        data = response.json()
        assert data["next_due"] is not None

    async def test_next_due_filters_by_active_language(self, client: AsyncClient, session) -> None:
        """GET /practice/next-due only considers cards in active_target_language."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="fr")
        session.add(settings)
        now = datetime.now(UTC)
        # ES card due very soon — should NOT be returned (wrong language)
        es_card = Card(target_word="hola", target_language="es", due=now + timedelta(hours=1))
        # FR card due later — should be returned
        fr_card = Card(target_word="bonjour", target_language="fr", due=now + timedelta(days=1))
        session.add(es_card)
        session.add(fr_card)
        await session.commit()

        response = await client.get("/practice/next-due")
        assert response.status_code == 200
        data = response.json()
        assert data["next_due"] is not None
        # Should return the FR card's due date (1 day from now), not the ES card (1 hour)
        returned_due = datetime.fromisoformat(data["next_due"].replace("Z", "+00:00"))
        now_utc = datetime.now(UTC)
        due_aware = returned_due if returned_due.tzinfo else returned_due.replace(tzinfo=UTC)
        diff_from_fr = abs(due_aware - now_utc - timedelta(days=1))
        assert diff_from_fr < timedelta(minutes=1)


# ── TestEvaluateAnswer ─────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestEvaluateAnswer:
    """Tests for POST /practice/cards/{card_id}/evaluate (AC: 1, 2, 3)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture
    async def seed_card(self, session):
        """Create a card with a known translation for evaluation tests."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="hola", translation="hello", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        return card

    @pytest.fixture
    async def mock_llm(self):
        """Mock get_llm_provider with a provider returning a fixed explanation."""
        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(return_value="You missed a letter.")
        mock.provider_name = "MockLLM"
        mock.model_name = "mock-model"

        app.dependency_overrides[get_llm_provider] = lambda: mock
        yield mock
        app.dependency_overrides.pop(get_llm_provider, None)

    @pytest.fixture
    async def mock_llm_timeout(self):
        """Mock LLM provider that raises asyncio.TimeoutError."""

        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(side_effect=TimeoutError())
        mock.provider_name = "MockLLM"
        mock.model_name = "mock-model"

        app.dependency_overrides[get_llm_provider] = lambda: mock
        yield mock
        app.dependency_overrides.pop(get_llm_provider, None)

    @pytest.fixture
    async def mock_llm_error(self):
        """Mock LLM provider that raises a generic exception."""
        from lingosips.services.llm.base import AbstractLLMProvider

        mock = AsyncMock(spec=AbstractLLMProvider)
        mock.complete = AsyncMock(side_effect=Exception("LLM unavailable"))
        mock.provider_name = "MockLLM"
        mock.model_name = "mock-model"

        app.dependency_overrides[get_llm_provider] = lambda: mock
        yield mock
        app.dependency_overrides.pop(get_llm_provider, None)

    async def test_evaluate_correct_answer_returns_success(
        self, client: AsyncClient, seed_card, mock_llm
    ) -> None:
        """Exact match → is_correct=True, suggested_rating=3, no LLM call."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is True
        assert data["suggested_rating"] == 3
        assert data["explanation"] is None
        assert data["highlighted_chars"] == []
        assert data["correct_value"] == "hello"
        mock_llm.complete.assert_not_called()

    async def test_evaluate_wrong_answer_returns_diff_and_explanation(
        self, client: AsyncClient, seed_card, mock_llm
    ) -> None:
        """Wrong answer → is_correct=False, char diff populated, explanation set."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "helo"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is False
        assert data["suggested_rating"] == 1
        assert data["explanation"] == "You missed a letter."
        assert len(data["highlighted_chars"]) == len("helo")
        # Check shape of each char highlight
        for hc in data["highlighted_chars"]:
            assert "char" in hc
            assert "correct" in hc
        mock_llm.complete.assert_called_once()

    async def test_evaluate_missing_answer_returns_422(
        self, client: AsyncClient, seed_card
    ) -> None:
        """Missing answer field → 422 Unprocessable Entity."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={},
        )
        assert response.status_code == 422

    async def test_evaluate_blank_answer_returns_422(
        self, client: AsyncClient, seed_card, mock_llm
    ) -> None:
        """Whitespace-only answer → 422 (not_whitespace_only validator fires)."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "   "},
        )
        assert response.status_code == 422

    async def test_evaluate_card_not_found_returns_404(self, client: AsyncClient, mock_llm) -> None:
        """Non-existent card_id → 404 with RFC 7807 body."""
        response = await client.post(
            "/practice/cards/99999/evaluate",
            json={"answer": "hello"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "/errors/card-not-found"
        assert data["title"] == "Card not found"

    async def test_evaluate_llm_timeout_returns_null_explanation(
        self, client: AsyncClient, seed_card, mock_llm_timeout
    ) -> None:
        """LLM timeout → explanation=null, is_correct=False, session continues."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "helo"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is False
        assert data["explanation"] is None
        assert data["suggested_rating"] == 1

    async def test_evaluate_llm_error_returns_null_explanation(
        self, client: AsyncClient, seed_card, mock_llm_error
    ) -> None:
        """LLM generic error → explanation=null, is_correct=False, session continues."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "helo"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is False
        assert data["explanation"] is None

    async def test_evaluate_case_insensitive_correct(
        self, client: AsyncClient, seed_card, mock_llm
    ) -> None:
        """Case-insensitive match → is_correct=True."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "HELLO"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is True
        assert data["suggested_rating"] == 3

    async def test_evaluate_card_with_no_translation_returns_422(
        self, client: AsyncClient, session, mock_llm
    ) -> None:
        """Card without translation → 422 (write mode requires a known translation)."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="untranslated", translation=None, target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        response = await client.post(
            f"/practice/cards/{card.id}/evaluate",
            json={"answer": "anything"},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "/errors/card-missing-translation"

    async def test_evaluate_answer_is_stripped_by_validator(
        self, client: AsyncClient, seed_card, mock_llm
    ) -> None:
        """Padded answer '  hello  ' is normalised to 'hello' by the validator → is_correct=True."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/evaluate",
            json={"answer": "  hello  "},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_correct"] is True  # stripped answer matches translation


@pytest.mark.anyio
class TestSentenceCardQueue:
    """Tests for AC: 2 — QueueCard includes card_type, forms, example_sentences."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture
    async def sentence_card_fixture(self, session):
        """Create a sentence card with forms/example_sentences in DB."""
        import json

        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(
            target_word="no te hagas el tonto",
            translation="don't play dumb",
            target_language="es",
            card_type="sentence",
            forms=json.dumps(
                {
                    "gender": None,
                    "article": None,
                    "plural": None,
                    "conjugations": {},
                    "register_context": "informal, River Plate Spanish",
                }
            ),
            example_sentences=json.dumps(
                ["No te hagas el tonto, te vi.", "Siempre se hace el tonto."]
            ),
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)
        return card

    @pytest.fixture
    async def word_card_fixture(self, session):
        """Create a standard word card in DB."""
        import json

        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(
            target_word="melancólico",
            translation="melancholic",
            target_language="es",
            card_type="word",
            forms=json.dumps(
                {
                    "gender": "masculine",
                    "article": "el",
                    "plural": "melancólicos",
                    "conjugations": {},
                    "register_context": None,
                }
            ),
            example_sentences=json.dumps(["Tenía un aire melancólico.", "Era un día melancólico."]),
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)
        return card

    async def test_session_includes_card_type_in_response(
        self, client: AsyncClient, sentence_card_fixture
    ) -> None:
        """GET /practice/session/start includes card_type field (AC: 2)."""
        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert len(data["cards"]) > 0
        assert "card_type" in data["cards"][0]
        assert data["cards"][0]["card_type"] == "sentence"

    async def test_session_includes_forms_and_example_sentences(
        self, client: AsyncClient, sentence_card_fixture
    ) -> None:
        """Queue response includes forms (JSON string) and example_sentences (AC: 2)."""
        response = await client.post("/practice/session/start")
        data = response.json()
        assert "forms" in data["cards"][0]
        assert "example_sentences" in data["cards"][0]
        assert data["cards"][0]["forms"] is not None
        assert data["cards"][0]["example_sentences"] is not None

    async def test_word_card_type_defaults_in_response(
        self, client: AsyncClient, word_card_fixture
    ) -> None:
        """Existing word cards show card_type='word' in queue response (AC: 6 backwards compat)."""
        response = await client.post("/practice/session/start")
        data = response.json()
        assert len(data["cards"]) > 0
        assert data["cards"][0]["card_type"] == "word"

    async def test_queue_endpoint_includes_card_type(
        self, client: AsyncClient, sentence_card_fixture
    ) -> None:
        """GET /practice/queue also exposes card_type (AC: 2)."""
        response = await client.get("/practice/queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "card_type" in data[0]


# ── TestEvaluateSpeak ─────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestEvaluateSpeak:
    """Tests for POST /practice/cards/{card_id}/speak (AC: 5, 7, 9)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    @pytest.fixture
    async def seed_card(self, session):
        """Create a card for speak evaluation tests."""
        from lingosips.db.models import Card, Settings

        settings = Settings(active_target_language="es")
        session.add(settings)
        card = Card(target_word="agua", translation="water", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)
        return card

    @pytest.fixture
    def mock_speech_evaluator(self):
        """Mock get_speech_evaluator with a provider that returns a fixed SyllableResult."""
        from lingosips.services.speech.base import SyllableDetail, SyllableResult
        from lingosips.services.speech.whisper_local import WhisperLocalProvider

        class MockEvaluator(WhisperLocalProvider):
            @property
            def provider_name(self) -> str:
                return "Local Whisper"

            async def evaluate_pronunciation(self, audio, target, language):
                return SyllableResult(
                    overall_correct=True,
                    syllables=[
                        SyllableDetail(syllable="a", correct=True, score=1.0),
                        SyllableDetail(syllable="gua", correct=True, score=1.0),
                    ],
                    correction_message=None,
                )

        app.dependency_overrides[get_speech_evaluator] = lambda: MockEvaluator()
        yield
        app.dependency_overrides.pop(get_speech_evaluator, None)

    @pytest.fixture
    def mock_speech_evaluator_azure(self):
        """Mock get_speech_evaluator returning Azure-like provider."""
        from lingosips.services.speech.azure import AzureSpeechProvider
        from lingosips.services.speech.base import SyllableDetail, SyllableResult

        class MockAzureEvaluator(AzureSpeechProvider):
            def __init__(self):
                super().__init__(api_key="mock-key", region="eastus")

            async def evaluate_pronunciation(self, audio, target, language):
                return SyllableResult(
                    overall_correct=True,
                    syllables=[SyllableDetail(syllable="test", correct=True, score=0.9)],
                    correction_message=None,
                )

        app.dependency_overrides[get_speech_evaluator] = lambda: MockAzureEvaluator()
        yield
        app.dependency_overrides.pop(get_speech_evaluator, None)

    @pytest.fixture
    def mock_speech_timeout(self):
        """Mock provider that raises RuntimeError (simulating timeout)."""
        from lingosips.services.speech.whisper_local import WhisperLocalProvider

        class TimeoutEvaluator(WhisperLocalProvider):
            async def evaluate_pronunciation(self, audio, target, language):
                raise RuntimeError("Speech evaluation timed out — provider: Local Whisper")

        app.dependency_overrides[get_speech_evaluator] = lambda: TimeoutEvaluator()
        yield
        app.dependency_overrides.pop(get_speech_evaluator, None)

    @pytest.fixture
    def mock_whisper_not_ready(self):
        """Mock get_speech_evaluator to raise 503 (model not downloaded)."""
        from fastapi import HTTPException

        def raise_503():
            raise HTTPException(
                status_code=503,
                detail={
                    "type": "/errors/speech-model-downloading",
                    "title": "Speech model is downloading",
                    "detail": "Subscribe to /models/download/progress for progress",
                    "status": 503,
                },
            )

        app.dependency_overrides[get_speech_evaluator] = raise_503
        yield
        app.dependency_overrides.pop(get_speech_evaluator, None)

    async def test_returns_syllable_result_shape(
        self, client: AsyncClient, seed_card, mock_speech_evaluator
    ) -> None:
        """POST with valid WAV bytes → 200 with SpeechEvaluationResponse."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "overall_correct" in data
        assert "syllables" in data
        assert "correction_message" in data
        assert "provider_used" in data
        assert isinstance(data["syllables"], list)

    async def test_whisper_provider_used_when_no_azure(
        self, client: AsyncClient, seed_card, mock_speech_evaluator
    ) -> None:
        """When Whisper mock is used → provider_used contains 'whisper'."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "whisper" in data["provider_used"].lower()

    async def test_azure_provider_used_when_configured(
        self, client: AsyncClient, seed_card, mock_speech_evaluator_azure
    ) -> None:
        """When Azure mock is used → provider_used contains 'azure'."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "azure" in data["provider_used"].lower()

    async def test_empty_audio_returns_400(
        self, client: AsyncClient, seed_card, mock_speech_evaluator
    ) -> None:
        """POST with empty body → 400."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["type"] == "/errors/empty-audio"

    async def test_card_not_found_returns_404(
        self, client: AsyncClient, mock_speech_evaluator
    ) -> None:
        """Non-existent card_id → 404 with RFC 7807 body."""
        response = await client.post(
            "/practice/cards/99999/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "/errors/card-not-found"
        assert data["title"] == "Card not found"

    async def test_speech_timeout_returns_422(
        self, client: AsyncClient, seed_card, mock_speech_timeout
    ) -> None:
        """RuntimeError from provider → 422 with RFC 7807 body."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "/errors/speech-evaluation-failed"

    async def test_503_when_whisper_model_not_ready(
        self, client: AsyncClient, seed_card, mock_whisper_not_ready
    ) -> None:
        """503 from get_speech_evaluator → propagated to client."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 503

    async def test_syllables_count_matches_mock(
        self, client: AsyncClient, seed_card, mock_speech_evaluator
    ) -> None:
        """Mock returns 2 syllables → response has 2 syllables."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["syllables"]) == 2

    async def test_syllable_detail_shape(
        self, client: AsyncClient, seed_card, mock_speech_evaluator
    ) -> None:
        """Each syllable detail has syllable, correct, score fields."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        for detail in data["syllables"]:
            assert "syllable" in detail
            assert "correct" in detail
            assert "score" in detail

    async def test_overall_correct_true_when_mock_returns_correct(
        self, client: AsyncClient, seed_card, mock_speech_evaluator
    ) -> None:
        """Mock returns overall_correct=True → response reflects that."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["overall_correct"] is True
        assert data["correction_message"] is None

    @pytest.fixture
    def mock_speech_evaluator_incorrect(self):
        """Mock get_speech_evaluator returning overall_correct=False with correction_message."""
        from lingosips.services.speech.base import SyllableDetail, SyllableResult
        from lingosips.services.speech.whisper_local import WhisperLocalProvider

        class IncorrectEvaluator(WhisperLocalProvider):
            @property
            def provider_name(self) -> str:
                return "Local Whisper"

            async def evaluate_pronunciation(self, audio, target, language):
                return SyllableResult(
                    overall_correct=False,
                    syllables=[
                        SyllableDetail(syllable="a", correct=False, score=0.2),
                        SyllableDetail(syllable="gua", correct=True, score=0.8),
                    ],
                    correction_message='Heard: "awa" — expected: "agua"',
                )

        app.dependency_overrides[get_speech_evaluator] = lambda: IncorrectEvaluator()
        yield
        app.dependency_overrides.pop(get_speech_evaluator, None)

    async def test_incorrect_pronunciation_returns_correction_message(
        self, client: AsyncClient, seed_card, mock_speech_evaluator_incorrect
    ) -> None:
        """Mock returns overall_correct=False → correction_message non-null (AC9 failure path)."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["overall_correct"] is False
        assert data["correction_message"] is not None
        assert len(data["correction_message"]) > 0

    async def test_incorrect_syllables_have_false_correct_flag(
        self, client: AsyncClient, seed_card, mock_speech_evaluator_incorrect
    ) -> None:
        """Mock returns mixed syllable correctness → response syllables reflect that."""
        card_id = seed_card.id
        response = await client.post(
            f"/practice/cards/{card_id}/speak",
            content=b"RIFF_fake_wav_audio",
            headers={"Content-Type": "audio/wav"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["syllables"]) == 2
        # First syllable incorrect, second correct
        assert data["syllables"][0]["correct"] is False
        assert data["syllables"][1]["correct"] is True


@pytest.mark.anyio
class TestSessionMode:
    """Tests for mode param on POST /practice/session/start (AC: 7, Story 5.1)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_start_session_with_mode_stored(
        self, client: AsyncClient, session
    ) -> None:
        """POST /practice/session/start?mode=write → practice_session.mode == 'write'."""
        from lingosips.db.models import PracticeSession

        response = await client.post("/practice/session/start?mode=write")
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]

        # Verify the mode was persisted in the DB
        ps = await session.get(PracticeSession, session_id)
        assert ps is not None
        assert ps.mode == "write"

    async def test_start_session_without_mode_defaults_to_null(
        self, client: AsyncClient, session
    ) -> None:
        """POST /practice/session/start (no mode) → practice_session.mode is None."""
        from lingosips.db.models import PracticeSession

        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]

        ps = await session.get(PracticeSession, session_id)
        assert ps is not None
        assert ps.mode is None
