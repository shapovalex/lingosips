# Story 1.6: Speech Provider Abstraction & Local TTS Fallback

Status: done

## Story

As a user,
I want speech synthesis to work out-of-the-box using local pyttsx3 when no Azure Speech credentials are configured,
so that audio is available with zero configuration.

## Acceptance Criteria

1. **Given** no Azure Speech credentials are configured
   **When** TTS is requested
   **Then** `services/registry.py`'s `get_speech_provider()` returns `Pyttsx3Provider`
   **And** audio is synthesized using `pyttsx3` without error

2. **Given** Azure Speech credentials are configured in the keyring
   **When** TTS is requested
   **Then** `services/registry.py`'s `get_speech_provider()` returns `AzureSpeechProvider`
   **And** synthesis uses the Azure Speech REST API for higher-quality audio

3. **Given** `get_speech_provider()` is called anywhere in router code
   **Then** it is always resolved via FastAPI `Depends(get_speech_provider)` — direct instantiation of providers is never used outside `services/`

4. **Given** `AbstractSpeechProvider` is defined in `services/speech/base.py`
   **Then** it declares two abstract methods: `synthesize(text: str, language: str) → bytes` and `evaluate_pronunciation(audio: bytes, target: str, language: str) → SyllableResult`
   **And** `Pyttsx3Provider` implements `synthesize()` and raises `NotImplementedError` for `evaluate_pronunciation()` — TTS-only providers do not evaluate speech
   **And** `AzureSpeechProvider` implements `synthesize()` (Story 1.6) and stubs `evaluate_pronunciation()` to raise `NotImplementedError("Implemented in Story 4.1")`
   **And** `WhisperLocalProvider` stubs `evaluate_pronunciation()` to raise `NotImplementedError("Implemented in Story 4.1")` and raises `NotImplementedError` for `synthesize()` — evaluation-only providers do not perform TTS
   **And** `SyllableResult` is a dataclass defined in `services/speech/base.py`: `overall_correct: bool`, `syllables: list[SyllableDetail]`, `correction_message: str | None`
   **And** `SyllableDetail` is a dataclass defined in `services/speech/base.py`: `syllable: str`, `correct: bool`, `score: float = 1.0`

5. **Given** a new provider class is added to `services/speech/` implementing `AbstractSpeechProvider`
   **When** `get_speech_provider()` returns it
   **Then** no changes to `core/` business logic are required — the interface is the only contract

## Tasks / Subtasks

- [x] **T1: Create `services/speech/base.py` — `AbstractSpeechProvider`, `SyllableResult`, `SyllableDetail`** (AC: 4, 5) — TDD: write failing import test first
  - [x] T1.1: Define `SyllableDetail` dataclass: `syllable: str`, `correct: bool`, `score: float = 1.0`
  - [x] T1.2: Define `SyllableResult` dataclass: `overall_correct: bool`, `syllables: list[SyllableDetail]`, `correction_message: str | None`
  - [x] T1.3: Define `AbstractSpeechProvider(ABC)` with abstract methods and properties (see Dev Notes §AbstractSpeechProvider)
  - [x] T1.4: Abstract method `async synthesize(text: str, language: str) → bytes`
  - [x] T1.5: Abstract method `async evaluate_pronunciation(audio: bytes, target: str, language: str) → SyllableResult`
  - [x] T1.6: Abstract property `provider_name: str` — human-readable name for `ServiceStatusIndicator` (Story 1.10)
  - [x] T1.7: Abstract property `model_name: str` — model/service identifier for display

- [x] **T2: Create `services/speech/pyttsx3_local.py` — `Pyttsx3Provider`** (AC: 1, 4) — TDD: write failing tests first
  - [x] T2.1: `Pyttsx3Provider()` constructor — no arguments; DO NOT call `pyttsx3.init()` at module load time
  - [x] T2.2: Implement `synthesize()` — calls `_synthesize_sync()` via `asyncio.get_running_loop().run_in_executor(None, ...)` (see Dev Notes §Pyttsx3Provider)
  - [x] T2.3: Implement `_synthesize_sync(text, language) → bytes` — creates fresh `pyttsx3.init()` per call (thread-safe), saves to temp WAV file, reads bytes, cleans up (see Dev Notes §Pyttsx3Provider)
  - [x] T2.4: `evaluate_pronunciation()` raises `NotImplementedError("Pyttsx3Provider does not support pronunciation evaluation")`
  - [x] T2.5: `provider_name` returns `"Local pyttsx3"`
  - [x] T2.6: `model_name` returns `"pyttsx3"`
  - [x] T2.7: Catch `pyttsx3.EngineError` or driver init failures in `_synthesize_sync` and re-raise as `RuntimeError("pyttsx3 init failed: {detail}")`

