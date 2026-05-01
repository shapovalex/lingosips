# Story 1.3: Secure Credential Storage Foundation

Status: done

## Story

As a user,
I want all API keys stored via the OS keychain (never plaintext) and all logs stripped of credential patterns,
so that my credentials are secure even if log files or config files are examined.

## Acceptance Criteria

1. **Given** any API key is saved in the app
   **When** `services/credentials.py` writes it
   **Then** the `keyring` library stores it in the OS keychain (macOS Keychain, Windows Credential Locker, Linux libsecret/kwallet)
   **And** if no OS keychain is available, an encrypted file store is used as fallback
   **And** the credential is never written to SQLite, `.env` files, or any plaintext config

2. **Given** the application produces any log output
   **When** a string matching a credential pattern is present in the data
   **Then** the `structlog` credential-scrubbing processor replaces it with `[REDACTED]` before emission

3. **Given** an unhandled exception occurs
   **When** the Python traceback or error response is generated
   **Then** no credential values appear in the traceback, error detail, or HTTP error response

4. **Given** any module needs to read a credential
   **Then** it must call `services/credentials.py` — no module reads from `keyring` directly

5. **Given** `LINGOSIPS_LOG_LEVEL=DEBUG` is set
   **When** verbose logging runs
   **Then** credentials are still scrubbed — debug logging does not bypass the credential processor

## Tasks / Subtasks

- [x] **T1: Add `keyrings.alt` dependency** (AC: 1)
  - [x] T1.1: Run `uv add "keyrings.alt"` to add encrypted file store fallback
  - [x] T1.2: Verify `pyproject.toml` is updated with the new dependency

- [x] **T2: Create `services/credentials.py`** (AC: 1, 4) — TDD: write failing tests first
  - [x] T2.1: Define `KEYRING_SERVICE = "lingosips"` constant
  - [x] T2.2: Define credential key constants (see Dev Notes §CredentialKeys)
  - [x] T2.3: Implement `get_credential(key: str) -> str | None`
  - [x] T2.4: Implement `set_credential(key: str, value: str) -> None`
  - [x] T2.5: Implement `delete_credential(key: str) -> None`
  - [x] T2.6: Implement `_setup_fallback_keyring()` for headless environments (see Dev Notes §FallbackKeyring)
  - [x] T2.7: Call `_setup_fallback_keyring()` at module import time if OS keychain unavailable

- [x] **T3: Update `api/app.py` exception handlers** (AC: 3)
  - [x] T3.1: Add `_scrub_from_string()` helper that applies the same patterns as `core/logging.py`
  - [x] T3.2: Update existing `StarletteHTTPException` handler to scrub any string values in `exc.detail`
  - [x] T3.3: Add a new generic `Exception` handler (500 errors) that returns RFC 7807 body `{"type": "/errors/internal", "title": "Internal server error", "status": 500}` — never exposes raw traceback or exception message

- [x] **T4: Write tests for `services/credentials.py`** (AC: 1, 4) — TDD: failing first
  - [x] T4.1: Create `tests/services/__init__.py`
  - [x] T4.2: Create `tests/services/test_credentials.py`
  - [x] T4.3: Test `set_credential` / `get_credential` round-trip (mocked keyring)
  - [x] T4.4: Test `delete_credential` removes the credential
  - [x] T4.5: Test `get_credential` returns `None` for missing key
  - [x] T4.6: Test `delete_credential` does NOT raise if credential doesn't exist
  - [x] T4.7: Test `delete_credential` does NOT raise on `PasswordDeleteError` (key not found)
  - [x] T4.8: Test keyring error during `get_credential` returns `None` (no propagation)

- [x] **T5: Tests for exception handler credential scrubbing** (AC: 3, 5)
  - [x] T5.1: Add test to `tests/api/test_app.py`: HTTP exception with credential in `detail` → scrubbed in response
  - [x] T5.2: Add test: unhandled exception (500) → response body never contains traceback or exception message
  - [x] T5.3: Add test to `tests/core/test_logging.py`: with `LINGOSIPS_LOG_LEVEL=DEBUG`, credential patterns still appear as `[REDACTED]` in log output (verify scrubbing applies at DEBUG level)

