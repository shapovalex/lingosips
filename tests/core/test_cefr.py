"""Tests for core/cefr.py — CEFR profile computation engine.

TDD: written BEFORE implementation.
AC: 1–7 (Story 5.1)
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# ── TestComputeVocabularyBreadth ──────────────────────────────────────────────


@pytest.mark.anyio
class TestComputeVocabularyBreadth:
    """Tests for core.cefr.compute_vocabulary_breadth (AC: 1)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        from sqlalchemy import text

        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    async def test_counts_review_and_mature_state_cards(self, session: AsyncSession) -> None:
        """Cards in Review or Mature state are counted as active vocabulary."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(Card(target_word="review_card", target_language="es", fsrs_state="Review"))
        session.add(Card(target_word="mature_card", target_language="es", fsrs_state="Mature"))
        await session.commit()

        result = await core_cefr.compute_vocabulary_breadth(session, "es")
        assert result == 2

    async def test_excludes_new_and_learning_state_cards(self, session: AsyncSession) -> None:
        """Cards in New/Learning/Relearning state are NOT counted."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(Card(target_word="new_card", target_language="es", fsrs_state="New"))
        session.add(Card(target_word="learning_card", target_language="es", fsrs_state="Learning"))
        session.add(
            Card(target_word="relearning_card", target_language="es", fsrs_state="Relearning")
        )
        await session.commit()

        result = await core_cefr.compute_vocabulary_breadth(session, "es")
        assert result == 0

    async def test_scopes_to_target_language(self, session: AsyncSession) -> None:
        """Only cards with the specified target_language are counted."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(Card(target_word="es_card", target_language="es", fsrs_state="Review"))
        session.add(Card(target_word="fr_card", target_language="fr", fsrs_state="Review"))
        await session.commit()

        es_result = await core_cefr.compute_vocabulary_breadth(session, "es")
        fr_result = await core_cefr.compute_vocabulary_breadth(session, "fr")
        assert es_result == 1
        assert fr_result == 1

    async def test_returns_zero_for_empty_db(self, session: AsyncSession) -> None:
        """Empty database returns 0."""
        from lingosips.core import cefr as core_cefr

        result = await core_cefr.compute_vocabulary_breadth(session, "es")
        assert result == 0


# ── TestComputeGrammarCoverage ────────────────────────────────────────────────


@pytest.mark.anyio
class TestComputeGrammarCoverage:
    """Tests for core.cefr.compute_grammar_coverage (AC: 1)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        from sqlalchemy import text

        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    async def test_counts_distinct_form_type_keys(self, session: AsyncSession) -> None:
        """Counts unique top-level keys across all cards' forms JSON."""
        import json

        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(
            Card(
                target_word="gato",
                target_language="es",
                forms=json.dumps({"gender": "masculine", "plural": "gatos"}),
            )
        )
        session.add(
            Card(
                target_word="correr",
                target_language="es",
                forms=json.dumps({"conjugations": {"yo": "corro"}, "infinitive": "correr"}),
            )
        )
        await session.commit()

        # distinct keys: gender, plural, conjugations, infinitive = 4
        result = await core_cefr.compute_grammar_coverage(session, "es")
        assert result == 4

    async def test_handles_null_forms(self, session: AsyncSession) -> None:
        """Cards with null forms are skipped — no crash, zero forms contribution."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(Card(target_word="word", target_language="es", forms=None))
        await session.commit()

        result = await core_cefr.compute_grammar_coverage(session, "es")
        assert result == 0

    async def test_handles_malformed_json(self, session: AsyncSession) -> None:
        """Cards with invalid JSON forms are skipped — no crash."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(Card(target_word="bad", target_language="es", forms="not-valid-json{"))
        await session.commit()

        result = await core_cefr.compute_grammar_coverage(session, "es")
        assert result == 0

    async def test_scopes_to_target_language(self, session: AsyncSession) -> None:
        """Only forms from cards with the specified language are counted."""
        import json

        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card

        session.add(
            Card(
                target_word="es_word",
                target_language="es",
                forms=json.dumps({"gender": "masculine"}),
            )
        )
        session.add(
            Card(target_word="fr_word", target_language="fr", forms=json.dumps({"article": "le"}))
        )
        await session.commit()

        es_result = await core_cefr.compute_grammar_coverage(session, "es")
        assert es_result == 1  # only "gender"


# ── TestComputeRecallRateByCardType ───────────────────────────────────────────


@pytest.mark.anyio
class TestComputeRecallRateByCardType:
    """Tests for core.cefr.compute_recall_rate_by_card_type (AC: 1)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        from sqlalchemy import text

        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    async def test_returns_correct_rate_by_card_type(self, session: AsyncSession) -> None:
        """Recall rate = correct / total per card_type for last 30 days."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card, Review

        card = Card(target_word="w", target_language="es", card_type="word")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        now = datetime.now(UTC)
        # 3 reviews: 2 good (rating >= 3), 1 fail
        for rating in [3, 4, 1]:
            session.add(
                Review(
                    card_id=card.id,
                    rating=rating,
                    reviewed_at=now - timedelta(days=1),
                    stability_after=1.0,
                    difficulty_after=5.0,
                    fsrs_state_after="Review",
                    reps_after=1,
                    lapses_after=0,
                )
            )
        await session.commit()

        result = await core_cefr.compute_recall_rate_by_card_type(session, "es")
        assert "word" in result
        assert abs(result["word"] - 2 / 3) < 0.001

    async def test_ignores_reviews_older_than_30_days(self, session: AsyncSession) -> None:
        """Reviews older than 30 days are excluded."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card, Review

        card = Card(target_word="old", target_language="es", card_type="word")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        old_date = datetime.now(UTC) - timedelta(days=31)
        session.add(
            Review(
                card_id=card.id,
                rating=3,
                reviewed_at=old_date,
                stability_after=1.0,
                difficulty_after=5.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        result = await core_cefr.compute_recall_rate_by_card_type(session, "es")
        assert result == {}

    async def test_returns_empty_dict_when_no_reviews(self, session: AsyncSession) -> None:
        """No reviews → empty dict (not null, not error)."""
        from lingosips.core import cefr as core_cefr

        result = await core_cefr.compute_recall_rate_by_card_type(session, "es")
        assert result == {}


# ── TestComputeActivePassiveRatio ─────────────────────────────────────────────


@pytest.mark.anyio
class TestComputeActivePassiveRatio:
    """Tests for core.cefr.compute_active_passive_ratio (AC: 1)."""

    @pytest.fixture(autouse=True)
    async def truncate_tables(self, test_engine) -> None:
        from sqlalchemy import text

        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))

    async def test_returns_correct_ratio(self, session: AsyncSession) -> None:
        """Returns active sessions / total sessions for target_language."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card, PracticeSession, Review

        card = Card(target_word="w", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # 1 active session (write mode)
        ps_active = PracticeSession(mode="write")
        session.add(ps_active)
        # 1 passive session (self_assess)
        ps_passive = PracticeSession(mode="self_assess")
        session.add(ps_passive)
        await session.commit()
        await session.refresh(ps_active)
        await session.refresh(ps_passive)

        session.add(
            Review(
                card_id=card.id,
                rating=3,
                session_id=ps_active.id,
                stability_after=1.0,
                difficulty_after=5.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        session.add(
            Review(
                card_id=card.id,
                rating=3,
                session_id=ps_passive.id,
                stability_after=1.0,
                difficulty_after=5.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        result = await core_cefr.compute_active_passive_ratio(session, "es")
        assert result is not None
        assert abs(result - 0.5) < 0.001

    async def test_returns_none_when_no_sessions_with_mode_data(
        self, session: AsyncSession
    ) -> None:
        """Returns None when no sessions have mode data (no reviews linked to sessions)."""
        from lingosips.core import cefr as core_cefr

        result = await core_cefr.compute_active_passive_ratio(session, "es")
        assert result is None

    async def test_treats_null_mode_as_self_assess(self, session: AsyncSession) -> None:
        """Sessions with null mode are treated as self_assess (passive)."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card, PracticeSession, Review

        card = Card(target_word="w", target_language="es")
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # Session with null mode — should count as passive
        ps_null = PracticeSession(mode=None)
        session.add(ps_null)
        await session.commit()
        await session.refresh(ps_null)

        session.add(
            Review(
                card_id=card.id,
                rating=3,
                session_id=ps_null.id,
                stability_after=1.0,
                difficulty_after=5.0,
                fsrs_state_after="Review",
                reps_after=1,
                lapses_after=0,
            )
        )
        await session.commit()

        result = await core_cefr.compute_active_passive_ratio(session, "es")
        # 0 active sessions / 1 total session = 0.0
        assert result is not None
        assert result == 0.0


# ── TestMapToCefrLevel ────────────────────────────────────────────────────────


class TestMapToCefrLevel:
    """Tests for core.cefr.map_to_cefr_level (AC: 2, 3)."""

    def test_a1_threshold(self) -> None:
        """49 active words → A1."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(49, 0, 15)
        assert result == "A1"

    def test_a2_threshold(self) -> None:
        """50 active words → A2."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(50, 0, 15)
        assert result == "A2"

    def test_b1_threshold(self) -> None:
        """150 active words → B1."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(150, 0, 15)
        assert result == "B1"

    def test_b2_threshold(self) -> None:
        """500 active words → B2."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(500, 0, 15)
        assert result == "B2"

    def test_c1_threshold(self) -> None:
        """1200 active words → C1."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(1200, 0, 15)
        assert result == "C1"

    def test_c2_threshold(self) -> None:
        """2500+ active words → C2."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(2500, 0, 15)
        assert result == "C2"

    def test_returns_none_when_fewer_than_10_reviews(self) -> None:
        """< 10 reviews → None (no valid estimate)."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(100, 0, 9)
        assert result is None

    def test_grammar_boost_advances_level_when_vocab_near_upper_threshold(self) -> None:
        """Grammar coverage >= 5 and vocab >= 80% of next threshold → advance one level."""
        from lingosips.core import cefr as core_cefr

        # B1 threshold: 150–499. 80% of 500 = 400. vocab=450 >= 400, grammar=5 → B2
        result = core_cefr.map_to_cefr_level(450, 5, 15)
        assert result == "B2"

    def test_grammar_boost_not_applied_when_vocab_below_80_percent(self) -> None:
        """Grammar boost NOT applied when vocab < 80% of next level threshold."""
        from lingosips.core import cefr as core_cefr

        # B1 threshold: 150–499. 80% of 500 = 400. vocab=200 < 400 → stays B1
        result = core_cefr.map_to_cefr_level(200, 5, 15)
        assert result == "B1"

    def test_grammar_boost_not_applied_when_grammar_below_5(self) -> None:
        """Grammar boost NOT applied when grammar_coverage < 5."""
        from lingosips.core import cefr as core_cefr

        # vocab=450 >= 400 (80% of 500), but grammar=4 < 5 → stays B1
        result = core_cefr.map_to_cefr_level(450, 4, 15)
        assert result == "B1"

    def test_grammar_boost_capped_at_c2(self) -> None:
        """Grammar boost cannot advance beyond C2."""
        from lingosips.core import cefr as core_cefr

        # C1 threshold: 1200–2499. 80% of 2500 = 2000. vocab=2200 >= 2000, grammar=5 → C2
        result = core_cefr.map_to_cefr_level(2200, 5, 15)
        assert result == "C2"

    def test_grammar_boost_fires_at_exact_80_percent_boundary(self) -> None:
        """Grammar boost triggers when vocab is exactly 80% of next threshold (inclusive)."""
        from lingosips.core import cefr as core_cefr

        # A1 threshold: 0–49. 80% of 50 = 40. vocab=40 >= 40, grammar=5 → A2
        result = core_cefr.map_to_cefr_level(40, 5, 15)
        assert result == "A2"

    def test_grammar_boost_does_not_fire_one_below_80_percent_boundary(self) -> None:
        """Grammar boost does NOT trigger when vocab is one below 80% boundary."""
        from lingosips.core import cefr as core_cefr

        # A1 threshold: 0–49. 80% of 50 = 40. vocab=39 < 40, grammar=5 → stays A1
        result = core_cefr.map_to_cefr_level(39, 5, 15)
        assert result == "A1"

    def test_zero_vocab_with_sufficient_reviews_returns_a1(self) -> None:
        """vocab_breadth=0 with enough reviews maps to A1 (not null)."""
        from lingosips.core import cefr as core_cefr

        result = core_cefr.map_to_cefr_level(0, 0, 10)
        assert result == "A1"


# ── TestGetCefrProfile ────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestGetCefrProfile:
    """Tests for core.cefr.get_profile (AC: 2, 3, 4)."""

    @pytest.fixture(autouse=True)
    async def truncate_and_clear_cache(self, test_engine) -> None:
        from sqlalchemy import text

        from lingosips.core import cefr as core_cefr

        core_cefr._profile_cache.clear()
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM practice_sessions"))
            await conn.execute(text("DELETE FROM cards"))
        yield
        core_cefr._profile_cache.clear()

    async def test_returns_null_level_when_fewer_than_10_reviews(
        self, session: AsyncSession
    ) -> None:
        """< 10 reviews → level=None, explanation contains 'Practice more'."""
        from lingosips.core import cefr as core_cefr

        result = await core_cefr.get_profile("es", session)
        assert result.level is None
        assert "Practice more" in result.explanation

    async def test_cached_result_returned_on_second_call(self, session: AsyncSession) -> None:
        """Second call returns cached result without hitting DB again."""
        from lingosips.core import cefr as core_cefr

        # First call — populates cache
        await core_cefr.get_profile("es", session)

        # Inject sentinel into cache to verify it's returned on second call
        from lingosips.core.cefr import CefrProfile

        sentinel = CefrProfile(
            level="A1",
            vocabulary_breadth=42,
            grammar_coverage=0,
            recall_rate_by_card_type={},
            active_passive_ratio=None,
            explanation="cached",
        )
        core_cefr._profile_cache["es"] = sentinel

        profile2 = await core_cefr.get_profile("es", session)
        assert profile2 is sentinel

    async def test_cache_invalidated_by_invalidate_profile_cache(
        self, session: AsyncSession
    ) -> None:
        """invalidate_profile_cache removes the cached entry."""
        from lingosips.core import cefr as core_cefr
        from lingosips.core.cefr import CefrProfile

        # Seed cache
        core_cefr._profile_cache["es"] = CefrProfile(
            level="A1",
            vocabulary_breadth=10,
            grammar_coverage=0,
            recall_rate_by_card_type={},
            active_passive_ratio=None,
            explanation="cached",
        )
        core_cefr.invalidate_profile_cache("es")
        assert "es" not in core_cefr._profile_cache

    async def test_profile_scoped_to_language(self, session: AsyncSession) -> None:
        """Profile for 'es' does not include 'fr' cards."""
        from lingosips.core import cefr as core_cefr
        from lingosips.db.models import Card, Review

        # Seed 40 es cards + 15 reviews
        for i in range(40):
            session.add(Card(target_word=f"es{i}", target_language="es", fsrs_state="Review"))
        # 10 fr cards
        for i in range(10):
            session.add(Card(target_word=f"fr{i}", target_language="fr", fsrs_state="Review"))
        await session.commit()

        from sqlalchemy import select

        es_cards_result = await session.execute(select(Card).where(Card.target_language == "es"))
        es_cards = es_cards_result.scalars().all()
        for c in es_cards[:15]:
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

        es_profile = await core_cefr.get_profile("es", session)
        assert es_profile.vocabulary_breadth == 40
        assert es_profile.level == "A1"

        # FR profile — not enough reviews
        core_cefr._profile_cache.clear()
        fr_profile = await core_cefr.get_profile("fr", session)
        assert fr_profile.level is None  # no reviews for fr
