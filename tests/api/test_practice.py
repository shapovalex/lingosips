"""Tests for api/practice.py — GET /practice/queue endpoint.

TDD: these tests are written BEFORE implementation to drive api/practice.py.
AC: 6
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text


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