- [x] **T3: Create `services/speech/azure.py` — `AzureSpeechProvider`** (AC: 2, 4) — TDD: write failing tests first
  - [x] T3.1: `AzureSpeechProvider(api_key: str, region: str)` constructor — stores both as private attrs; NEVER log key value
  - [x] T3.2: Define `_AZURE_VOICE_MAP` — language-code→voice-name dict for MVP languages (see Dev Notes §AzureSpeechProvider)
  - [x] T3.3: Implement `synthesize()` using `httpx.AsyncClient` POST to Azure TTS REST endpoint with SSML body (see Dev Notes §AzureSpeechProvider)
  - [x] T3.4: On non-2xx response raise `RuntimeError(f"Azure Speech TTS {status_code}: {body[:200]}")` — never include `api_key` in error
  - [x] T3.5: `evaluate_pronunciation()` raises `NotImplementedError("AzureSpeechProvider.evaluate_pronunciation() is implemented in Story 4.1")`
  - [x] T3.6: `provider_name` returns `"Azure Speech"`
  - [x] T3.7: `model_name` returns `f"azure-{self._region}"`

- [x] **T4: Create `services/speech/whisper_local.py` — `WhisperLocalProvider`** (AC: 4) — TDD: write failing tests first
  - [x] T4.1: `WhisperLocalProvider()` constructor — no arguments; faster-whisper model loading is Story 4.1's responsibility
  - [x] T4.2: `synthesize()` raises `NotImplementedError("WhisperLocalProvider does not support TTS synthesis")`
  - [x] T4.3: `evaluate_pronunciation()` raises `NotImplementedError("WhisperLocalProvider.evaluate_pronunciation() is implemented in Story 4.1")`
  - [x] T4.4: `provider_name` returns `"Local Whisper"`
  - [x] T4.5: `model_name` returns `"faster-whisper"`

- [x] **T5: Update `services/registry.py` — add `get_speech_provider()`** (AC: 1, 2, 3) — TDD: write failing tests first
  - [x] T5.1: Import `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` from `services.credentials` (already defined there — DO NOT duplicate)
  - [x] T5.2: Import `AzureSpeechProvider` from `services.speech.azure`
  - [x] T5.3: Import `Pyttsx3Provider` from `services.speech.pyttsx3_local`
  - [x] T5.4: Define module-level `_pyttsx3_provider: Pyttsx3Provider | None = None` — lazy singleton (see Dev Notes §Registry)
  - [x] T5.5: Implement `get_speech_provider() -> AbstractSpeechProvider` (see Dev Notes §Registry)
  - [x] T5.6: AzureSpeechProvider is preferred when BOTH `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` credentials are present; falls back to `Pyttsx3Provider` when either is missing
  - [x] T5.7: Add `AbstractSpeechProvider` import from `services.speech.base`

- [x] **T6: Update `services/speech/__init__.py`** (housekeeping)
  - [x] T6.1: Export `AbstractSpeechProvider`, `SyllableResult`, `SyllableDetail`

- [x] **T7: Backend tests — TDD (write BEFORE T2–T5 implementation)** (AC: 1, 2, 3, 4, 5)
  - [x] T7.1: Create `tests/services/speech/__init__.py` (empty)
  - [x] T7.2: Create `tests/services/speech/test_base.py` — test dataclass instantiation, ABC cannot be instantiated (see Dev Notes §TestBase)
  - [x] T7.3: Create `tests/services/speech/test_pyttsx3_local.py` (see Dev Notes §TestPyttsx3)
  - [x] T7.4: Create `tests/services/speech/test_azure.py` (see Dev Notes §TestAzure)
  - [x] T7.5: Create `tests/services/speech/test_whisper_local.py` (see Dev Notes §TestWhisper)
  - [x] T7.6: Update `tests/services/test_registry.py` — add speech provider routing tests (see Dev Notes §TestRegistry)

- [x] **T8: Ruff compliance check**
  - [x] T8.1: `uv run ruff check --fix src/lingosips/services/speech/ src/lingosips/services/registry.py tests/services/speech/ tests/services/test_registry.py`
  - [x] T8.2: Import order: `stdlib` (`abc`, `asyncio`, `dataclasses`, `tempfile`, `threading`) → `third-party` (`httpx`, `pyttsx3`, `structlog`) → `local` (`lingosips.*`)
  - [x] T8.3: Use `@dataclass` from `dataclasses` module for `SyllableResult` and `SyllableDetail`
  - [x] T8.4: Use `collections.abc.AsyncIterator` not `typing.AsyncIterator` (Python 3.12)

---

## Dev Notes

### ⚠️ DO NOT Recreate — Already Exists

| Existing | Location | What it provides |
|---|---|---|
| `services/credentials.py` | `src/lingosips/services/credentials.py` | `get_credential()`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` — already defined; import directly |
| `services/registry.py` | `src/lingosips/services/registry.py` | EXISTS — UPDATE by adding `get_speech_provider()` to it; DO NOT create a new file |
| `services/speech/__init__.py` | stub — 1 line | UPDATE this file (T6), do not recreate |
| `services/llm/base.py` | `AbstractLLMProvider` | Pattern reference — mirror its structure for `AbstractSpeechProvider` |
| `tests/conftest.py` | `client`, `session`, `test_engine` fixtures | All tests use these — do not create parallel fixtures |
| `tests/services/__init__.py` | already exists from Story 1.5 | DO NOT recreate |

**CRITICAL**: `services/speech/base.py`, `services/speech/pyttsx3_local.py`, `services/speech/azure.py`, `services/speech/whisper_local.py` do NOT exist — create them new.

**CRITICAL**: `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are already defined in `services/credentials.py` lines 27-28. DO NOT add them again.

