"""Tests for api/decks.py — CRUD + multi-language deck management.

TDD: these tests are written BEFORE implementation to drive api/decks.py and core/decks.py.
AC: 1, 2, 3, 4, 7, 9
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.db.models import Card, Deck, Settings

# ── Shared fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
async def seed_settings(session: AsyncSession) -> Settings:
    """Insert a Settings row with two target languages configured."""
    s = Settings(
        native_language="en",
        active_target_language="es",
        target_languages='["es", "fr"]',
        onboarding_completed=True,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@pytest.fixture
async def seed_deck(session: AsyncSession) -> Deck:
    deck = Deck(name="Spanish Vocab", target_language="es")
    session.add(deck)
    await session.commit()
    await session.refresh(deck)
    return deck


@pytest.fixture
async def seed_deck_with_cards(session: AsyncSession) -> tuple[Deck, list[Card]]:
    """A deck with 3 cards, 2 of which are due."""
    deck = Deck(name="Deck With Cards", target_language="es")
    session.add(deck)
    await session.flush()  # get deck.id before creating cards
    now = datetime.now(UTC)
    cards = [
        Card(
            target_word="uno",
            target_language="es",
            deck_id=deck.id,
            due=now - timedelta(days=1),
        ),
        Card(
            target_word="dos",
            target_language="es",
            deck_id=deck.id,
            due=now - timedelta(hours=1),
        ),
        Card(
            target_word="tres",
            target_language="es",
            deck_id=deck.id,
            due=now + timedelta(days=3),
        ),
    ]
    for c in cards:
        session.add(c)
    await session.commit()
    await session.refresh(deck)
    return deck, cards


# ── TestListDecks ────────────────────────────────────────────────────────────


class TestListDecks:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_list_decks_empty_returns_empty_list(self, client: AsyncClient):
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_decks_filtered_by_target_language(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Spanish Vocab"
        assert data[0]["target_language"] == "es"

    async def test_list_decks_other_language_not_returned(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.get("/decks?target_language=fr")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_decks_includes_accurate_card_count(
        self, client: AsyncClient, seed_deck_with_cards: tuple[Deck, list[Card]]
    ):
        deck, cards = seed_deck_with_cards
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["card_count"] == 3

    async def test_list_decks_includes_accurate_due_count(
        self, client: AsyncClient, seed_deck_with_cards: tuple[Deck, list[Card]]
    ):
        deck, cards = seed_deck_with_cards
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["due_card_count"] == 2

    async def test_list_decks_missing_target_language_returns_422(
        self, client: AsyncClient
    ):
        response = await client.get("/decks")
        assert response.status_code == 422

    async def test_list_decks_ordered_by_name(
        self, client: AsyncClient, session: AsyncSession
    ):
        for name in ["Zebra Deck", "Alpha Deck", "Mango Deck"]:
            session.add(Deck(name=name, target_language="es"))
        await session.commit()
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        names = [d["name"] for d in response.json()]
        assert names == sorted(names)

    async def test_list_decks_response_shape(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        deck_data = response.json()[0]
        assert "id" in deck_data
        assert "name" in deck_data
        assert "target_language" in deck_data
        assert "card_count" in deck_data
        assert "due_card_count" in deck_data
        assert "created_at" in deck_data
        assert "updated_at" in deck_data

    async def test_list_decks_zero_cards_deck_included(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """Decks with zero cards must still appear (outerjoin required)."""
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["card_count"] == 0
        assert data[0]["due_card_count"] == 0


# ── TestCreateDeck ───────────────────────────────────────────────────────────


class TestCreateDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_create_deck_success(self, client: AsyncClient):
        response = await client.post(
            "/decks", json={"name": "My Deck", "target_language": "es"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Deck"
        assert data["target_language"] == "es"
        assert data["card_count"] == 0
        assert data["due_card_count"] == 0
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_deck_name_required_returns_422(self, client: AsyncClient):
        response = await client.post("/decks", json={"target_language": "es"})
        assert response.status_code == 422

    async def test_create_deck_empty_name_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/decks", json={"name": "", "target_language": "es"}
        )
        assert response.status_code == 422

    async def test_create_deck_duplicate_name_same_language_returns_409(
        self, client: AsyncClient
    ):
        await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
        response = await client.post(
            "/decks", json={"name": "My Deck", "target_language": "es"}
        )
        assert response.status_code == 409
        body = response.json()
        assert body["type"] == "/errors/deck-name-conflict"
        assert body["status"] == 409
        assert "My Deck" in body["detail"]
        assert "es" in body["detail"]

    async def test_create_deck_duplicate_name_different_language_succeeds(
        self, client: AsyncClient
    ):
        await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
        response = await client.post(
            "/decks", json={"name": "My Deck", "target_language": "fr"}
        )
        assert response.status_code == 201
        assert response.json()["target_language"] == "fr"

    async def test_create_deck_defaults_to_active_language(
        self, client: AsyncClient, seed_settings: Settings
    ):
        response = await client.post("/decks", json={"name": "No Lang Deck"})
        assert response.status_code == 201
        assert response.json()["target_language"] == "es"

    async def test_create_deck_adds_language_to_settings_target_languages(
        self, client: AsyncClient, session: AsyncSession
    ):
        settings = Settings(
            native_language="en",
            active_target_language="es",
            target_languages='["es"]',
            onboarding_completed=True,
        )
        session.add(settings)
        await session.commit()

        await client.post("/decks", json={"name": "French Deck", "target_language": "fr"})

        await session.refresh(settings)
        langs = json.loads(settings.target_languages)
        assert "fr" in langs

    async def test_create_deck_name_stripped_of_whitespace(self, client: AsyncClient):
        response = await client.post(
            "/decks", json={"name": "  My Deck  ", "target_language": "es"}
        )
        assert response.status_code == 201
        assert response.json()["name"] == "My Deck"


# ── TestPatchDeck ────────────────────────────────────────────────────────────


class TestPatchDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_patch_deck_rename_success(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.patch(
            f"/decks/{seed_deck.id}", json={"name": "New Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["id"] == seed_deck.id

    async def test_patch_deck_not_found_returns_404(self, client: AsyncClient):
        response = await client.patch("/decks/99999", json={"name": "New Name"})
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/deck-not-found"
        assert body["status"] == 404

    async def test_patch_deck_duplicate_name_same_language_returns_409(
        self, client: AsyncClient, session: AsyncSession
    ):
        deck_a = Deck(name="Deck A", target_language="es")
        deck_b = Deck(name="Deck B", target_language="es")
        session.add(deck_a)
        session.add(deck_b)
        await session.commit()
        await session.refresh(deck_a)

        response = await client.patch(f"/decks/{deck_a.id}", json={"name": "Deck B"})
        assert response.status_code == 409
        assert response.json()["type"] == "/errors/deck-name-conflict"

    async def test_patch_deck_duplicate_name_self_is_ok(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.patch(
            f"/decks/{seed_deck.id}", json={"name": seed_deck.name}
        )
        assert response.status_code == 200

    async def test_patch_deck_empty_name_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.patch(f"/decks/{seed_deck.id}", json={"name": ""})
        assert response.status_code == 422

    async def test_patch_returns_updated_deck_response(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.patch(
            f"/decks/{seed_deck.id}", json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "target_language" in data
        assert "card_count" in data
        assert "due_card_count" in data
        assert "created_at" in data
        assert "updated_at" in data


# ── TestDeleteDeck ───────────────────────────────────────────────────────────


class TestDeleteDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_delete_deck_returns_204(
        self, client: AsyncClient, seed_deck: Deck
    ):
        response = await client.delete(f"/decks/{seed_deck.id}")
        assert response.status_code == 204

    async def test_delete_deck_not_found_returns_404(self, client: AsyncClient):
        response = await client.delete("/decks/99999")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/deck-not-found"
        assert body["status"] == 404

    async def test_delete_deck_cards_remain_with_null_deck_id(
        self, client: AsyncClient,
        session: AsyncSession,
        seed_deck_with_cards: tuple[Deck, list[Card]],
    ):
        deck, cards = seed_deck_with_cards
        response = await client.delete(f"/decks/{deck.id}")
        assert response.status_code == 204

        # Verify cards still exist with deck_id = None
        for card in cards:
            await session.refresh(card)
            assert card.deck_id is None

    async def test_delete_deck_and_refetch_returns_404(
        self, client: AsyncClient, seed_deck: Deck
    ):
        await client.delete(f"/decks/{seed_deck.id}")
        # After deletion the deck should no longer appear in list
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        ids = [d["id"] for d in response.json()]
        assert seed_deck.id not in ids
