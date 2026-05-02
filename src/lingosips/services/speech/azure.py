"""Azure Speech Service TTS provider using the REST API (no SDK needed).

Azure TTS REST API:
- Endpoint: https://{region}.tts.speech.microsoft.com/cognitiveservices/v1
- Auth header: Ocp-Apim-Subscription-Key: {api_key}
- Content-Type: application/ssml+xml
- Output format: X-Microsoft-OutputFormat: riff-24khz-16bit-mono-pcm

Story 1.6 implements synthesize(). evaluate_pronunciation() is implemented
in Story 4.1 using Azure Pronunciation Assessment API.
"""

import base64
import html
import json

import httpx
import structlog

from lingosips.services.speech.base import AbstractSpeechProvider, SyllableDetail, SyllableResult

logger = structlog.get_logger(__name__)

# BCP-47 normalisation: naive uppercase expansion produces invalid tags for some locales.
# Maps the broken expansion → the correct Azure BCP-47 locale code.
_LANG_NORMALIZATIONS: dict[str, str] = {
    "en-EN": "en-US",
    "zh-ZH": "zh-CN",
    "ar-AR": "ar-SA",
    "hi-HI": "hi-IN",
    "ko-KO": "ko-KR",
    "sv-SV": "sv-SE",
    "nl-NL": "nl-NL",  # already valid, listed for explicitness
    "ru-RU": "ru-RU",  # already valid
    "pl-PL": "pl-PL",  # already valid
    "tr-TR": "tr-TR",  # already valid
    "pt-PT": "pt-BR",  # align with TTS voice map ("pt" → pt-BR-FranciscaNeural)
    "ja-JA": "ja-JP",
    "de-DE": "de-DE",  # already valid
    "fr-FR": "fr-FR",  # already valid
    "it-IT": "it-IT",  # already valid
    "es-ES": "es-ES",  # already valid
}

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
        self._api_key = api_key  # NEVER log this
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
        # XML-escape text before SSML interpolation — vocabulary words may contain & < >
        ssml_text = html.escape(text)
        ssml = (
            "<speak version='1.0' "
            "xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xml:lang='{language}'>"
            f"<voice name='{voice}'>{ssml_text}</voice>"
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
            raise RuntimeError(f"Azure Speech TTS {response.status_code}: {response.text[:200]}")
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
        """Evaluate pronunciation using Azure Speech Pronunciation Assessment REST API.

        Uses Phoneme granularity + HundredMark grading.
        Maps phoneme scores → syllables via simple CV grouping.
        Timeout: 10s hard limit (2s SLA target).
        """
        if not audio:
            raise ValueError("audio bytes must not be empty")

        # Language tag: Azure wants BCP-47 (e.g. "es-ES") — expand short codes.
        # Some short codes produce invalid or mismatched BCP-47 tags when naively
        # uppercased; the normalisation dict maps the broken form → correct tag.
        lang_tag = language if "-" in language else f"{language}-{language.upper()}"
        lang_tag = _LANG_NORMALIZATIONS.get(lang_tag, lang_tag)

        pron_params = {
            "ReferenceText": target,
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
        }
        pron_header = base64.b64encode(json.dumps(pron_params).encode("utf-8")).decode("ascii")

        url = (
            f"https://{self._region}.stt.speech.microsoft.com"
            "/speech/recognition/conversation/cognitiveservices/v1"
            f"?language={lang_tag}&format=detailed&usePronunciationAssessment=true"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._api_key,  # NEVER log
                    "Content-Type": "audio/wav; codec=audio/pcm; samplerate=16000",
                    "Pronunciation-Assessment": pron_header,
                },
                content=audio,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Azure Pronunciation Assessment {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        recognition_status = data.get("RecognitionStatus", "")
        if recognition_status != "Success":
            # e.g. "NoMatch" — audio not recognized
            syllables_from_target = _syllabify_from_azure(target)
            return SyllableResult(
                overall_correct=False,
                syllables=[
                    SyllableDetail(syllable=s, correct=False, score=0.0)
                    for s in syllables_from_target
                ],
                correction_message=f'Speech not recognized — expected: "{target}"',
            )

        nbest = data.get("NBest", [{}])[0]
        pron_assessment = nbest.get("PronunciationAssessment", {})
        overall_score = pron_assessment.get("AccuracyScore", 0.0)
        overall_correct = overall_score >= 75.0  # ≥ 75/100 = correct

        words = nbest.get("Words", [])
        syllable_details = _map_phonemes_to_syllables(target, words)

        correction = None if overall_correct else _build_correction_message(target, words)

        logger.info(
            "azure_speech.evaluated",
            target=target,
            language=lang_tag,
            overall_score=overall_score,
            overall_correct=overall_correct,
        )

        return SyllableResult(
            overall_correct=overall_correct,
            syllables=syllable_details,
            correction_message=correction,
        )


# ── Module-level helper functions ─────────────────────────────────────────────


def _syllabify_from_azure(word: str) -> list[str]:
    """Minimal syllabification for fallback cases when Azure returns no phonemes."""
    vowels = set("aeiouáéíóúàèìòùäëïöü")
    syllables: list[str] = []
    current = ""
    for ch in word.lower():
        current += ch
        if ch in vowels:
            syllables.append(current)
            current = ""
    if current:
        if syllables:
            syllables[-1] += current
        else:
            syllables.append(current)
    return syllables if syllables else [word]


def _map_phonemes_to_syllables(target: str, words: list[dict]) -> list[SyllableDetail]:
    """Map Azure phoneme scores to target word's syllables.

    Groups phonemes into syllable-sized chunks. Each syllable is 'correct'
    if its average phoneme accuracy score ≥ 75.
    """
    syllables = _syllabify_from_azure(target)
    phonemes: list[dict] = []
    for word in words:
        phonemes.extend(word.get("Phonemes", []))

    if not phonemes:
        # No phoneme data — use word-level score
        target_word_data = words[0] if words else {}
        word_score = target_word_data.get("PronunciationAssessment", {}).get("AccuracyScore", 0.0)
        correct = word_score >= 75.0
        return [
            SyllableDetail(syllable=s, correct=correct, score=word_score / 100.0) for s in syllables
        ]

    # Distribute phonemes evenly across syllables
    chunk_size = max(1, len(phonemes) // len(syllables))
    result: list[SyllableDetail] = []
    for i, syl in enumerate(syllables):
        start = i * chunk_size
        end = start + chunk_size if i < len(syllables) - 1 else len(phonemes)
        chunk = phonemes[start:end]
        avg_score = (
            sum(p.get("PronunciationAssessment", {}).get("AccuracyScore", 0.0) for p in chunk)
            / len(chunk)
            if chunk
            else 0.0
        )
        result.append(
            SyllableDetail(
                syllable=syl,
                correct=avg_score >= 75.0,
                score=avg_score / 100.0,
            )
        )
    return result


def _build_correction_message(target: str, words: list[dict]) -> str | None:
    """Build a human-readable correction message from Azure word data.

    Returns None only when overall_correct is True (caller responsibility).
    When overall_correct is False and no specific word errors are identified,
    falls back to a generic improvement message so users always get feedback.
    Uses w.get("Word") to guard against Azure responses missing the "Word" key.
    """
    if not words:
        return f'Expected: "{target}"'
    errors = [
        w.get("Word", "")
        for w in words
        if w.get("PronunciationAssessment", {}).get("ErrorType", "None") != "None"
        and w.get("Word")  # skip entries with missing or empty Word field
    ]
    if not errors:
        # Score was below threshold but no specific word errors — generic fallback
        return f'Pronunciation needs improvement — expected: "{target}"'
    return f"Check pronunciation of: {', '.join(errors)}"