### §AbstractSpeechProvider — Exact Interface

```python
# src/lingosips/services/speech/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SyllableDetail:
    """Per-syllable pronunciation result — used by SyllableFeedback component (Story 4.2)."""
    syllable: str    # e.g., "a", "gua", "ca", "te"
    correct: bool    # True if correct pronunciation
    score: float = 1.0   # pronunciation accuracy 0.0–1.0


@dataclass
class SyllableResult:
    """Full pronunciation evaluation result returned by AbstractSpeechProvider."""
    overall_correct: bool
    syllables: list[SyllableDetail]
    correction_message: str | None


class AbstractSpeechProvider(ABC):
    """Base class for all speech providers.

    Contract rules:
    - Never import fastapi, SQLModel, or AsyncSession — this is a pure service
    - synthesize() returns raw audio bytes (WAV format for pyttsx3; as returned by Azure TTS)
    - evaluate_pronunciation() returns SyllableResult with per-syllable detail
    - provider_name and model_name are used by ServiceStatusIndicator (Story 1.10)
    - TTS-only providers raise NotImplementedError for evaluate_pronunciation()
    - Eval-only providers raise NotImplementedError for synthesize()
    """

    @abstractmethod
    async def synthesize(self, text: str, language: str) -> bytes:
        """Synthesize text to audio bytes.

        Returns raw audio bytes (format depends on provider: WAV for pyttsx3,
        provider-dependent for Azure Speech).
        Raises NotImplementedError if provider does not support TTS.
        """
        ...

    @abstractmethod
    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        """Evaluate spoken audio against target text.

        Returns SyllableResult with per-syllable correctness data.
        Raises NotImplementedError if provider does not support evaluation.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for ServiceStatusIndicator."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model/service identifier for display in ServiceStatusIndicator."""
        ...
```

### §Pyttsx3Provider — Implementation Pattern

**CRITICAL**: `pyttsx3` is synchronous and NOT thread-safe across shared engine instances. MUST:
1. Use `asyncio.get_running_loop().run_in_executor()` (NOT `get_event_loop()` — deprecated since Python 3.10)
2. Create a **NEW** `pyttsx3.init()` engine per call within the executor thread — do NOT share engine instances across threads

```python
# src/lingosips/services/speech/pyttsx3_local.py
import asyncio
import tempfile
from pathlib import Path

import pyttsx3
import structlog

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableResult

logger = structlog.get_logger(__name__)


class Pyttsx3Provider(AbstractSpeechProvider):
    """Local TTS fallback using pyttsx3 (system TTS engine — espeak/nsss/sapi5).

    Creates a fresh pyttsx3 engine per synthesis call — this is intentionally
    thread-safe by avoiding shared state. pyttsx3 engines are NOT safe to share.
    """

    @property
    def provider_name(self) -> str:
        return "Local pyttsx3"

    @property
    def model_name(self) -> str:
        return "pyttsx3"

    async def synthesize(self, text: str, language: str) -> bytes:
        """Synthesize text using pyttsx3 — runs in thread executor (blocking I/O)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text, language)

    def _synthesize_sync(self, text: str, language: str) -> bytes:
        """Blocking synthesis — runs in background thread. Creates engine per call."""
        engine = None
        tmp_path = None
        try:
            engine = pyttsx3.init()
        except Exception as exc:
            raise RuntimeError(f"pyttsx3 init failed: {exc}") from exc

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            audio_bytes = Path(tmp_path).read_bytes()
            logger.info("pyttsx3.synthesized", text_length=len(text), audio_bytes=len(audio_bytes))
            return audio_bytes

        except Exception as exc:
            logger.error("pyttsx3.synthesis_failed", error=str(exc))
            raise RuntimeError(f"pyttsx3 synthesis failed: {exc}") from exc
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink()
                except FileNotFoundError:
                    pass

    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        raise NotImplementedError("Pyttsx3Provider does not support pronunciation evaluation")
```

**Key decisions:**
- `_synthesize_sync` creates a new engine per call — no shared mutable state
- `engine.stop()` called in `finally` to release OS audio resources
- Temp file deleted in `finally` even if synthesis fails
- `pyttsx3.EngineError` or generic `Exception` caught and re-raised as `RuntimeError` — callers see a predictable error type

### §AzureSpeechProvider — Implementation Pattern

**Azure TTS REST API** (no SDK required — uses `httpx` already in dependencies):
- Endpoint: `https://{region}.tts.speech.microsoft.com/cognitiveservices/v1`
- Auth header: `Ocp-Apim-Subscription-Key: {api_key}`
- Content-Type: `application/ssml+xml`
- Output format header: `X-Microsoft-OutputFormat: riff-24khz-16bit-mono-pcm`
- Body: SSML XML (see below)