## Dev Notes

### ⚠️ What Already Exists — DO NOT Recreate

**`core/logging.py`** — already implemented in Story 1.1 with `_scrub_credentials` processor. This covers AC2 and partially AC5. DO NOT modify `core/logging.py` — it is already correct.

**`tests/core/test_logging.py`** — already has `TestCredentialScrubbing` class with 5 passing tests for `_scrub_credentials`. DO NOT duplicate those tests. Only add T5.3 (the missing DEBUG-level integration test).

**`keyring>=25.7.0`** — already in `pyproject.toml`. DO NOT add it again.

**`configure_logging()`** — already called first in `__main__.py` startup sequence. Credential scrubbing is active from the very first log line.

### §CredentialKeys — Constants in `services/credentials.py`

```python
KEYRING_SERVICE = "lingosips"

# Credential key constants — used by all future stories that touch external services
OPENROUTER_API_KEY = "openrouter_api_key"
AZURE_SPEECH_KEY = "azure_speech_key"
AZURE_SPEECH_REGION = "azure_speech_region"
IMAGE_ENDPOINT_URL = "image_endpoint_url"
IMAGE_ENDPOINT_KEY = "image_endpoint_key"
```

Stories 1.5, 1.6, and 2.3 will use these constants when they need to read/write credentials. Define them all here now — that is the contract established by this story.

### §FallbackKeyring — Headless / No-Keychain Fallback

When `keyring` detects no OS backend (common on headless Linux), it configures a `fail.Keyring` that raises `keyring.errors.NoKeyringError` on every call. Detect this and switch to `EncryptedKeyring` from `keyrings.alt`.

```python
from pathlib import Path

import keyring
import keyring.errors
import structlog

logger = structlog.get_logger(__name__)

_FALLBACK_CRED_FILE = Path.home() / ".lingosips" / "credentials.enc"


def _setup_fallback_keyring() -> None:
    """Configure file-based encrypted keyring when OS keychain is unavailable."""
    current_backend = type(keyring.get_keyring()).__name__.lower()
    if "fail" in current_backend or "null" in current_backend:
        try:
            from keyrings.alt.file import EncryptedKeyring  # type: ignore[import]
            kr = EncryptedKeyring()
            kr.file_path = str(_FALLBACK_CRED_FILE)
            keyring.set_keyring(kr)
            logger.info("keyring.fallback_configured", path=str(_FALLBACK_CRED_FILE))
        except ImportError:
            logger.warning("keyring.no_fallback_available", detail="keyrings.alt not installed")


# Call at module import time
_setup_fallback_keyring()
```

**Important**: `EncryptedKeyring` from `keyrings.alt` uses a master password. On a desktop (non-CI) system, this prompts once on first use and caches. In tests, the backend is mocked — this code path is never hit in test runs.

### §CredentialsModule — Full Implementation Pattern

```python
def get_credential(key: str) -> str | None:
    """Read a credential from the OS keychain. Returns None if not found or on error."""
    try:
        return keyring.get_password(KEYRING_SERVICE, key)
    except keyring.errors.KeyringError:
        logger.warning("keyring.get_failed", key=key)
        return None


def set_credential(key: str, value: str) -> None:
    """Write a credential to the OS keychain."""
    keyring.set_password(KEYRING_SERVICE, key, value)


def delete_credential(key: str) -> None:
    """Delete a credential from the OS keychain. Silent no-op if not found."""
    try:
        keyring.delete_password(KEYRING_SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass  # Already deleted or never existed — not an error
```

**CRITICAL**: The `logger.warning` call in `get_credential` passes only `key=key` — never `value`. No credential values ever appear in logs.

### §ExceptionHandler — Credential Scrubbing in `api/app.py`

