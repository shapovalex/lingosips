"""Azure Speech Service TTS provider using the REST API (no SDK needed).

Azure TTS REST API:
- Endpoint: https://{region}.tts.speech.microsoft.com/cognitiveservices/v1
- Auth header: Ocp-Apim-Subscription-Key: {api_key}
- Content-Type: application/ssml+xml
- Output format: X-Microsoft-OutputFormat: riff-24khz-16bit-mono-pcm

Story 1.6 implements synthesize(). evaluate_pronunciation() is implemented
in Story 4.1 using Azure Pronunciation Assessment API.
"""

import html

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
        raise NotImplementedError(
            "AzureSpeechProvider.evaluate_pronunciation() is implemented in Story 4.1"
        )