```python
# src/lingosips/services/speech/azure.py
import httpx
import structlog

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableResult

logger = structlog.get_logger(__name__)

# MVP voice map: language code → Azure Neural voice name
# Keys match BCP-47 language tags; short codes match Settings.active_target_language format
_AZURE_VOICE_MAP: dict[str, str] = {
    "es": "es-ES-AlvaroNeural",
    "es-ES": "es-ES-AlvaroNeural",
    "es-MX": "es-MX-DaliaNeural",
    "es-US": "es-US-PalomaNeural",
    "en": "en-US-JennyNeural",
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-SoniaNeural",
    "fr": "fr-FR-DeniseNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "de-DE": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "pt-PT": "pt-PT-RaquelNeural",
    "ja": "ja-JP-NanamiNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "nl": "nl-NL-FennaNeural",
    "pl": "pl-PL-ZofiaNeural",
    "sv": "sv-SE-SofieNeural",
    "tr": "tr-TR-EmelNeural",
    "ar": "ar-SA-ZariyahNeural",
    "hi": "hi-IN-SwaraNeural",
}
_DEFAULT_AZURE_VOICE = "en-US-JennyNeural"


class AzureSpeechProvider(AbstractSpeechProvider):
    """Azure Speech Service TTS provider using the REST API (no SDK needed).

    Story 1.6 implements synthesize(). evaluate_pronunciation() is implemented
    in Story 4.1 using Azure Pronunciation Assessment API.
    """

    def __init__(self, api_key: str, region: str) -> None:
        self._api_key = api_key   # NEVER log this
        self._region = region

    @property
    def provider_name(self) -> str:
        return "Azure Speech"

    @property
    def model_name(self) -> str:
        return f"azure-{self._region}"

    async def synthesize(self, text: str, language: str) -> bytes:
        """Synthesize text using Azure Speech TTS REST API."""
        voice = _AZURE_VOICE_MAP.get(language) or _AZURE_VOICE_MAP.get(
            language.split("-")[0], _DEFAULT_AZURE_VOICE
        )
        ssml = (
            "<speak version='1.0' "
            "xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xml:lang='{language}'>"
            f"<voice name='{voice}'>{text}</voice>"
            "</speak>"
        )
        url = f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._api_key,  # NEVER log
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                },
                content=ssml.encode("utf-8"),
            )
        if response.status_code != 200:
            # DO NOT include api_key in error
            raise RuntimeError(
                f"Azure Speech TTS {response.status_code}: {response.text[:200]}"
            )
        logger.info(
            "azure_speech.synthesized",
            language=language,
            voice=voice,
            audio_bytes=len(response.content),
        )
        return response.content

    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        raise NotImplementedError(
            "AzureSpeechProvider.evaluate_pronunciation() is implemented in Story 4.1"
        )
```

### §WhisperLocalProvider — Skeleton

```python
# src/lingosips/services/speech/whisper_local.py
import structlog

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableResult

logger = structlog.get_logger(__name__)


class WhisperLocalProvider(AbstractSpeechProvider):
    """Local speech evaluation using faster-whisper.

    synthesize() is not supported — WhisperLocalProvider is evaluation-only.
    evaluate_pronunciation() is implemented in Story 4.1.
    """

    @property
    def provider_name(self) -> str:
        return "Local Whisper"

    @property
    def model_name(self) -> str:
        return "faster-whisper"

    async def synthesize(self, text: str, language: str) -> bytes:
        raise NotImplementedError("WhisperLocalProvider does not support TTS synthesis")

    async def evaluate_pronunciation(
        self, audio: bytes, target: str, language: str
    ) -> SyllableResult:
        raise NotImplementedError(
            "WhisperLocalProvider.evaluate_pronunciation() is implemented in Story 4.1"
        )
```

### §Registry — `get_speech_provider()` Pattern

Add to the existing `services/registry.py` (DO NOT recreate — add alongside the existing `get_llm_provider()`):

```python
# ADD to src/lingosips/services/registry.py — append after existing content

from lingosips.services.credentials import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION
from lingosips.services.speech.azure import AzureSpeechProvider
from lingosips.services.speech.base import AbstractSpeechProvider
from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider

_pyttsx3_provider: Pyttsx3Provider | None = None  # module-level singleton


def get_speech_provider() -> AbstractSpeechProvider:
    """Return the appropriate speech provider based on configured credentials.

    AzureSpeechProvider preferred when BOTH key and region are present.
    Falls back to Pyttsx3Provider when either is missing.

    NOTE: This function covers TTS (synthesize). Speech evaluation routing
    (WhisperLocalProvider or AzureSpeechProvider for evaluate_pronunciation)
    is added in Story 4.1 as get_speech_evaluator().

    Used exclusively via FastAPI Depends(get_speech_provider) in api/ routers.
    """
    global _pyttsx3_provider

    api_key = get_credential(AZURE_SPEECH_KEY)
    region = get_credential(AZURE_SPEECH_REGION)
    if api_key and region:
        return AzureSpeechProvider(api_key=api_key, region=region)

    # Local TTS fallback
    if _pyttsx3_provider is None:
        _pyttsx3_provider = Pyttsx3Provider()

    return _pyttsx3_provider
```

**IMPORTANT**: Add the imports to the TOP of registry.py (in correct Ruff order), not at the end. The existing `from lingosips.services.credentials import OPENROUTER_API_KEY, OPENROUTER_MODEL, get_credential` line must be extended to also include `AZURE_SPEECH_KEY, AZURE_SPEECH_REGION`.

