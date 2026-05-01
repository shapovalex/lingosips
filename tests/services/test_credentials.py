"""Tests for services/credentials.py — secure keyring-based credential storage.

AC: 1, 4 — keyring integration; only credentials.py accesses keyring.
TDD: tests written before implementation (failing first).
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_keyring():
    """Mock keyring so tests never touch the OS keychain."""
    with patch("lingosips.services.credentials.keyring") as mock_kr:
        # Simulate a working keyring backend (not "fail" type)
        mock_backend = MagicMock()
        mock_backend.__class__ = MagicMock(__name__="MockKeyring")
        mock_kr.get_keyring.return_value = mock_backend
        mock_kr.get_password.return_value = None  # default: no credential stored
        mock_kr.errors.KeyringError = Exception
        mock_kr.errors.PasswordDeleteError = Exception
        yield mock_kr


class TestGetCredential:
    def test_returns_none_when_not_found(self, mock_keyring) -> None:
        """T4.5 — get_credential returns None for a missing key."""
        mock_keyring.get_password.return_value = None

        from lingosips.services.credentials import get_credential

        assert get_credential("openrouter_api_key") is None

    def test_returns_value_when_found(self, mock_keyring) -> None:
        """T4.3 — get_credential returns the stored value (round-trip read side)."""
        mock_keyring.get_password.return_value = "sk-abc123"

        from lingosips.services.credentials import get_credential

        result = get_credential("openrouter_api_key")
        assert result == "sk-abc123"
        mock_keyring.get_password.assert_called_once_with("lingosips", "openrouter_api_key")

    def test_returns_none_on_keyring_error(self, mock_keyring) -> None:
        """T4.8 — keyring error during get_credential returns None (no propagation)."""
        mock_keyring.get_password.side_effect = mock_keyring.errors.KeyringError("backend error")

        from lingosips.services.credentials import get_credential

        result = get_credential("openrouter_api_key")
        assert result is None  # Error swallowed, not propagated


class TestSetCredential:
    def test_calls_set_password(self, mock_keyring) -> None:
        """T4.3 — set_credential / get_credential round-trip (write side)."""
        from lingosips.services.credentials import set_credential

        set_credential("openrouter_api_key", "sk-secret123")
        mock_keyring.set_password.assert_called_once_with(
            "lingosips", "openrouter_api_key", "sk-secret123"
        )

    def test_reraises_on_keyring_error(self, mock_keyring) -> None:
        """set_credential re-raises KeyringError so callers know the write failed.

        The credential value must never appear in logs; only the key name is safe.
        """
        mock_keyring.set_password.side_effect = mock_keyring.errors.KeyringError("backend error")

        from lingosips.services.credentials import set_credential

        with pytest.raises(Exception):  # KeyringError propagates
            set_credential("openrouter_api_key", "sk-should-not-be-stored")


class TestDeleteCredential:
    def test_calls_delete_password(self, mock_keyring) -> None:
        """T4.4 — delete_credential removes the credential."""
        from lingosips.services.credentials import delete_credential

        delete_credential("openrouter_api_key")
        mock_keyring.delete_password.assert_called_once_with("lingosips", "openrouter_api_key")

    def test_silent_when_not_found(self, mock_keyring) -> None:
        """T4.6 — delete_credential does NOT raise if credential doesn't exist."""
        mock_keyring.delete_password.return_value = None  # No error, nothing to delete

        from lingosips.services.credentials import delete_credential

        # Must NOT raise
        delete_credential("nonexistent_key")

    def test_silent_on_password_delete_error(self, mock_keyring) -> None:
        """T4.7 — delete_credential does NOT raise on PasswordDeleteError (key not found)."""
        mock_keyring.delete_password.side_effect = mock_keyring.errors.PasswordDeleteError(
            "not found"
        )

        from lingosips.services.credentials import delete_credential

        # Must NOT raise
        delete_credential("openrouter_api_key")

    def test_silent_on_keyring_error(self, mock_keyring) -> None:
        """delete_credential silently swallows any KeyringError (e.g. locked OS keychain).

        PasswordDeleteError is a KeyringError subclass; any broader backend error
        (locked keychain, backend unavailable) must also be a silent no-op.
        """
        mock_keyring.delete_password.side_effect = mock_keyring.errors.KeyringError(
            "backend unavailable"
        )

        from lingosips.services.credentials import delete_credential

        # Must NOT raise — broader KeyringError treated identically to PasswordDeleteError
        delete_credential("openrouter_api_key")


class TestSetupFallbackKeyring:
    """Tests for _setup_fallback_keyring() branches added in code review.

    The module-level call at import time uses the mocked keyring (MockKeyring — not
    a "fail" backend) so the if-branch is never taken there. These tests call the
    function directly with a controlled fail-type backend to cover the new code paths.
    """

    def test_configures_encrypted_keyring_on_fail_backend(self, mock_keyring) -> None:
        """_setup_fallback_keyring installs EncryptedKeyring when OS backend reports 'fail'."""
        from pathlib import Path
        from unittest.mock import patch

        class _FailBackend:
            """Stub matching keyring.backends.fail.Keyring class-name pattern."""

        mock_keyring.get_keyring.return_value = _FailBackend()

        with (
            patch(
                "lingosips.services.credentials._FALLBACK_CRED_FILE",
                new=Path("/tmp/test-cred.enc"),
            ),
            patch("keyrings.alt.file.EncryptedKeyring") as mock_enc,
        ):
            from lingosips.services.credentials import _setup_fallback_keyring

            _setup_fallback_keyring()

        mock_enc.assert_called_once()
        mock_keyring.set_keyring.assert_called_once_with(mock_enc.return_value)

    def test_non_import_exception_in_setup_is_swallowed(self, mock_keyring) -> None:
        """_setup_fallback_keyring catches non-ImportError exceptions gracefully.

        If EncryptedKeyring() raises (e.g. permissions, bad home dir), the module
        must still import successfully — the exception is logged and discarded.
        """
        from pathlib import Path
        from unittest.mock import patch

        class _FailBackend:
            """Stub matching keyring.backends.fail.Keyring class-name pattern."""

        mock_keyring.get_keyring.return_value = _FailBackend()

        with (
            patch(
                "lingosips.services.credentials._FALLBACK_CRED_FILE",
                new=Path("/tmp/test-cred.enc"),
            ),
            patch("keyrings.alt.file.EncryptedKeyring", side_effect=OSError("permission denied")),
        ):
            from lingosips.services.credentials import _setup_fallback_keyring

            # Must NOT raise — non-ImportError exceptions are caught and logged
            _setup_fallback_keyring()

        mock_keyring.set_keyring.assert_not_called()


class TestCredentialConstants:
    def test_keyring_service_constant(self) -> None:
        """AC4 — KEYRING_SERVICE constant is defined correctly."""
        from lingosips.services.credentials import KEYRING_SERVICE

        assert KEYRING_SERVICE == "lingosips"

    def test_credential_key_constants_defined(self) -> None:
        """AC4 — All credential key constants are defined in credentials.py."""
        import lingosips.services.credentials as creds

        assert creds.OPENROUTER_API_KEY == "openrouter_api_key"
        assert creds.AZURE_SPEECH_KEY == "azure_speech_key"
        assert creds.AZURE_SPEECH_REGION == "azure_speech_region"
        assert creds.IMAGE_ENDPOINT_URL == "image_endpoint_url"
        assert creds.IMAGE_ENDPOINT_KEY == "image_endpoint_key"