The current `app.py` has only a `StarletteHTTPException` handler. Two changes needed:

**1. Add credential scrubbing to the existing HTTP handler:**
```python
import re

_SCRUB_PATTERNS = [
    re.compile(r"(api[_-]?key|apikey|password|passwd|secret|token)[=:\s\"']+\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]+"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]

def _scrub_string(s: str) -> str:
    for pattern in _SCRUB_PATTERNS:
        s = pattern.sub("[REDACTED]", s)
    return s

def _scrub_detail(detail: str | dict | None) -> str | dict:
    if isinstance(detail, str):
        return _scrub_string(detail)
    if isinstance(detail, dict):
        return {k: _scrub_string(v) if isinstance(v, str) else v for k, v in detail.items()}
    return detail or {}
```

Apply `_scrub_detail(exc.detail)` before building the RFC 7807 body.

**2. Add a generic `Exception` handler (500 errors):**
```python
from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

@application.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the real exception (structlog scrubbing applies) — never expose it to caller
    logger.error("unhandled_exception", exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "type": "/errors/internal",
            "title": "Internal server error",
            "status": 500,
        },
        headers={"Content-Type": "application/problem+json"},
    )
```

**CRITICAL**: The `logger.error` call passes only `exc_type=type(exc).__name__` — NEVER `str(exc)`, NEVER `repr(exc)`, NEVER the traceback. Exception messages may contain credential values. Only the exception class name is safe to log.

### §Testing — Mocking Keyring

Tests must NEVER touch the real OS keychain. Mock the entire `keyring` module:

```python
# tests/services/test_credentials.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_keyring():
    """Mock keyring so tests never touch the OS keychain."""
    with patch("lingosips.services.credentials.keyring") as mock_kr:
        # Simulate a working keyring backend (not "fail" type)
        mock_kr.get_keyring.return_value = MagicMock(__class__=MagicMock(__name__="MockKeyring"))
        mock_kr.get_password.return_value = None  # default: no credential stored
        mock_kr.errors.KeyringError = Exception
        mock_kr.errors.PasswordDeleteError = Exception
        yield mock_kr


class TestGetCredential:
    def test_returns_none_when_not_found(self, mock_keyring):
        mock_keyring.get_password.return_value = None
        from lingosips.services.credentials import get_credential
        assert get_credential("openrouter_api_key") is None

    def test_returns_value_when_found(self, mock_keyring):
        mock_keyring.get_password.return_value = "sk-abc123"
        from lingosips.services.credentials import get_credential
        result = get_credential("openrouter_api_key")
        assert result == "sk-abc123"
        mock_keyring.get_password.assert_called_once_with("lingosips", "openrouter_api_key")

    def test_returns_none_on_keyring_error(self, mock_keyring):
        mock_keyring.get_password.side_effect = mock_keyring.errors.KeyringError("backend error")
        from lingosips.services.credentials import get_credential
        result = get_credential("openrouter_api_key")
        assert result is None  # Error swallowed, not propagated


class TestSetCredential:
    def test_calls_set_password(self, mock_keyring):
        from lingosips.services.credentials import set_credential
        set_credential("openrouter_api_key", "sk-secret123")
        mock_keyring.set_password.assert_called_once_with("lingosips", "openrouter_api_key", "sk-secret123")


class TestDeleteCredential:
    def test_calls_delete_password(self, mock_keyring):
        from lingosips.services.credentials import delete_credential
        delete_credential("openrouter_api_key")
        mock_keyring.delete_password.assert_called_once_with("lingosips", "openrouter_api_key")

    def test_silent_on_password_delete_error(self, mock_keyring):
        mock_keyring.delete_password.side_effect = mock_keyring.errors.PasswordDeleteError("not found")
        from lingosips.services.credentials import delete_credential
        # Must NOT raise
        delete_credential("openrouter_api_key")
```

**Note**: The `patch("lingosips.services.credentials.keyring")` pattern patches keyring within the module's namespace. Import the module AFTER patching to ensure the mock takes effect properly.

