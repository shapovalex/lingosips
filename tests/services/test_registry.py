"""Tests for services/registry.py — written BEFORE implementation (TDD).

Covers get_llm_provider(): OpenRouter selection, Qwen local fallback, 503 on model not ready.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from lingosips.services.llm.openrouter import OpenRouterProvider
from lingosips.services.llm.qwen_local import QwenLocalProvider


@pytest.mark.anyio
class TestGetLLMProvider:
    def test_returns_openrouter_when_key_configured(self):
        with patch("lingosips.services.registry.get_credential") as mock_cred:
            mock_cred.side_effect = lambda k: "sk-abc" if k == "openrouter_api_key" else None
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = True
                import lingosips.services.registry as reg

                reg._qwen_provider = None  # reset singleton
                provider = reg.get_llm_provider()
        assert isinstance(provider, OpenRouterProvider)
        assert provider.provider_name == "OpenRouter"

    def test_returns_qwen_local_when_no_api_key(self, tmp_path):
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"x")
        with patch("lingosips.services.registry.get_credential", return_value=None):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = True
                mock_mm.get_model_path.return_value = model_file
                import lingosips.services.registry as reg

                reg._qwen_provider = None  # reset singleton
                provider = reg.get_llm_provider()
        assert isinstance(provider, QwenLocalProvider)
        assert provider.provider_name == "Local Qwen"

    def test_raises_503_when_model_not_ready(self):
        with patch("lingosips.services.registry.get_credential", return_value=None):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = False
                mock_mm.get_model_path.return_value = "/nonexistent"
                import lingosips.services.registry as reg

                reg._qwen_provider = None
                with pytest.raises(HTTPException) as exc_info:
                    reg.get_llm_provider()
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["type"] == "/errors/model-downloading"

    def test_empty_string_api_key_treated_as_no_key(self, tmp_path):
        """Empty string from keyring must be treated the same as None."""
        model_file = tmp_path / "qwen.gguf"
        model_file.write_bytes(b"x")
        with patch("lingosips.services.registry.get_credential", return_value=""):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = True
                mock_mm.get_model_path.return_value = model_file
                import lingosips.services.registry as reg

                reg._qwen_provider = None
                provider = reg.get_llm_provider()
        assert isinstance(provider, QwenLocalProvider)

    def test_503_detail_follows_rfc7807(self):
        """503 error detail must follow RFC 7807 shape."""
        with patch("lingosips.services.registry.get_credential", return_value=None):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = False
                mock_mm.get_model_path.return_value = "/nonexistent"
                import lingosips.services.registry as reg

                reg._qwen_provider = None
                with pytest.raises(HTTPException) as exc_info:
                    reg.get_llm_provider()
        detail = exc_info.value.detail
        assert "type" in detail
        assert "title" in detail
        assert "detail" in detail
        assert "status" in detail
        assert detail["status"] == 503

    def test_503_title_matches_ac3_spec(self):
        """AC3: 503 title must be exactly 'Model is downloading'."""
        with patch("lingosips.services.registry.get_credential", return_value=None):
            with patch("lingosips.services.registry._model_manager") as mock_mm:
                mock_mm.is_ready.return_value = False
                mock_mm.get_model_path.return_value = "/nonexistent"
                import lingosips.services.registry as reg

                reg._qwen_provider = None
                with pytest.raises(HTTPException) as exc_info:
                    reg.get_llm_provider()
        assert exc_info.value.detail["title"] == "Model is downloading"

    def test_openrouter_model_imported_from_credentials(self):
        """registry.py must use OPENROUTER_MODEL from credentials.py (no duplicate constant)."""
        import lingosips.services.registry as reg

        # The module must NOT define its own OPENROUTER_MODEL_KEY constant
        assert not hasattr(reg, "OPENROUTER_MODEL_KEY"), (
            "OPENROUTER_MODEL_KEY must not exist in registry"
            " — import OPENROUTER_MODEL from credentials"
        )
        # The OPENROUTER_MODEL name from credentials must be used internally
        from lingosips.services.credentials import OPENROUTER_MODEL

        assert OPENROUTER_MODEL == "openrouter_model"


# --- get_speech_provider() tests ---


@pytest.mark.anyio
class TestGetSpeechProvider:
    def test_returns_azure_when_both_key_and_region_configured(self):
        from lingosips.services.speech.azure import AzureSpeechProvider

        def mock_cred(k):
            return {"azure_speech_key": "key-123", "azure_speech_region": "eastus"}.get(k)

        with patch("lingosips.services.registry.get_credential", side_effect=mock_cred):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            provider = reg.get_speech_provider()

        assert isinstance(provider, AzureSpeechProvider)
        assert provider.provider_name == "Azure Speech"

    def test_returns_pyttsx3_when_no_azure_key(self):
        from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider

        with patch("lingosips.services.registry.get_credential", return_value=None):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            provider = reg.get_speech_provider()

        assert isinstance(provider, Pyttsx3Provider)
        assert provider.provider_name == "Local pyttsx3"

    def test_returns_pyttsx3_when_key_set_but_region_missing(self):
        """Both key AND region required — missing region → pyttsx3 fallback."""
        from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider

        def mock_cred(k):
            return "key-123" if k == "azure_speech_key" else None

        with patch("lingosips.services.registry.get_credential", side_effect=mock_cred):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            provider = reg.get_speech_provider()

        assert isinstance(provider, Pyttsx3Provider)

    def test_returns_pyttsx3_when_region_set_but_key_missing(self):
        """Both key AND region required — missing key → pyttsx3 fallback."""
        from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider

        def mock_cred(k):
            return "eastus" if k == "azure_speech_region" else None

        with patch("lingosips.services.registry.get_credential", side_effect=mock_cred):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            provider = reg.get_speech_provider()

        assert isinstance(provider, Pyttsx3Provider)

    def test_empty_string_key_treated_as_no_credential(self):
        """Empty string from keyring must be treated same as None."""
        from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider

        with patch("lingosips.services.registry.get_credential", return_value=""):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            provider = reg.get_speech_provider()

        assert isinstance(provider, Pyttsx3Provider)

    def test_pyttsx3_provider_is_cached_singleton(self):
        """Same Pyttsx3Provider instance returned on repeated calls."""
        with patch("lingosips.services.registry.get_credential", return_value=None):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            p1 = reg.get_speech_provider()
            p2 = reg.get_speech_provider()

        assert p1 is p2  # same cached instance

    def test_azure_provider_not_cached_new_instance_per_call(self):
        """AzureSpeechProvider is NOT a singleton — new instance per call (stateless)."""
        from lingosips.services.speech.azure import AzureSpeechProvider

        def mock_cred(k):
            return {"azure_speech_key": "key", "azure_speech_region": "eastus"}.get(k)

        with patch("lingosips.services.registry.get_credential", side_effect=mock_cred):
            import lingosips.services.registry as reg

            reg._pyttsx3_provider = None
            p1 = reg.get_speech_provider()
            p2 = reg.get_speech_provider()

        assert isinstance(p1, AzureSpeechProvider)
        assert isinstance(p2, AzureSpeechProvider)
