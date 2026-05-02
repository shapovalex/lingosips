"""Local speech evaluation using faster-whisper.

evaluate_pronunciation() implemented in Story 4.1.
synthesize() is not supported — WhisperLocalProvider is evaluation-only.

THREAD SAFETY: WhisperModel is NOT thread-safe. Create a new instance per
evaluation in run_in_executor. This is intentional for MVP simplicity.
"""

import asyncio
import os
import tempfile

import structlog
from faster_whisper import WhisperModel

from lingosips.services.models.whisper_manager import WHISPER_MODEL_DIR
from lingosips.services.speech.base import AbstractSpeechProvider, SyllableDetail, SyllableResult

logger = structlog.get_logger(__name__)

EVAL_TIMEOUT_SECONDS = 10.0  # hard limit; 2s SLA is the goal


class WhisperLocalProvider(AbstractSpeechProvider):
    """Local speech evaluation using faster-whisper (tiny model).

    Evaluation-only: synthesize() raises NotImplementedError.
    Model must be pre-downloaded via WhisperModelManager before first use.
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
        """Evaluate pronunciation by transcribing audio and comparing with target.

        Runs in thread executor — WhisperModel is blocking and not thread-safe.
        Creates a new WhisperModel instance per call (stateless, safe for MVP).
        """
        if not audio:
            raise ValueError("audio bytes must not be empty")

        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._evaluate_sync,
                    audio,
                    target,
                    language,
                ),
                timeout=EVAL_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Whisper evaluation timed out after {EVAL_TIMEOUT_SECONDS}s"
            ) from exc

        return result

    def _evaluate_sync(self, audio: bytes, target: str, language: str) -> SyllableResult:
        """Blocking evaluation — runs in thread executor.

        Writes audio bytes to a temp WAV file, transcribes with faster-whisper,
        then computes syllable-level correctness by comparing transcription to target.

        NOTE: Uses delete=False + explicit close before transcription so that
        faster-whisper can open the file by name. On Windows, NamedTemporaryFile
        with delete=True holds an exclusive lock that prevents a second open.
        """
        model_path = str(WHISPER_MODEL_DIR)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        try:
            tmp.write(audio)
            tmp.flush()
            tmp.close()  # close before passing path to WhisperModel (Windows-safe)

            model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
                download_root=None,  # model_path IS the root — already downloaded
            )
            segments, _info = model.transcribe(
                tmp_path,
                language=language.split("-")[0] if "-" in language else language,
                beam_size=1,
                vad_filter=True,
            )
            transcription = " ".join(seg.text.strip() for seg in segments).strip().lower()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # already deleted or never created — not an error

        return _build_syllable_result(transcription, target)


def _syllabify(word: str) -> list[str]:
    """Naive syllabification: split on vowel clusters for MVP feedback.

    Returns at least one entry (the whole word) even if no vowels found.
    Uses simple CV heuristic — adequate for per-syllable UX; not linguistically precise.
    """
    vowels = set("aeiouáéíóúàèìòùäëïöüāēīōū")
    word = word.lower().strip(".,!?;:")
    if not word:
        return [word]

    syllables: list[str] = []
    current = ""
    for char in word:
        current += char
        if char in vowels:
            syllables.append(current)
            current = ""
    if current:
        if syllables:
            syllables[-1] += current
        else:
            syllables.append(current)
    return syllables if syllables else [word]


def _build_syllable_result(transcription: str, target: str) -> SyllableResult:
    """Compare transcription to target word, return SyllableResult.

    Exact match (case-insensitive, stripped) → all syllables correct.
    Partial or no match → derive per-syllable correctness from Levenshtein similarity.
    """
    target_clean = target.lower().strip(".,!?;:")
    trans_clean = transcription.lower().strip(".,!?;:")
    syllables = _syllabify(target_clean)

    overall_correct = target_clean == trans_clean or target_clean in trans_clean

    if overall_correct:
        details = [SyllableDetail(syllable=s, correct=True, score=1.0) for s in syllables]
        return SyllableResult(
            overall_correct=True,
            syllables=details,
            correction_message=None,
        )

    # Partial match: score each syllable by comparing transcription coverage
    details = []
    for syl in syllables:
        if syl in trans_clean:
            details.append(SyllableDetail(syllable=syl, correct=True, score=1.0))
        else:
            details.append(SyllableDetail(syllable=syl, correct=False, score=0.0))

    correct_count = sum(1 for d in details if d.correct)
    correction = (
        None
        if correct_count == len(details)
        else f'Heard: "{transcription or "(nothing)"}" — expected: "{target}"'
    )

    return SyllableResult(
        overall_correct=False,
        syllables=details,
        correction_message=correction,
    )