### §DebugLoggingTest — AC5 Test for `test_logging.py`

Add this to `tests/core/test_logging.py` in the `TestCredentialScrubbing` class:

```python
def test_debug_level_still_scrubs(self, monkeypatch, capsys) -> None:
    """AC5: Credentials scrubbed even when LINGOSIPS_LOG_LEVEL=DEBUG."""
    from lingosips.core.logging import configure_logging

    monkeypatch.setenv("LINGOSIPS_LOG_LEVEL", "DEBUG")
    configure_logging()

    import structlog
    log = structlog.get_logger("test_debug_scrub")
    log.debug("debug event", api_key="sk-supersecret999")

    captured = capsys.readouterr()
    assert "sk-supersecret999" not in captured.out
    assert "sk-supersecret999" not in captured.err
```

### §ExceptionHandlerTests — Tests in `tests/api/test_app.py`

Add these test classes to the existing `test_app.py`:

```python
class TestExceptionHandlerCredentialScrubbing:
    async def test_http_exception_with_credential_in_detail_is_scrubbed(self, client) -> None:
        """AC3: Credential in exc.detail must not appear in HTTP response."""
        # This tests the exception handler scrubs string details
        # Set up a route that raises with a credential-containing detail
        from fastapi import HTTPException
        from lingosips.api.app import app

        @app.get("/test-credential-leak")
        async def _leak():
            raise HTTPException(status_code=400, detail="Error: api_key=sk-leakedsecret123 is invalid")

        response = await client.get("/test-credential-leak")
        assert response.status_code == 400
        assert "sk-leakedsecret123" not in response.text
        assert "[REDACTED]" in response.text or "Error" in response.text

        # Clean up the test route
        app.routes.pop()

    async def test_unhandled_exception_returns_generic_500(self, client) -> None:
        """AC3: Unhandled exceptions never expose traceback or exception message."""
        from lingosips.api.app import app

        @app.get("/test-unhandled-exception")
        async def _raise():
            raise RuntimeError("api_key=sk-verysecretvalue123 caused a crash")

        response = await client.get("/test-unhandled-exception")
        assert response.status_code == 500
        assert "sk-verysecretvalue123" not in response.text
        assert "RuntimeError" not in response.text
        body = response.json()
        assert body["type"] == "/errors/internal"
        assert body["status"] == 500

        app.routes.pop()
```

**Alternative test approach**: If dynamic route injection is fragile in your test environment, create a fixture in `conftest.py` that mounts these test-only routes on the test app at session scope, then cleans them up after.

### §FileStructure — New and Modified Files

```
src/lingosips/
└── services/
    └── credentials.py          ← NEW

tests/
└── services/
    ├── __init__.py              ← NEW (empty)
    └── test_credentials.py     ← NEW

pyproject.toml                  ← UPDATED (add keyrings.alt)
src/lingosips/api/app.py        ← UPDATED (add generic 500 handler + credential scrubbing)
tests/core/test_logging.py      ← UPDATED (add T5.3 DEBUG-level test)
tests/api/test_app.py           ← UPDATED (add T5.1, T5.2 exception handler tests)
```

**NEVER create `services/registry.py` in this story** — that's Story 1.5 (provider fallback). `credentials.py` is pure keyring I/O with no awareness of providers.

**NEVER create `api/settings.py` in this story** — that's Story 2.3.

### §Ruff Compliance

After all Python changes, run:
```bash
uv run ruff check --fix src/lingosips/services/credentials.py tests/services/
```

