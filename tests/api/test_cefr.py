"""Tests for api/cefr.py — GET /cefr/profile endpoint.

TDD: written BEFORE implementation.
AC: 1–6 (Story 5.1)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.anyio
class TestGetCefrProfile:
    """Tests for GET /cefr/profile (AC: 1–6)."""

    @pytest.fixture(autouse=True)
    async def truncate_and_clear_cache(self, test_engine) -> None:
        """Truncate tables and clear CEFR cache before/after each test."""
        from lingosips.core import cefr as core_cefr

        core_cefr._profile_cache.clear()
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))
        yield
        core_cefr._profile_cache.clear()

    async def test_missing_target_language_returns_422(self, client: AsyncClient) -> None:
        """Missing target_language query param → 422 with RFC 7807 validation body (AC5)."""
        response = await client.get("/cefr/profile")
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "/errors/validation"
        # field path contains "target_language"
        errors = data.get("errors", [])
        assert any("target_language" in e.get("field", "") for e in errors)

    async def test_empty_profile_fewer_than_10_reviews(self, client: AsyncClient) -> None:
        """Fewer than 10 reviews → level: null, explanation prompts to practice more (AC3)."""
        response = await client.get("/cefr/profile?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert data["level"] is None
        assert "Practice more" in data["explanation"]

    async def test_correct_a1_level_for_seeded_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """40 Review-state cards + 15 reviews → level: A1 (AC1, AC2)."""
        from sqlalchemy import select

        from lingosips.db.models import Card, Review

        for i in range(40):
            session.add(Card(target_word=f"word{i}", target_language="es", fsrs_state="Review"))
        await session.commit()

        cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        db_cards = cards_result.scalars().all()
        for c in db_cards[:15]:
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        response = await client.get("/cefr/profile?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "A1"
        assert data["vocabulary_breadth"] == 40

    async def test_correct_b1_level_for_seeded_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """200 Review-state cards + 10 reviews → level: B1 (AC2)."""
        from sqlalchemy import select

        from lingosips.db.models import Card, Review

        for i in range(200):
            session.add(Card(target_word=f"word{i}", target_language="es", fsrs_state="Review"))
        await session.commit()

        cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        db_cards = cards_result.scalars().all()
        for c in db_cards[:10]:
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        response = await client.get("/cefr/profile?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "B1"
        assert data["vocabulary_breadth"] == 200

    async def test_correct_c1_level_for_seeded_data(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """1300 Review-state cards + 10 reviews → level: C1 (AC2)."""
        from sqlalchemy import select

        from lingosips.db.models import Card, Review

        for i in range(1300):
            session.add(Card(target_word=f"word{i}", target_language="es", fsrs_state="Review"))
        await session.commit()

        cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        db_cards = cards_result.scalars().all()
        for c in db_cards[:10]:
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        response = await client.get("/cefr/profile?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "C1"

    async def test_language_scoping_excludes_other_languages(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Spanish cards do NOT affect French profile (AC5)."""
        from sqlalchemy import select

        from lingosips.db.models import Card, Review

        # Seed 40 Spanish cards + 15 reviews
        for i in range(40):
            session.add(Card(target_word=f"es{i}", target_language="es", fsrs_state="Review"))
        await session.commit()

        cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        db_cards = cards_result.scalars().all()
        for c in db_cards[:15]:
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        # French profile must be null (no French data)
        response = await client.get("/cefr/profile?target_language=fr")
        assert response.status_code == 200
        data = response.json()
        assert data["level"] is None
        assert data["vocabulary_breadth"] == 0

    async def test_cache_returns_same_result_without_requery(self, client: AsyncClient) -> None:
        """Two consecutive calls return same result; cache is populated after first call."""
        from lingosips.core import cefr as core_cefr

        response1 = await client.get("/cefr/profile?target_language=es")
        assert response1.status_code == 200
        # Cache should now be populated
        assert "es" in core_cefr._profile_cache

        response2 = await client.get("/cefr/profile?target_language=es")
        assert response2.status_code == 200
        assert response1.json() == response2.json()

    async def test_cache_invalidated_after_rating(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """After rating a card, cache is invalidated; next GET recomputes (AC4)."""
        from sqlalchemy import select

        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card, Review

        # Seed 40 Review-state cards for vocabulary breadth
        for i in range(40):
            session.add(Card(target_word=f"vocab{i}", target_language="es", fsrs_state="Review"))
        # Seed one New-state card for rating (New state works with FSRS at stability=0.0)
        rateable = Card(target_word="rateable", target_language="es", fsrs_state="New")
        session.add(rateable)
        await session.commit()
        await session.refresh(rateable)

        # Seed 15 reviews to reach non-null profile
        cards_result = await session.execute(
            select(Card).where(Card.target_language == "es", Card.fsrs_state == "Review")
        )
        review_cards = cards_result.scalars().all()
        for c in review_cards[:15]:
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        # First GET — populates cache
        r1 = await client.get("/cefr/profile?target_language=es")
        assert r1.status_code == 200
        assert "es" in core_cefr._profile_cache

        # Rate the New-state card → should invalidate cache
        r_rate = await client.post(f"/practice/cards/{rateable.id}/rate", json={"rating": 3})
        assert r_rate.status_code == 200

        # Cache must be cleared after rating
        assert "es" not in core_cefr._profile_cache

    async def test_response_shape_with_valid_profile(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Response contains all required fields with correct types (AC1, AC2)."""
        from sqlalchemy import select

        from lingosips.db.models import Card, Review

        for i in range(40):
            session.add(Card(target_word=f"word{i}", target_language="es", fsrs_state="Review"))
        await session.commit()
        cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        db_cards = cards_result.scalars().all()
        for c in db_cards[:15]:
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        response = await client.get("/cefr/profile?target_language=es")
        assert response.status_code == 200
        data = response.json()

        # All required fields present
        for field in [
            "level",
            "vocabulary_breadth",
            "grammar_coverage",
            "recall_rate_by_card_type",
            "active_passive_ratio",
            "explanation",
        ]:
            assert field in data, f"Missing field: {field}"

        assert isinstance(data["vocabulary_breadth"], int)
        assert isinstance(data["grammar_coverage"], int)
        assert isinstance(data["recall_rate_by_card_type"], dict)
        assert isinstance(data["explanation"], str)

    async def test_large_review_log_returns_within_500ms(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """GET /cefr/profile responds within 500ms with 1000+ rows (AC6)."""
        import time

        from sqlalchemy import select

        from lingosips.db.models import Card, Review

        # Seed 100 cards with 1000 reviews (1000+ rows in the review log — AC6)
        for i in range(100):
            session.add(Card(target_word=f"perf{i}", target_language="es", fsrs_state="Review"))
        await session.commit()
        cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        db_cards = cards_result.scalars().all()

        # Seed 1000+ reviews across the cards
        for i in range(1000):
            c = db_cards[i % len(db_cards)]
            session.add(
                Review(
                    card_id=c.id,
                    rating=3,
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        start = time.monotonic()
        response = await client.get("/cefr/profile?target_language=es")
        elapsed_ms = (time.monotonic() - start) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 500, f"Response took {elapsed_ms:.0f}ms, expected < 500ms"