**Module-level `_pyttsx3_provider` singleton**: Like `_qwen_provider`, tests MUST reset it between runs:
```python
import lingosips.services.registry as reg
reg._pyttsx3_provider = None  # reset between tests
```

### §TestBase — Patterns

```python
# tests/services/speech/test_base.py
import pytest
from dataclasses import fields
from lingosips.services.speech.base import AbstractSpeechProvider, SyllableDetail, SyllableResult


class TestSyllableDetail:
    def test_syllable_detail_fields(self):
        detail = SyllableDetail(syllable="ca", correct=True, score=0.95)
        assert detail.syllable == "ca"
        assert detail.correct is True
        assert detail.score == 0.95

    def test_syllable_detail_default_score(self):
        detail = SyllableDetail(syllable="te", correct=False)
        assert detail.score == 1.0  # default


class TestSyllableResult:
    def test_syllable_result_fields(self):
        result = SyllableResult(
            overall_correct=False,
            syllables=[SyllableDetail("a", True), SyllableDetail("gua", False)],
            correction_message="Stress on third syllable",
        )
        assert result.overall_correct is False
        assert len(result.syllables) == 2
        assert result.correction_message == "Stress on third syllable"

    def test_syllable_result_none_correction(self):
        result = SyllableResult(overall_correct=True, syllables=[], correction_message=None)
        assert result.correction_message is None


class TestAbstractSpeechProvider:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            AbstractSpeechProvider()  # type: ignore[abstract]
```

### §TestPyttsx3 — Patterns

```python
# tests/services/speech/test_pyttsx3_local.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lingosips.services.speech.pyttsx3_local import Pyttsx3Provider


@pytest.mark.anyio
class TestPyttsx3Provider:
    def test_provider_name(self):
        provider = Pyttsx3Provider()
        assert provider.provider_name == "Local pyttsx3"

    def test_model_name(self):
        provider = Pyttsx3Provider()
        assert provider.model_name == "pyttsx3"

    async def test_evaluate_pronunciation_raises_not_implemented(self):
        provider = Pyttsx3Provider()
        with pytest.raises(NotImplementedError):
            await provider.evaluate_pronunciation(b"audio", "hello", "en")

    async def test_synthesize_returns_bytes(self, tmp_path):
        """Mocking pyttsx3.init() to avoid real audio I/O in unit tests."""
        fake_audio = b"RIFF fake wav content"
        mock_engine = MagicMock()

        def fake_save_to_file(text, path):
            Path(path).write_bytes(fake_audio)

        mock_engine.save_to_file.side_effect = fake_save_to_file
        mock_engine.runAndWait.return_value = None
        mock_engine.stop.return_value = None

        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.init.return_value = mock_engine
            provider = Pyttsx3Provider()
            result = await provider.synthesize("hello world", "en")

        assert result == fake_audio
        mock_engine.save_to_file.assert_called_once()
        mock_engine.runAndWait.assert_called_once()
        mock_engine.stop.assert_called_once()

    async def test_synthesize_cleans_up_temp_file_on_success(self, tmp_path):
        """Verify no temp files are left behind after synthesis."""
        import tempfile
        import os
        fake_audio = b"RIFF wav"
        mock_engine = MagicMock()

        created_files = []
        original_named_temp = tempfile.NamedTemporaryFile

        def track_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            created_files.append(f.name)
            return f

        def fake_save(text, path):
            Path(path).write_bytes(fake_audio)

        mock_engine.save_to_file.side_effect = fake_save
        mock_engine.runAndWait.return_value = None
        mock_engine.stop.return_value = None

        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            with patch("lingosips.services.speech.pyttsx3_local.tempfile.NamedTemporaryFile", side_effect=track_temp):
                mock_pyttsx3.init.return_value = mock_engine
                provider = Pyttsx3Provider()
                await provider.synthesize("cleanup test", "en")

        # All temp files cleaned up
        for f in created_files:
            assert not Path(f).exists(), f"Temp file {f} was not cleaned up"

    async def test_synthesize_raises_runtime_error_on_pyttsx3_init_failure(self):
        with patch("lingosips.services.speech.pyttsx3_local.pyttsx3") as mock_pyttsx3:
            mock_pyttsx3.init.side_effect = Exception("no audio driver")
            provider = Pyttsx3Provider()
            with pytest.raises(RuntimeError, match="pyttsx3 init failed"):
                await provider.synthesize("test", "en")
```

### §TestAzure — Patterns

