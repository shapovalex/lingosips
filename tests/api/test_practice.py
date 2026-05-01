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
