"""Tests for get_service_status_info() in services/registry.py (TDD).

Tests cover all credential combinations for LLM and speech provider status detection.
Follows patch-at-import pattern: lingosips.services.registry.get_credential
"""

from unittest.mock import patch

import pytest

from lingosips.services.credentials import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
)


@pytest.mark.anyio
class TestGetServiceStatusInfo:
    """Tests for get_service_status_info() → ServiceStatusInfo dataclass."""

    def test_returns_qwen_when_no_openrouter_key(self):
        """No credentials → llm_provider == 'qwen_local', llm_model is None."""
        with patch("lingosips.services.registry.get_credential", return_value=""):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.llm_provider == "qwen_local"
        assert status.llm_model is None

    def test_returns_openrouter_when_key_configured(self):
        """OpenRouter key + model configured → llm_provider == 'openrouter', llm_model set."""

        def _cred(key: str) -> str:
            return {
                OPENROUTER_API_KEY: "sk-test-key",
                OPENROUTER_MODEL: "openai/gpt-4o-mini",
            }.get(key, "")

        with patch("lingosips.services.registry.get_credential", side_effect=_cred):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.llm_provider == "openrouter"
        assert status.llm_model == "openai/gpt-4o-mini"

    def test_returns_default_model_when_model_not_configured(self):
        """OpenRouter key exists but model is empty → llm_model == DEFAULT_OPENROUTER_MODEL."""
        from lingosips.services.registry import DEFAULT_OPENROUTER_MODEL

        def _cred(key: str) -> str:
            if key == OPENROUTER_API_KEY:
                return "sk-test-key"
            return ""

        with patch("lingosips.services.registry.get_credential", side_effect=_cred):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.llm_provider == "openrouter"
        assert status.llm_model == DEFAULT_OPENROUTER_MODEL

    def test_returns_pyttsx3_when_no_azure_credentials(self):
        """No Azure credentials → speech_provider == 'pyttsx3'."""
        with patch("lingosips.services.registry.get_credential", return_value=""):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.speech_provider == "pyttsx3"

    def test_returns_azure_when_both_azure_credentials_configured(self):
        """Both Azure key + region present → speech_provider == 'azure'."""

        def _cred(key: str) -> str:
            return {
                AZURE_SPEECH_KEY: "az-key",
                AZURE_SPEECH_REGION: "eastus",
            }.get(key, "")

        with patch("lingosips.services.registry.get_credential", side_effect=_cred):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.speech_provider == "azure"

    def test_returns_pyttsx3_when_only_azure_key_but_no_region(self):
        """Azure key without region → speech_provider == 'pyttsx3' (both required)."""

        def _cred(key: str) -> str:
            if key == AZURE_SPEECH_KEY:
                return "az-key"
            return ""

        with patch("lingosips.services.registry.get_credential", side_effect=_cred):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.speech_provider == "pyttsx3"

    def test_reserved_latency_fields_are_none(self):
        """Reserved latency/timestamp fields must be None (not tracked yet in this story)."""
        with patch("lingosips.services.registry.get_credential", return_value=""):
            from lingosips.services.registry import get_service_status_info

            status = get_service_status_info()

        assert status.last_llm_latency_ms is None
        assert status.last_llm_success_at is None
        assert status.last_speech_latency_ms is None
        assert status.last_speech_success_at is None

    def test_does_not_raise_on_credential_errors(self):
        """get_service_status_info() must never raise — always return a status object."""
        with patch(
            "lingosips.services.registry.get_credential",
            side_effect=Exception("keyring error"),
        ):
            from lingosips.services.registry import get_service_status_info

            # Must not raise
            try:
                status = get_service_status_info()
                # If it doesn't raise, it should default to local providers
                assert status.llm_provider == "qwen_local"
            except Exception as e:
                pytest.fail(f"get_service_status_info() raised unexpectedly: {e}")