```python
# tests/services/speech/test_azure.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lingosips.services.speech.azure import AzureSpeechProvider


@pytest.mark.anyio
class TestAzureSpeechProvider:
    def test_provider_name(self):
        provider = AzureSpeechProvider(api_key="test-key", region="eastus")
        assert provider.provider_name == "Azure Speech"

    def test_model_name_includes_region(self):
        provider = AzureSpeechProvider(api_key="test-key", region="westeurope")
        assert provider.model_name == "azure-westeurope"

    async def test_evaluate_pronunciation_raises_not_implemented(self):
        provider = AzureSpeechProvider(api_key="k", region="r")
        with pytest.raises(NotImplementedError):
            await provider.evaluate_pronunciation(b"audio", "hello", "en")

    async def test_synthesize_sends_correct_headers_and_ssml(self):
        fake_audio = b"riff wav bytes"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_audio

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="sub-key-123", region="eastus")
            result = await provider.synthesize("hello", "en")

        assert result == fake_audio
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs["headers"]
        assert headers["Ocp-Apim-Subscription-Key"] == "sub-key-123"
        assert headers["Content-Type"] == "application/ssml+xml"
        assert "tts.speech.microsoft.com" in call_kwargs.args[0]

    async def test_api_key_not_in_error_message(self):
        """API key must NEVER appear in error messages."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="very-secret-key", region="eastus")
            with pytest.raises(RuntimeError) as exc_info:
                await provider.synthesize("test", "en")

        assert "very-secret-key" not in str(exc_info.value)

    async def test_synthesize_raises_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            provider = AzureSpeechProvider(api_key="key", region="eastus")
            with pytest.raises(RuntimeError, match="Azure Speech TTS 403"):
                await provider.synthesize("test", "en")

    def test_voice_map_spanish(self):
        """Verify language→voice lookup works for common target languages."""
        from lingosips.services.speech.azure import _AZURE_VOICE_MAP
        assert "es" in _AZURE_VOICE_MAP
        assert "Neural" in _AZURE_VOICE_MAP["es"]
```

### §TestWhisper — Patterns

```python
# tests/services/speech/test_whisper_local.py
import pytest
from lingosips.services.speech.whisper_local import WhisperLocalProvider


@pytest.mark.anyio
class TestWhisperLocalProvider:
    def test_provider_name(self):
        provider = WhisperLocalProvider()
        assert provider.provider_name == "Local Whisper"

    def test_model_name(self):
        provider = WhisperLocalProvider()
        assert provider.model_name == "faster-whisper"

    async def test_synthesize_raises_not_implemented(self):
        provider = WhisperLocalProvider()
        with pytest.raises(NotImplementedError):
            await provider.synthesize("hello", "en")

    async def test_evaluate_pronunciation_raises_not_implemented(self):
        """Story 4.1 implements this — must raise NotImplementedError for now."""
        provider = WhisperLocalProvider()
        with pytest.raises(NotImplementedError):
            await provider.evaluate_pronunciation(b"audio", "hello", "en")
```

### §TestRegistry — Speech Provider Additions

Add to the existing `tests/services/test_registry.py`:

```python
# ADD to tests/services/test_registry.py

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
```

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `pyttsx3.init()` at class `__init__` time | Call `pyttsx3.init()` inside `_synthesize_sync()` (fresh per call, thread-safe) |
| `asyncio.get_event_loop()` | `asyncio.get_running_loop()` — `get_event_loop()` deprecated in Python 3.10+ |
| Sharing `pyttsx3` engine across threads | Each executor thread call creates its own engine |
| `AzureSpeechProvider(api_key=get_credential(...))` in a router | `Depends(get_speech_provider)` — registry only |
| Adding `AZURE_SPEECH_KEY` constant to registry.py or anywhere besides credentials.py | Import `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` from `services.credentials` only |
| `import fastapi` in `services/speech/` | Only `services/registry.py` may import fastapi |
| Logging `api_key` or `Ocp-Apim-Subscription-Key` header value | Use structlog; NEVER log credential values |
| Putting `_AZURE_VOICE_MAP` lookup logic in `api/` or `core/` | Voice selection is internal to `AzureSpeechProvider` |
| `asyncio.run()` inside `_synthesize_sync` | This runs inside an executor thread — use sync `pyttsx3` calls only, no new event loops |
| Re-creating `AbstractSpeechProvider` to mirror `AbstractLLMProvider` with different signatures | Exact method signatures per AC4: `synthesize(text, language)`, `evaluate_pronunciation(audio, target, language)` |

### §FileStructure — New and Modified Files

```
src/lingosips/
├── services/
│   ├── registry.py             ← UPDATED: add get_speech_provider(), _pyttsx3_provider singleton
│   └── speech/
│       ├── __init__.py         ← UPDATED: export AbstractSpeechProvider, SyllableResult, SyllableDetail
│       ├── base.py             ← NEW: AbstractSpeechProvider, SyllableDetail, SyllableResult
│       ├── pyttsx3_local.py    ← NEW: Pyttsx3Provider (local TTS fallback)
│       ├── azure.py            ← NEW: AzureSpeechProvider (Azure Speech TTS)
│       └── whisper_local.py    ← NEW: WhisperLocalProvider skeleton (evaluate_pronunciation in Story 4.1)

tests/
└── services/
    ├── test_registry.py        ← UPDATED: add get_speech_provider() tests
    └── speech/
        ├── __init__.py         ← NEW (empty)
        ├── test_base.py        ← NEW
        ├── test_pyttsx3_local.py ← NEW
        ├── test_azure.py       ← NEW
        └── test_whisper_local.py ← NEW
```

No new Python dependencies needed — `pyttsx3>=2.99`, `faster-whisper>=1.2.1`, and `httpx>=0.28.1` are already in `pyproject.toml`.

### §RuffCompliance

