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

from lingosips.api.decks import _parse_deck_overrides
from lingosips.db.models import Card, Deck, Settings

# ── Unit tests for _parse_deck_overrides ─────────────────────────────────────


class TestParseDeckOverrides:
    """Direct unit tests for the _parse_deck_overrides helper."""

    def test_none_returns_none(self) -> None:
        assert _parse_deck_overrides(None) is None

    def test_valid_json_dict_returns_dict(self) -> None:
        result = _parse_deck_overrides('{"cards_per_session": 10}')
        assert result == {"cards_per_session": 10}

    def test_malformed_json_returns_none(self) -> None:
        """Invalid JSON string → returns None instead of raising (defensive)."""
        assert _parse_deck_overrides("not-json") is None

    def test_json_non_dict_returns_none(self) -> None:
        """JSON array (not a dict) → returns None."""
        assert _parse_deck_overrides("[1, 2, 3]") is None


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

    async def test_list_decks_missing_target_language_returns_422(self, client: AsyncClient):
        response = await client.get("/decks")
        assert response.status_code == 422

    async def test_list_decks_ordered_by_name(self, client: AsyncClient, session: AsyncSession):
        for name in ["Zebra Deck", "Alpha Deck", "Mango Deck"]:
            session.add(Deck(name=name, target_language="es"))
        await session.commit()
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        names = [d["name"] for d in response.json()]
        assert names == sorted(names)

    async def test_list_decks_response_shape(self, client: AsyncClient, seed_deck: Deck):
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

    async def test_list_decks_zero_cards_deck_included(self, client: AsyncClient, seed_deck: Deck):
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
        response = await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
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
        response = await client.post("/decks", json={"name": "", "target_language": "es"})
        assert response.status_code == 422

    async def test_create_deck_duplicate_name_same_language_returns_409(self, client: AsyncClient):
        await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
        response = await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
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
        response = await client.post("/decks", json={"name": "My Deck", "target_language": "fr"})
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

    async def test_patch_deck_rename_success(self, client: AsyncClient, seed_deck: Deck):
        response = await client.patch(f"/decks/{seed_deck.id}", json={"name": "New Name"})
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

    async def test_patch_deck_duplicate_name_self_is_ok(self, client: AsyncClient, seed_deck: Deck):
        response = await client.patch(f"/decks/{seed_deck.id}", json={"name": seed_deck.name})
        assert response.status_code == 200

    async def test_patch_deck_empty_name_returns_422(self, client: AsyncClient, seed_deck: Deck):
        response = await client.patch(f"/decks/{seed_deck.id}", json={"name": ""})
        assert response.status_code == 422

    async def test_patch_returns_updated_deck_response(self, client: AsyncClient, seed_deck: Deck):
        response = await client.patch(f"/decks/{seed_deck.id}", json={"name": "Updated Name"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "target_language" in data
        assert "card_count" in data
        assert "due_card_count" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_patch_deck_settings_overrides_success(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """T4.1: PATCH with settings_overrides → 200, body contains overrides."""
        overrides = {"auto_generate_images": True, "default_practice_mode": "write"}
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": overrides},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["settings_overrides"] == overrides

    async def test_patch_deck_settings_overrides_null_clears_overrides(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """T4.1: PATCH settings_overrides=None clears any previously stored overrides."""
        # First set some overrides
        await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"auto_generate_images": True}},
        )
        # Then clear them
        response = await client.patch(f"/decks/{seed_deck.id}", json={"settings_overrides": None})
        assert response.status_code == 200
        assert response.json()["settings_overrides"] is None

    async def test_patch_deck_settings_overrides_invalid_key_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """T4.1: invalid key in settings_overrides → 422."""
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"invalid_key": True}},
        )
        assert response.status_code == 422

    async def test_patch_deck_list_returns_settings_overrides(
        self, client: AsyncClient, seed_deck: Deck, seed_settings: Settings
    ) -> None:
        """T4.1: DeckResponse in list endpoint includes settings_overrides after patch."""
        await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"cards_per_session": 10}},
        )
        list_resp = await client.get("/decks", params={"target_language": "es"})
        assert list_resp.status_code == 200
        deck_in_list = next(d for d in list_resp.json() if d["id"] == seed_deck.id)
        assert deck_in_list["settings_overrides"] == {"cards_per_session": 10}

    async def test_patch_deck_settings_overrides_invalid_value_type_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """settings_overrides with invalid cards_per_session type → 422."""
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"cards_per_session": "not-a-number"}},
        )
        assert response.status_code == 422

    async def test_patch_deck_settings_overrides_invalid_audio_bool_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """settings_overrides with non-bool auto_generate_audio → 422."""
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"auto_generate_audio": "yes"}},
        )
        assert response.status_code == 422

    async def test_patch_deck_settings_overrides_invalid_images_bool_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """settings_overrides with non-bool auto_generate_images → 422."""
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"auto_generate_images": 1}},
        )
        assert response.status_code == 422

    async def test_patch_deck_settings_overrides_invalid_practice_mode_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """settings_overrides with invalid default_practice_mode value → 422."""
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"default_practice_mode": "invalid_mode"}},
        )
        assert response.status_code == 422

    async def test_patch_deck_settings_overrides_cards_per_session_boundary_returns_422(
        self, client: AsyncClient, seed_deck: Deck
    ) -> None:
        """settings_overrides with cards_per_session out of range → 422."""
        response = await client.patch(
            f"/decks/{seed_deck.id}",
            json={"settings_overrides": {"cards_per_session": 0}},
        )
        assert response.status_code == 422


# ── TestDeleteDeck ───────────────────────────────────────────────────────────


class TestDeleteDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_delete_deck_returns_204(self, client: AsyncClient, seed_deck: Deck):
        response = await client.delete(f"/decks/{seed_deck.id}")
        assert response.status_code == 204

    async def test_delete_deck_not_found_returns_404(self, client: AsyncClient):
        response = await client.delete("/decks/99999")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/deck-not-found"
        assert body["status"] == 404

    async def test_delete_deck_cards_remain_with_null_deck_id(
        self,
        client: AsyncClient,
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

    async def test_delete_deck_and_refetch_returns_404(self, client: AsyncClient, seed_deck: Deck):
        await client.delete(f"/decks/{seed_deck.id}")
        # After deletion the deck should no longer appear in list
        response = await client.get("/decks?target_language=es")
        assert response.status_code == 200
        ids = [d["id"] for d in response.json()]
        assert seed_deck.id not in ids


# ── TestGetDeck ──────────────────────────────────────────────────────────────


class TestGetDeck:
    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_get_deck_success(self, client: AsyncClient, seed_deck: Deck):
        """GET /decks/{deck_id} returns the deck with full response shape."""
        response = await client.get(f"/decks/{seed_deck.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == seed_deck.id
        assert data["name"] == "Spanish Vocab"
        assert data["target_language"] == "es"
        assert "card_count" in data
        assert "due_card_count" in data
        assert "created_at" in data
        assert "updated_at" in data

    async def test_get_deck_not_found_returns_404(self, client: AsyncClient):
        """GET /decks/99999 returns 404 RFC 7807."""
        response = await client.get("/decks/99999")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/deck-not-found"
        assert body["status"] == 404
        assert "99999" in body["detail"]

    async def test_get_deck_card_count_zero_when_no_cards(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """GET /decks/{deck_id} returns card_count=0 when deck has no cards."""
        response = await client.get(f"/decks/{seed_deck.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["card_count"] == 0
        assert data["due_card_count"] == 0

    async def test_get_deck_card_count_accurate(
        self, client: AsyncClient, seed_deck_with_cards: tuple[Deck, list[Card]]
    ):
        """GET /decks/{deck_id} returns correct card_count and due_card_count."""
        deck, _ = seed_deck_with_cards
        response = await client.get(f"/decks/{deck.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["card_count"] == 3
        assert data["due_card_count"] == 2


# ── TestExportDeck ───────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestExportDeck:
    """API-level tests for GET /decks/{deck_id}/export."""

    @pytest.fixture(autouse=True)
    async def truncate(self, test_engine):
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM cards"))
            await conn.execute(text("DELETE FROM decks"))
            await conn.execute(text("DELETE FROM settings"))

    async def test_export_deck_unknown_id_returns_404(self, client: AsyncClient):
        """GET /decks/99999/export returns 404 RFC 7807."""
        response = await client.get("/decks/99999/export")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "/errors/deck-not-found"

    async def test_export_deck_returns_zip_content_type(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """Export returns application/zip content type."""
        response = await client.get(f"/decks/{seed_deck.id}/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    async def test_export_deck_returns_lingosips_filename(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """Content-Disposition header contains .lingosips filename."""
        response = await client.get(f"/decks/{seed_deck.id}/export")
        assert response.status_code == 200
        cd = response.headers.get("content-disposition", "")
        assert ".lingosips" in cd

    async def test_export_deck_zip_contains_deck_json(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """The downloaded ZIP contains deck.json."""
        import io
        import zipfile

        response = await client.get(f"/decks/{seed_deck.id}/export")
        assert response.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert "deck.json" in zf.namelist()

    async def test_export_deck_json_has_correct_format_version(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """deck.json inside the ZIP has format_version='1'."""
        import io
        import zipfile

        response = await client.get(f"/decks/{seed_deck.id}/export")
        assert response.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        deck_json = json.loads(zf.read("deck.json"))
        assert deck_json["format_version"] == "1"
        assert deck_json["deck"]["name"] == seed_deck.name
        assert deck_json["deck"]["target_language"] == seed_deck.target_language

    async def test_export_deck_empty_deck_has_cards_array(
        self, client: AsyncClient, seed_deck: Deck
    ):
        """Exporting a deck with no cards produces deck.json with 'cards': []."""
        import io
        import zipfile

        response = await client.get(f"/decks/{seed_deck.id}/export")
        assert response.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        deck_json = json.loads(zf.read("deck.json"))
        assert deck_json["cards"] == []

    async def test_export_deck_with_cards_includes_card_data(
        self, client: AsyncClient, session: AsyncSession, seed_deck: Deck
    ):
        """Deck with cards exports all cards in deck.json."""
        import io
        import zipfile

        card = Card(
            target_word="melancólico",
            translation="melancholic",
            target_language="es",
            deck_id=seed_deck.id,
        )
        session.add(card)
        await session.commit()

        response = await client.get(f"/decks/{seed_deck.id}/export")
        assert response.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        deck_json = json.loads(zf.read("deck.json"))
        assert len(deck_json["cards"]) == 1
        assert deck_json["cards"][0]["target_word"] == "melancólico"
        assert deck_json["cards"][0]["translation"] == "melancholic"

    async def test_export_deck_card_no_ids_in_export(
        self, client: AsyncClient, session: AsyncSession, seed_deck: Deck
    ):
        """IDs are NOT exported in card JSON."""
        import io
        import zipfile

        card = Card(target_word="agua", target_language="es", deck_id=seed_deck.id)
        session.add(card)
        await session.commit()

        response = await client.get(f"/decks/{seed_deck.id}/export")
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        deck_json = json.loads(zf.read("deck.json"))
        assert "id" not in deck_json["cards"][0]
