"""Tests for GET /settings and PUT /settings endpoints.

TDD: Written BEFORE implementing core/settings.py and api/settings.py.
All 10 tests per story task T4.

Test isolation: settings table must be empty for tests that require no pre-existing row.
A truncate_settings autouse fixture is applied to both test classes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text


class TestGetSettings:
    """Tests for GET /settings (AC: 1, 2, 4, 5)."""

    @pytest.fixture(autouse=True)
    async def truncate_settings(self, test_engine) -> None:
        """Ensure empty settings table before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM settings"))

    async def test_get_settings_creates_default_on_empty_db(
        self, client: AsyncClient
    ) -> None:
        """T4.2: empty DB → 200, onboarding_completed=false, native="en", target="es"."""
        response = await client.get("/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["native_language"] == "en"
        assert body["active_target_language"] == "es"
        assert body["onboarding_completed"] is False

    async def test_get_settings_returns_existing_row(self, client: AsyncClient) -> None:
        """T4.3: seed a Settings row → 200 returns it unchanged."""
        # Seed via PUT (creates default first, then updates)
        put_resp = await client.put(
            "/settings",
            json={
                "native_language": "fr",
                "active_target_language": "de",
                "onboarding_completed": True,
            },
        )
        assert put_resp.status_code == 200
        seeded_id = put_resp.json()["id"]

        # GET should return the same row
        response = await client.get("/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == seeded_id
        assert body["native_language"] == "fr"
        assert body["active_target_language"] == "de"
        assert body["onboarding_completed"] is True

    async def test_get_settings_is_idempotent(self, client: AsyncClient) -> None:
        """T4.4: two sequential GETs on empty DB → only one row in DB (no duplicate insert)."""
        r1 = await client.get("/settings")
        r2 = await client.get("/settings")
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Same ID = same row
        assert r1.json()["id"] == r2.json()["id"]

    async def test_get_settings_response_has_all_fields(self, client: AsyncClient) -> None:
        """GET /settings returns SettingsResponse with all required fields."""
        response = await client.get("/settings")
        assert response.status_code == 200
        body = response.json()
        required_fields = [
            "id",
            "native_language",
            "target_languages",
            "active_target_language",
            "auto_generate_audio",
            "auto_generate_images",
            "default_practice_mode",
            "cards_per_session",
            "onboarding_completed",
        ]
        for field in required_fields:
            assert field in body, f"Missing field: {field}"


class TestPutSettings:
    """Tests for PUT /settings (AC: 2, 3)."""

    @pytest.fixture(autouse=True)
    async def truncate_settings(self, test_engine) -> None:
        """Ensure empty settings table before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM settings"))

    async def test_put_settings_updates_native_language(self, client: AsyncClient) -> None:
        """T4.5: PUT {"native_language": "fr"} → 200, persisted."""
        response = await client.put("/settings", json={"native_language": "fr"})
        assert response.status_code == 200
        body = response.json()
        assert body["native_language"] == "fr"

        # Verify persisted
        get_resp = await client.get("/settings")
        assert get_resp.json()["native_language"] == "fr"

    async def test_put_settings_updates_target_language(self, client: AsyncClient) -> None:
        """T4.6: PUT {"active_target_language": "de"} → 200, persisted."""
        response = await client.put("/settings", json={"active_target_language": "de"})
        assert response.status_code == 200
        body = response.json()
        assert body["active_target_language"] == "de"

        # Verify persisted
        get_resp = await client.get("/settings")
        assert get_resp.json()["active_target_language"] == "de"

    async def test_put_settings_marks_onboarding_complete(
        self, client: AsyncClient
    ) -> None:
        """T4.7: PUT {"onboarding_completed": true} → 200, field persisted."""
        response = await client.put("/settings", json={"onboarding_completed": True})
        assert response.status_code == 200
        body = response.json()
        assert body["onboarding_completed"] is True

        # Verify persisted
        get_resp = await client.get("/settings")
        assert get_resp.json()["onboarding_completed"] is True

    async def test_put_settings_invalid_native_language_returns_422(
        self, client: AsyncClient
    ) -> None:
        """T4.8: PUT {"native_language": "xx"} → 422 RFC 7807."""
        response = await client.put("/settings", json={"native_language": "xx"})
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/invalid-language"
        assert "xx" in body["detail"]
        assert body["status"] == 422

    async def test_put_settings_invalid_target_language_returns_422(
        self, client: AsyncClient
    ) -> None:
        """T4.9: PUT {"active_target_language": "zz"} → 422 RFC 7807."""
        response = await client.put("/settings", json={"active_target_language": "zz"})
        assert response.status_code == 422
        body = response.json()
        assert body["type"] == "/errors/invalid-language"
        assert "zz" in body["detail"]
        assert body["status"] == 422

    async def test_put_settings_partial_update_preserves_other_fields(
        self, client: AsyncClient
    ) -> None:
        """T4.10: PUT only native_language → other fields remain unchanged."""
        # Establish known state
        await client.put(
            "/settings",
            json={
                "native_language": "en",
                "active_target_language": "fr",
                "onboarding_completed": False,
            },
        )
        # Update only native_language
        response = await client.put("/settings", json={"native_language": "de"})
        assert response.status_code == 200
        body = response.json()
        assert body["native_language"] == "de"
        # Other fields unchanged
        assert body["active_target_language"] == "fr"
        assert body["onboarding_completed"] is False

    async def test_put_settings_resets_onboarding_completed_to_false(
        self, client: AsyncClient
    ) -> None:
        """PUT {"onboarding_completed": false} correctly persists False.

        Verifies that the `exclude_none` filter does NOT drop False values
        (False is not None). This is the path used by E2E resetOnboarding.
        """
        # Set to True first
        await client.put("/settings", json={"onboarding_completed": True})
        # Reset to False — False must pass the exclude_none filter
        response = await client.put("/settings", json={"onboarding_completed": False})
        assert response.status_code == 200
        assert response.json()["onboarding_completed"] is False
        # Verify persisted via GET
        get_resp = await client.get("/settings")
        assert get_resp.json()["onboarding_completed"] is False
