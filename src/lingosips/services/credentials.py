"""Secure credential storage via OS keychain.

This is the ONLY module in lingosips that reads from or writes to keyring.
No other module may import keyring directly (see project-context.md#Layer Architecture).

Credentials are stored in the OS keychain (macOS Keychain, Windows Credential Locker,
Linux libsecret/kwallet). If no OS keychain is available (headless Linux), an encrypted
file store from keyrings.alt is used as fallback.
"""

from pathlib import Path

import keyring
import keyring.errors
import structlog

logger = structlog.get_logger(__name__)

# ── Service identifier ────────────────────────────────────────────────────────

KEYRING_SERVICE = "lingosips"

# ── Credential key constants — used by all modules that touch external services ─

OPENROUTER_API_KEY = "openrouter_api_key"
AZURE_SPEECH_KEY = "azure_speech_key"
AZURE_SPEECH_REGION = "azure_speech_region"
IMAGE_ENDPOINT_URL = "image_endpoint_url"
IMAGE_ENDPOINT_KEY = "image_endpoint_key"

# ── Fallback encrypted file path for headless environments ────────────────────

_FALLBACK_CRED_FILE = Path.home() / ".lingosips" / "credentials.enc"


# ── Fallback keyring setup ────────────────────────────────────────────────────


def _setup_fallback_keyring() -> None:
    """Configure file-based encrypted keyring when OS keychain is unavailable.

    keyring uses a ``fail.Keyring`` (or ``null.Keyring``) backend when no OS
    keychain is detected (common on headless Linux). Detect this and switch to
    EncryptedKeyring from keyrings.alt so credentials can still be persisted.
    """
    current_backend = type(keyring.get_keyring()).__name__.lower()
    if "fail" in current_backend or "null" in current_backend:
        try:
            from keyrings.alt.file import EncryptedKeyring  # type: ignore[import]

            kr = EncryptedKeyring()
            kr.file_path = str(_FALLBACK_CRED_FILE)
            # Ensure the parent directory exists before EncryptedKeyring tries to write
            _FALLBACK_CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
            keyring.set_keyring(kr)
            logger.info("keyring.fallback_configured", path=str(_FALLBACK_CRED_FILE))
        except ImportError:
            logger.warning("keyring.no_fallback_available", detail="keyrings.alt not installed")
        except Exception:  # noqa: BLE001
            # EncryptedKeyring instantiation or set_keyring failed (permissions, etc.)
            # Log and continue — credentials will raise at first use, but import succeeds.
            logger.warning("keyring.fallback_setup_failed", path=str(_FALLBACK_CRED_FILE))


# Called at module import time so the correct backend is active before any
# credential read/write operations.
_setup_fallback_keyring()


# ── Public API ────────────────────────────────────────────────────────────────


def get_credential(key: str) -> str | None:
    """Read a credential from the OS keychain.

    Returns None if the credential is not found or if the keychain raises an
    error — never propagates keyring exceptions to callers.

    SECURITY: Only the key name is logged — credential values are never logged.
    """
    try:
        return keyring.get_password(KEYRING_SERVICE, key)
    except keyring.errors.KeyringError:
        logger.warning("keyring.get_failed", key=key)
        return None


def set_credential(key: str, value: str) -> None:
    """Write a credential to the OS keychain.

    SECURITY: The value is never logged — only the key name appears in logs.
    Re-raises KeyringError so the caller knows the write did not succeed.
    """
    try:
        keyring.set_password(KEYRING_SERVICE, key, value)
    except keyring.errors.KeyringError:
        logger.error("keyring.set_failed", key=key)
        raise


def delete_credential(key: str) -> None:
    """Delete a credential from the OS keychain.

    Silent no-op if the credential does not exist or if the backend raises any
    KeyringError (including PasswordDeleteError).  Callers need not check for
    prior existence; a locked or unavailable backend is also treated as a no-op
    rather than propagating an unexpected exception.
    """
    try:
        keyring.delete_password(KEYRING_SERVICE, key)
    except keyring.errors.KeyringError:
        pass  # Already deleted, not found, or backend error — all treated as no-op
