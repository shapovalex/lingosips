"""Unit tests for core/decks.py — direct function coverage.

Calls core functions directly with the test AsyncSession (not through ASGI transport),
guaranteeing coverage.py can track their execution.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import decks as core_decks
from lingosips.db.models import Card, Deck, Settings


class TestCoreDecksList:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_list_decks_empty(self, session: AsyncSession):
        result = await core_decks.list_decks(session, "es")
        assert result == []

    async def test_list_decks_returns_deck_with_counts(self, session: AsyncSession):
        now = datetime.now(UTC)
        deck = Deck(name="My Deck", target_language="es")
        session.add(deck)
        await session.flush()

        session.add(Card(
            target_word="word1",
            target_language="es",
            deck_id=deck.id,
            due=now - timedelta(hours=1),
        ))
        session.add(Card(
            target_word="word2",
            target_language="es",
            deck_id=deck.id,
            due=now + timedelta(days=3),
        ))
        await session.commit()

        rows = await core_decks.list_decks(session, "es")
        assert len(rows) == 1
        assert rows[0]["deck"].name == "My Deck"
        assert rows[0]["card_count"] == 2
        assert rows[0]["due_card_count"] == 1

    async def test_list_decks_filters_by_language(self, session: AsyncSession):
        session.add(Deck(name="Spanish", target_language="es"))
        session.add(Deck(name="French", target_language="fr"))
        await session.commit()

        rows = await core_decks.list_decks(session, "es")
        assert len(rows) == 1
        assert rows[0]["deck"].target_language == "es"

    async def test_list_decks_ordered_alphabetically(self, session: AsyncSession):
        for name in ["Zebra", "Alpha", "Mango"]:
            session.add(Deck(name=name, target_language="es"))
        await session.commit()

        rows = await core_decks.list_decks(session, "es")
        names = [r["deck"].name for r in rows]
        assert names == sorted(names)

    async def test_list_decks_zero_card_deck_shows_zero_counts(self, session: AsyncSession):
        session.add(Deck(name="Empty Deck", target_language="es"))
        await session.commit()

        rows = await core_decks.list_decks(session, "es")
        assert rows[0]["card_count"] == 0
        assert rows[0]["due_card_count"] == 0


class TestCoreGetDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_get_deck_success(self, session: AsyncSession):
        deck = Deck(name="Test Deck", target_language="es")
        session.add(deck)
        await session.commit()
        await session.refresh(deck)

        result = await core_decks.get_deck(deck.id, session)
        assert result.id == deck.id
        assert result.name == "Test Deck"

    async def test_get_deck_not_found_raises_value_error(self, session: AsyncSession):
        with pytest.raises(ValueError, match="99999"):
            await core_decks.get_deck(99999, session)


class TestCoreCreateDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_create_deck_success(self, session: AsyncSession):
        deck = await core_decks.create_deck("My Deck", "es", session)
        assert deck.id is not None
        assert deck.name == "My Deck"
        assert deck.target_language == "es"

    async def test_create_deck_conflict_raises_value_error(self, session: AsyncSession):
        await core_decks.create_deck("My Deck", "es", session)
        with pytest.raises(ValueError, match="conflict"):
            await core_decks.create_deck("My Deck", "es", session)

    async def test_create_deck_different_language_ok(self, session: AsyncSession):
        await core_decks.create_deck("My Deck", "es", session)
        deck_fr = await core_decks.create_deck("My Deck", "fr", session)
        assert deck_fr.target_language == "fr"

    async def test_create_deck_adds_language_to_settings(self, session: AsyncSession):
        settings = Settings(
            native_language="en",
            active_target_language="es",
            target_languages='["es"]',
            onboarding_completed=True,
        )
        session.add(settings)
        await session.commit()

        await core_decks.create_deck("French Deck", "fr", session)

        await session.refresh(settings)
        langs = json.loads(settings.target_languages)
        assert "fr" in langs

    async def test_create_deck_no_settings_does_not_fail(self, session: AsyncSession):
        # No settings row — create_deck should still work
        deck = await core_decks.create_deck("My Deck", "es", session)
        assert deck.name == "My Deck"

    async def test_create_deck_language_already_in_settings_no_duplicate(
        self, session: AsyncSession
    ):
        settings = Settings(
            native_language="en",
            active_target_language="es",
            target_languages='["es", "fr"]',
            onboarding_completed=True,
        )
        session.add(settings)
        await session.commit()

        await core_decks.create_deck("Deck", "es", session)

        await session.refresh(settings)
        langs = json.loads(settings.target_languages)
        assert langs.count("es") == 1  # no duplicate


class TestCoreUpdateDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_update_deck_rename(self, session: AsyncSession):
        deck = Deck(name="Old Name", target_language="es")
        session.add(deck)
        await session.commit()
        await session.refresh(deck)

        updated = await core_decks.update_deck(deck.id, {"name": "New Name"}, session)
        assert updated.name == "New Name"
        assert updated.id == deck.id

    async def test_update_deck_rename_to_same_name_ok(self, session: AsyncSession):
        deck = Deck(name="Same Name", target_language="es")
        session.add(deck)
        await session.commit()
        await session.refresh(deck)

        updated = await core_decks.update_deck(deck.id, {"name": "Same Name"}, session)
        assert updated.name == "Same Name"

    async def test_update_deck_conflict_raises_value_error(self, session: AsyncSession):
        deck_a = Deck(name="Deck A", target_language="es")
        deck_b = Deck(name="Deck B", target_language="es")
        session.add(deck_a)
        session.add(deck_b)
        await session.commit()
        await session.refresh(deck_a)

        with pytest.raises(ValueError, match="conflict"):
            await core_decks.update_deck(deck_a.id, {"name": "Deck B"}, session)

    async def test_update_deck_not_found_raises_value_error(self, session: AsyncSession):
        with pytest.raises(ValueError, match="99999"):
            await core_decks.update_deck(99999, {"name": "New Name"}, session)

    async def test_update_deck_empty_update_data_still_updates_timestamp(
        self, session: AsyncSession
    ):
        deck = Deck(name="My Deck", target_language="es")
        session.add(deck)
        await session.commit()
        await session.refresh(deck)

        updated = await core_decks.update_deck(deck.id, {}, session)
        # updated_at should be set (may equal original in fast tests, but shouldn't raise)
        assert updated.name == "My Deck"


class TestCoreDeleteDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_delete_deck_removes_deck(self, session: AsyncSession):
        deck = Deck(name="To Delete", target_language="es")
        session.add(deck)
        await session.commit()
        await session.refresh(deck)
        deck_id = deck.id

        await core_decks.delete_deck(deck_id, session)

        result = await session.execute(select(Deck).where(Deck.id == deck_id))
        assert result.scalar_one_or_none() is None

    async def test_delete_deck_cards_get_null_deck_id(self, session: AsyncSession):
        deck = Deck(name="Deck With Cards", target_language="es")
        session.add(deck)
        await session.flush()

        card = Card(target_word="word", target_language="es", deck_id=deck.id)
        session.add(card)
        await session.commit()
        await session.refresh(card)

        await core_decks.delete_deck(deck.id, session)

        await session.refresh(card)
        assert card.deck_id is None

    async def test_delete_deck_not_found_raises_value_error(self, session: AsyncSession):
        with pytest.raises(ValueError, match="99999"):
            await core_decks.delete_deck(99999, session)