Common ruff issues to pre-empt:
- Import order: stdlib → third-party (`keyring`, `structlog`) → local (`lingosips.*`)
- `type: ignore[import]` comment on `from keyrings.alt.file import EncryptedKeyring` (optional dep)
- No unused imports (don't import `MagicMock` if you use `Mock`)

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `import keyring` in `api/cards.py` | `from lingosips.services.credentials import get_credential` |
| `logger.error("error", message=str(exc))` | `logger.error("error", exc_type=type(exc).__name__)` |
| `logger.debug("got key", value=api_key)` | Never log credential values — log only key names |
| `keyring.set_password("lingosips", "key", val)` outside credentials.py | Only `credentials.set_credential("key", val)` |
| `raise RuntimeError(str(exc))` in exception handler | Return `JSONResponse({"type": "/errors/internal", ...})` |
| `SQLModel.create_all()` anywhere | Not applicable to this story — no new DB models |
| Adding new Alembic migration | Not applicable to this story — no schema changes |
| Storing credentials in `Settings` SQLModel table | Credentials in keyring ONLY — never in DB |

### §NoPythonChanges — Story 1.2 Reminder

Story 1.2 was frontend-only (no Python changes). The last Python work was Story 1.1. The test suite was last run with Story 1.1's changes. Verify `uv run pytest tests/ --cov=src/lingosips` passes before starting this story.

### §CoverageGate

The 90% backend coverage gate must remain satisfied after this story. New files:
- `services/credentials.py` — must be fully covered by `tests/services/test_credentials.py`
- New exception handler code in `app.py` — must be covered by tests in `test_app.py`

### Project Structure Notes

**Layer compliance:**
- `services/credentials.py` is in `services/` — correct location per architecture
- It reads from `keyring` (external library) — this is appropriate for a services/ module
- It imports `structlog` for logging — correct (not `logging` directly)
- It does NOT import `fastapi`, `SQLModel`, or `AsyncSession` — correct per architecture

**Architecture rule enforcement:**
- `services/credentials.py` = "ONLY reader/writer of keyring — no other module touches keyring" [Source: project-context.md#Layer Architecture & Boundaries]
- All logs via `structlog` — never `print()` or `logging` directly [Source: project-context.md#Security Rules]

### References

- Story 1.3 acceptance criteria: [Source: epics.md#Story 1.3]
- `services/credentials.py` is the ONLY keyring reader/writer: [Source: project-context.md#Layer Architecture & Boundaries]
- `keyring>=25.7.0` already in dependencies: [Source: pyproject.toml]
- `_scrub_credentials` processor already in `core/logging.py`: [Source: Story 1.1 implementation]
- `configure_logging()` called at startup: [Source: src/lingosips/__main__.py line 21]
- RFC 7807 error format: [Source: project-context.md#API Design Rules]
- Credential scrubbing patterns: [Source: src/lingosips/core/logging.py lines 23-27]
- Security rule — credentials never in logs: [Source: project-context.md#Security Rules]
- Tests must be written BEFORE implementation (TDD): [Source: project-context.md#Testing Rules]
- `keyring` library API: `keyring.get_password(service, username)`, `set_password()`, `delete_password()`, `errors.KeyringError`, `errors.PasswordDeleteError`
- `keyrings.alt` encrypted file fallback: headless Linux environments without GNOME/KWallet
- Test DB: uses in-memory SQLite — credential tests use mocked keyring, never in-memory keyring

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

- T5.1/T5.2: Dynamic route injection into `app` after test client creation returned 404 because Starlette's middleware stack is compiled on first request. Switched to direct handler invocation (same pattern as `TestRFC7807DictDetail`).
- `_setup_fallback_keyring()` internal branches (lines 48–56) remain uncovered in unit tests — by design per Dev Notes ("backend is mocked in tests"). Total coverage 90.35% satisfies the 90% gate.

### Completion Notes List

- **T1**: Added `keyrings-alt>=5.0.2` via `uv add "keyrings.alt"` — `pyproject.toml` updated.
- **T2**: Created `src/lingosips/services/credentials.py` with `KEYRING_SERVICE`, all 5 credential key constants, `get_credential`, `set_credential`, `delete_credential`, and `_setup_fallback_keyring()`. Mocked-keyring unit tests (T4) were written first (TDD RED phase), then implementation made them GREEN.
- **T3**: Updated `src/lingosips/api/app.py` — added `_scrub_string()` / `_scrub_detail()` helpers, applied credential scrubbing to the existing `StarletteHTTPException` handler, and added a new generic `Exception` handler returning a safe RFC 7807 500 body without exposing exception message or traceback.
- **T4**: Created `tests/services/__init__.py` and `tests/services/test_credentials.py` with 9 tests covering all specified cases (round-trip, delete, missing key, PasswordDeleteError, KeyringError, constants). All mocked — no OS keychain access.
- **T5**: Added `test_debug_level_still_scrubs` to `tests/core/test_logging.py` (AC5 verified). Added `TestExceptionHandlerCredentialScrubbing` to `tests/api/test_app.py` (T5.1 HTTP scrub, T5.2 generic 500 safe response).
- All 49 tests pass. No regressions. Coverage: 90.35% (gate: 90%).

### File List

- `src/lingosips/services/credentials.py` — NEW
- `tests/services/__init__.py` — NEW
- `tests/services/test_credentials.py` — NEW
- `pyproject.toml` — UPDATED (added `keyrings-alt>=5.0.2`)
- `uv.lock` — UPDATED (dependency lockfile)
- `src/lingosips/api/app.py` — UPDATED (credential scrubbing helpers + generic 500 handler)
- `tests/api/test_app.py` — UPDATED (added `TestExceptionHandlerCredentialScrubbing`)
- `tests/core/test_logging.py` — UPDATED (added `test_debug_level_still_scrubs`)

## Review Findings

- [x] [Review][Patch] `_scrub_detail` returns `{}` for `None` detail — invalid RFC 7807 body [`api/app.py:42`] — **Fixed**: returns `""` so RFC 7807 envelope is built by caller
- [x] [Review][Patch] `_scrub_detail` shallow-only — nested dict values pass through unscrubbed [`api/app.py:41`] — **Fixed**: recursive scrub of str/dict values
- [x] [Review][Patch] `set_credential` has no error handling — KeyringError propagates raw to caller [`credentials.py:87`] — **Fixed**: try/except logs key (never value) and re-raises
- [x] [Review][Patch] `_setup_fallback_keyring` only catches `ImportError` — other exceptions crash module import [`credentials.py:48-56`] — **Fixed**: added `except Exception` with warning log
- [x] [Review][Patch] `delete_credential` catches only `PasswordDeleteError`, not broader `KeyringError` [`credentials.py:96-99`] — **Fixed**: catches `KeyringError` (base class) uniformly
- [x] [Review][Patch] `_FALLBACK_CRED_FILE` parent directory never created before `EncryptedKeyring` setup [`credentials.py:53`] — **Fixed**: `mkdir(parents=True, exist_ok=True)` added
- [x] [Review][Patch] `_SCRUB_PATTERNS` duplicated from `core/logging.py` — sync drift risk [`api/app.py:22-26`] — **Fixed**: `CREDENTIAL_PATTERNS` exported from `core/logging.py`, imported in `app.py`
- [x] [Review][Patch] `test_debug_level_still_scrubs` has only negative assertions — vacuous pass if logging disabled [`tests/core/test_logging.py:103-105`] — **Fixed**: added positive `assert "[REDACTED]" in captured.out or ...`
- [x] [Review][Defer] Fallback keyring detection uses fragile class-name string matching — matches spec exactly, pre-existing architectural decision
- [x] [Review][Defer] `_setup_fallback_keyring()` ImportError branch intentionally uncovered — documented in agent record; 94.14% coverage achieved
- [x] [Review][Defer] AC4 enforcement is convention-only — CI import-boundary gate is out of scope for this story

## Change Log

- 2026-04-30: Story 1.3 implemented — secure credential storage via OS keychain (`keyrings.alt` fallback for headless), credential scrubbing in HTTP exception responses, and safe generic 500 handler. 12 new tests added (9 credential + 3 exception handler/logging). All ACs satisfied.
