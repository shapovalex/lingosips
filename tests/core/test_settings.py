"""Direct unit tests for core/settings.py business logic.

These tests call get_or_create_settings() and update_settings() directly
through the async session fixture, bypassing the HTTP layer. This ensures
coverage is correctly tracked regardless of pytest-asyncio tracing quirks.

AC: T11 coverage gate ≥90%
"""

import json

import pytest
from sqlalchemy import text

from lingosips.core.settings import (
    DEFAULT_NATIVE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_or_create_settings,
    update_settings,
    validate_language_code,
)


@pytest.mark.anyio
class TestValidateLanguageCode:
    """Tests for validate_language_code()."""

    def test_valid_codes_do_not_raise(self) -> None:
        for code in ("en", "es", "fr", "de", "ja"):
            validate_language_code(code)  # should not raise

    def test_invalid_code_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="not a supported language code"):
            validate_language_code("xx")

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            validate_language_code("")

    def test_error_message_contains_code(self) -> None:
        with pytest.raises(ValueError, match="'zz'"):
            validate_language_code("zz")

    def test_all_supported_languages_are_valid(self) -> None:
        for code in SUPPORTED_LANGUAGES:
            validate_language_code(code)  # should not raise


@pytest.mark.anyio
class TestGetOrCreateSettings:
    """Tests for get_or_create_settings() — exercises lines 71-83."""

    @pytest.fixture(autouse=True)
    async def truncate_settings(self, test_engine) -> None:
        """Wipe settings table before each test for isolation."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM settings"))

    async def test_creates_default_row_when_table_empty(self, session) -> None:
        """Empty table → creates singleton with EN/ES defaults (lines 72-83)."""
        result = await get_or_create_settings(session)

        assert result.native_language == DEFAULT_NATIVE_LANGUAGE
        assert result.active_target_language == DEFAULT_TARGET_LANGUAGE
        assert result.onboarding_completed is False
        assert result.id is not None

    async def test_target_languages_default_is_json_string(self, session) -> None:
        """Default target_languages is a valid JSON string containing the default code."""
        result = await get_or_create_settings(session)

        langs = json.loads(result.target_languages)
        assert isinstance(langs, list)
        assert DEFAULT_TARGET_LANGUAGE in langs

    async def test_returns_existing_row_when_present(self, session) -> None:
        """Second call returns the SAME row (idempotent singleton)."""
        first = await get_or_create_settings(session)
        second = await get_or_create_settings(session)

        assert first.id == second.id

    async def test_only_one_row_created_on_repeated_calls(self, session, test_engine) -> None:
        """Multiple calls never create duplicate rows."""
        await get_or_create_settings(session)
        await get_or_create_settings(session)

        async with test_engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM settings"))
            count = result.scalar()
        assert count == 1


@pytest.mark.anyio
class TestUpdateSettings:
    """Tests for update_settings() — exercises lines 101-108."""

    @pytest.fixture(autouse=True)
    async def truncate_settings(self, test_engine) -> None:
        """Wipe settings table before each test."""
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM settings"))

    async def test_updates_native_language(self, session) -> None:
        """update_settings sets native_language on the singleton row."""
        result = await update_settings(session, native_language="fr")

        assert result.native_language == "fr"
        assert result.active_target_language == DEFAULT_TARGET_LANGUAGE

    async def test_updates_active_target_language(self, session) -> None:
        """update_settings sets active_target_language."""
        result = await update_settings(session, active_target_language="de")

        assert result.active_target_language == "de"

    async def test_updates_onboarding_completed(self, session) -> None:
        """update_settings sets onboarding_completed to True."""
        result = await update_settings(session, onboarding_completed=True)

        assert result.onboarding_completed is True

    async def test_partial_update_preserves_other_fields(self, session) -> None:
        """Only kwargs fields are changed; others retain defaults."""
        await update_settings(session, native_language="en", active_target_language="fr")
        result = await update_settings(session, native_language="de")

        assert result.native_language == "de"
        assert result.active_target_language == "fr"  # untouched

    async def test_serializes_target_languages_list_to_json(self, session) -> None:
        """list[str] for target_languages is stored as JSON string (line 98-99)."""
        result = await update_settings(session, target_languages=["es", "fr", "de"])

        stored = json.loads(result.target_languages)
        assert stored == ["es", "fr", "de"]

    async def test_target_languages_string_stored_as_is(self, session) -> None:
        """A pre-serialized JSON string is stored without double-encoding."""
        result = await update_settings(session, target_languages='["es"]')

        # Should be stored as-is (no double-encoding)
        assert result.target_languages == '["es"]'

    async def test_updated_at_is_set(self, session) -> None:
        """update_settings stamps updated_at timestamp."""
        result = await update_settings(session, native_language="es")

        assert result.updated_at is not None

    async def test_multiple_fields_updated_atomically(self, session) -> None:
        """Multiple kwargs are all applied in the same call."""
        result = await update_settings(
            session,
            native_language="pt",
            active_target_language="it",
            onboarding_completed=True,
            cards_per_session=30,
        )

        assert result.native_language == "pt"
        assert result.active_target_language == "it"
        assert result.onboarding_completed is True
        assert result.cards_per_session == 30