```bash
uv run ruff check --fix \
  src/lingosips/services/speech/ \
  src/lingosips/services/registry.py \
  tests/services/speech/ \
  tests/services/test_registry.py
```

Common issues to pre-empt:
- Import order: `stdlib` (`abc`, `asyncio`, `dataclasses`, `tempfile`) → `third-party` (`httpx`, `pyttsx3`, `structlog`) → `local` (`lingosips.*`)
- `@dataclass` from `dataclasses` module (not pydantic for these internal dataclasses)
- Abstract methods need `@abstractmethod` decorator + `...` body (not `pass`)
- `AsyncIterator` is from `collections.abc` in Python 3.12, not `typing`
- Unused imports from ABC if `ABC` is used as base: check `from abc import ABC, abstractmethod`

### Previous Story Intelligence

From Story 1.5 (last completed — code review patches applied 2026-05-01):

- **`asyncio.get_running_loop()` NOT `asyncio.get_event_loop()`** — `get_event_loop()` is deprecated in Python 3.10+. Story 1.5 code review patched this exact issue (`[Review][Patch]` #6). MUST use `get_running_loop()` in `Pyttsx3Provider.synthesize()`.
- **`session.execute()` NOT `session.exec()`** — the project uses SQLAlchemy's `AsyncSession`. Not directly relevant to this story (no DB access), but remember for any future cross-story work.
- **`@pytest.mark.anyio` on the class** (not individual methods). All test methods are `async def`. Confirmed working in Story 1.5.
- **Module-level singleton test isolation**: `_pyttsx3_provider` global in `registry.py` will persist between tests. Reset it: `import lingosips.services.registry as reg; reg._pyttsx3_provider = None` in each test that needs a clean state.
- **RFC 7807 error format** not needed for speech providers (no HTTP responses from providers) but required at the `api/` layer when speech fails.
- **Coverage gate 90%** is hard CI. All new files under `src/lingosips/` must be tested. The `_synthesize_sync` method CAN be covered in unit tests via mocking `pyttsx3.init()` — unlike `_download_sync` in Story 1.5 which required a real download thread.
- **structlog pattern**: `logger = structlog.get_logger(__name__)` at module level. Log events snake_case: `logger.info("pyttsx3.synthesized", ...)`, `logger.error("pyttsx3.synthesis_failed", ...)`.
- **Ruff SSE f-string issue** from Story 1.5 debug log #2: Ruff rejects dict literals split across multi-line f-strings. Pre-compute any `json.dumps(...)` into local variables before f-strings. Not directly applicable here but good to remember.
- **`asyncio.run_coroutine_threadsafe()` not `asyncio.run()`** inside background threads. For `Pyttsx3Provider`, this pattern is NOT needed (no async calls inside `_synthesize_sync`) — just use `run_in_executor()` to run the sync method.
- **Module-level singleton for `_pyttsx3_provider`**: Follow the exact same pattern as `_qwen_provider` in registry.py. Pyttsx3Provider() initialization is cheap (no model loading), but caching avoids re-creating the object on every request.

From Story 1.4 (credentials patterns):
- `get_credential(AZURE_SPEECH_KEY)` already tested and works — BOTH `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are already defined in `services/credentials.py`. Do NOT redefine.
- Credentials must NEVER appear in logs, error messages, or test output.

From Story 1.2 (app shell):
- `services/speech/__init__.py` is currently a stub (1 line). Update to export the public API.
- No router registration needed for this story — no new API endpoints are added.

### References

- Story 1.6 acceptance criteria: [Source: epics.md#Story 1.6]
- `AbstractSpeechProvider` gains `synthesize(text, lang) → bytes` method: [Source: epics.md#Additional Requirements — TTS service]
- `pyttsx3` is a required backend dependency: [Source: epics.md#Additional Requirements — TTS service]
- `services/registry.py` is ONLY location for provider fallback logic: [Source: project-context.md#Layer Architecture & Boundaries]
- `get_speech_provider()` via Depends() only: [Source: project-context.md#Dependency Injection — Depends() Always]
- `AZURE_SPEECH_KEY = "azure_speech_key"` already in credentials.py line 27: [Source: src/lingosips/services/credentials.py]
- `AZURE_SPEECH_REGION = "azure_speech_region"` already in credentials.py line 28: [Source: src/lingosips/services/credentials.py]
- No `import fastapi` in `services/speech/`: [Source: project-context.md#Layer Architecture — services/registry.py is ONLY services/ file that may import fastapi]
- `services/speech/base.py` — `AbstractSpeechProvider (ABC)`: [Source: architecture.md#Structure Patterns]
- `services/speech/azure.py` — `AzureSpeechProvider`: [Source: architecture.md#Structure Patterns]
- `services/speech/whisper_local.py` — skeleton: [Source: architecture.md#Structure Patterns]
- `services/registry.py` — `get_speech_provider()` — Depends() target: [Source: architecture.md#Structure Patterns]
- `WhisperLocalProvider` evaluate_pronunciation() fully implemented in Story 4.1: [Source: epics.md#Story 4.1]
- `SyllableResult` fields: `overall_correct`, `syllables`, `correction_message`: [Source: epics.md#Story 1.6 AC4]
- Per-syllable chip: `aria-label="{syllable} — {correct|incorrect}"`: [Source: epics.md#UX-DR2, Story 4.2]
- `asyncio.get_running_loop()` not `get_event_loop()`: [Source: Story 1.5 Dev Agent Record — Review Finding #6]
- `pyttsx3>=2.99` already in dependencies: [Source: pyproject.toml]
- `faster-whisper>=1.2.1` already in dependencies: [Source: pyproject.toml]
- `httpx>=0.28.1` already in dependencies (async HTTP for Azure): [Source: pyproject.toml]
- TDD mandatory — failing tests before implementation: [Source: project-context.md#Testing Rules]
- 90% backend coverage CI hard gate: [Source: project-context.md#CI gates]
- FR27: Speech routing Azure Speech → Whisper local fallback: [Source: epics.md#FR27]
- FR39: Fully functional before any external service configured: [Source: epics.md#FR39]
- NFR24: Speech providers swappable behind common interface: [Source: epics.md#NFR24]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

No blocking issues. Ruff auto-fixed 3 import-order issues in test files (stdlib/third-party order in test_base.py, test_pyttsx3_local.py, test_azure.py). Formatter reformatted azure.py (long error line). All clean on final check.

### Completion Notes List

- ✅ Created `services/speech/base.py` with `AbstractSpeechProvider` ABC, `SyllableDetail` and `SyllableResult` dataclasses following exact interface from Dev Notes §AbstractSpeechProvider.
- ✅ Created `services/speech/pyttsx3_local.py` with `Pyttsx3Provider` using `asyncio.get_running_loop()` (not deprecated `get_event_loop()`), fresh engine per call pattern, temp file cleanup in `finally` block.
- ✅ Created `services/speech/azure.py` with `AzureSpeechProvider` — 26-language neural voice map, SSML construction, httpx REST integration, API key never logged or included in error messages.
- ✅ Created `services/speech/whisper_local.py` with `WhisperLocalProvider` skeleton — both methods raise `NotImplementedError` pending Story 4.1.
- ✅ Updated `services/registry.py` — added `get_speech_provider()` with `_pyttsx3_provider` singleton, Azure preferred when both key+region present, pyttsx3 fallback otherwise.
- ✅ Updated `services/speech/__init__.py` — exports `AbstractSpeechProvider`, `SyllableResult`, `SyllableDetail`.
- ✅ TDD followed: all test files created and confirmed failing BEFORE production code was written.
- ✅ 167 tests pass (55 new tests: 41 speech + 7 registry speech + existing), 0 regressions.
- ✅ Coverage: 93.76% (exceeds 90% CI hard gate). New speech files: `azure.py` 100%, `base.py` 100%, `whisper_local.py` 100%, `pyttsx3_local.py` 91%, `registry.py` 100%.
- ✅ Ruff check: all checks passed after auto-fix.

### File List

**New files:**
- `src/lingosips/services/speech/base.py`
- `src/lingosips/services/speech/pyttsx3_local.py`
- `src/lingosips/services/speech/azure.py`
- `src/lingosips/services/speech/whisper_local.py`
- `tests/services/speech/__init__.py`
- `tests/services/speech/test_base.py`
- `tests/services/speech/test_pyttsx3_local.py`
- `tests/services/speech/test_azure.py`
- `tests/services/speech/test_whisper_local.py`

**Modified files:**
- `src/lingosips/services/speech/__init__.py`
- `src/lingosips/services/registry.py`
- `tests/services/test_registry.py`

### Review Findings

- [x] [Review][Patch] SSML XML injection in AzureSpeechProvider.synthesize() — text interpolated raw into SSML without html.escape(); vocabulary words containing & < > produced invalid SSML rejected by Azure API. Fixed: added `html.escape(text)` before interpolation. [azure.py:83]
- [x] [Review][Patch] language parameter silently ignored in Pyttsx3Provider — undocumented limitation caused ambiguity about pyttsx3 language support. Fixed: added clarifying docstring in `_synthesize_sync()`. [pyttsx3_local.py:41]
- [x] [Review][Patch] Missing tests for SSML XML escaping — two new tests added to verify & and < > are properly escaped. [tests/services/speech/test_azure.py]
- [x] [Review][Defer] Race condition in _pyttsx3_provider singleton — two concurrent calls could create two Pyttsx3Provider instances before either sets the global. Benign (Pyttsx3Provider is stateless) and matches pre-existing _qwen_provider pattern. [registry.py:90] — deferred, pre-existing

### Change Log

- 2026-05-01: Implemented Story 1.6 — Speech Provider Abstraction & Local TTS Fallback. Created `AbstractSpeechProvider` ABC with `SyllableDetail`/`SyllableResult` dataclasses; added `Pyttsx3Provider` (local TTS fallback), `AzureSpeechProvider` (Azure TTS REST), `WhisperLocalProvider` (stub); wired `get_speech_provider()` into `services/registry.py` with Azure→pyttsx3 fallback logic. 55 new tests, 167 total, 93.76% coverage.
- 2026-05-01: Code review complete — 2 patches applied (SSML XML injection fix + language param docstring), 2 new tests added (XML escaping). 169 tests, 93.78% coverage. Story marked done.
