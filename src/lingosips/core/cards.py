"""Card creation pipeline for lingosips.

Business logic only — no FastAPI imports.
API layer (api/cards.py) delegates to create_card_stream().
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import safety
from lingosips.db.models import Card
from lingosips.services.llm.base import AbstractLLMProvider, LLMMessage
from lingosips.services.speech.base import AbstractSpeechProvider

if TYPE_CHECKING:
    from lingosips.services.image import ImageService

logger = structlog.get_logger(__name__)

AUDIO_DIR = Path.home() / ".lingosips" / "audio"
AUDIO_SYNTHESIS_TIMEOUT = 30.0  # seconds — generous for slow local TTS

IMAGE_DIR = Path.home() / ".lingosips" / "images"

_CONTENT_TYPE_EXT: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}


# ── Request model ─────────────────────────────────────────────────────────────


class CardCreateRequest(BaseModel):
    target_word: str = Field(
        min_length=1, max_length=500, description="Word or phrase to create a card for"
    )

    @field_validator("target_word")
    @classmethod
    def not_whitespace_only(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be whitespace only")
        return stripped  # strip leading/trailing whitespace


# ── SSE helper ────────────────────────────────────────────────────────────────


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event string.

    Exact envelope required by the architecture spec and frontend SSE parser:
        event: {event_type}
        data: {json_payload}

    (blank line terminates the event)
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ── LLM prompt ────────────────────────────────────────────────────────────────


CARD_SYSTEM_PROMPT = """\
You are a language learning assistant. Given a word or phrase in a target language, \
return ONLY a JSON object with these exact fields. No markdown, no explanation, no extra text.

{
  "card_type": "word | sentence | collocation",
  "translation": "English translation or idiomatic meaning",
  "forms": {
    "gender": "masculine | feminine | neuter | null",
    "article": "definite article or null",
    "plural": "plural form or null",
    "conjugations": {},
    "register_context": "register or style note for collocations/sentences, or null"
  },
  "example_sentences": ["Example sentence 1 using the word.", "Example sentence 2."]
}

Rules:
- Return ONLY the JSON object
- card_type classification:
    "word": single word (noun, verb, adjective, adverb)
    "collocation": fixed multi-word phrase (idiom, set phrase, verb+noun, e.g. "hacer el tonto")
    "sentence": full sentence or clause with a complete predicate
- For verbs, populate conjugations: {"infinitive": "...", "present_1s": "...", "present_3s": "..."}
- For nouns with gender, populate gender and article
- For word type cards, set register_context to null
- For sentence and collocation cards:
    set gender/article/plural to null
    set register_context to a brief note on register or usage (e.g., "informal, spoken Spanish")
    translation should be the idiomatic English meaning, not word-for-word
- example_sentences must have exactly 2 sentences in the target language
- For other word types, set gender/article/plural to null
- Sentences must be in the target language, not English
"""


def _build_messages(target_word: str, target_language: str) -> list[LLMMessage]:
    """Build OpenAI-compatible messages for card generation."""
    return [
        {"role": "system", "content": CARD_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Target language: {target_language}\nWord/phrase: {target_word}",
        },
    ]


# ── LLM response parser ───────────────────────────────────────────────────────


def _parse_llm_response(raw: str) -> dict:
    """Extract and parse JSON from LLM response.

    Handles:
    - Clean JSON: {"translation": "..."}
    - Markdown fenced: ```json\\n{"translation": "..."}\\n```
    - Extra preamble/trailing text around JSON object

    Raises ValueError if no valid JSON object found.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        # Find closing fence
        end_fence = next(
            (i for i, line in enumerate(lines[1:], 1) if line.strip() == "```"),
            len(lines),
        )
        text = "\n".join(lines[1:end_fence]).strip()

    # Find and parse the outermost JSON object using raw_decode, which correctly
    # locates the matching closing brace rather than using rfind (which fails when
    # trailing text after the JSON also contains '}').
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response (got: {raw[:100]!r})")

    try:
        decoder = json.JSONDecoder()
        parsed, _ = decoder.raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in LLM response: {exc}") from exc

    # Apply defaults for missing fields
    forms = parsed.get(
        "forms",
        {
            "gender": None,
            "article": None,
            "plural": None,
            "conjugations": {},
            "register_context": None,
        },
    )
    # Ensure register_context key always exists in forms
    if "register_context" not in forms:
        forms["register_context"] = None

    # Normalize card_type to a known value — unknown values (e.g. "phrase") default to "word"
    valid_card_types = {"word", "sentence", "collocation"}
    raw_card_type = parsed.get("card_type", "word")
    card_type = raw_card_type if raw_card_type in valid_card_types else "word"

    return {
        "card_type": card_type,
        "translation": parsed.get("translation", ""),
        "forms": forms,
        "example_sentences": parsed.get("example_sentences", []),
    }


# ── Core generator ────────────────────────────────────────────────────────────


async def create_card_stream(
    request: CardCreateRequest,
    llm: AbstractLLMProvider,
    session: AsyncSession,
    target_language: str,
    speech: AbstractSpeechProvider,
) -> AsyncGenerator[str, None]:
    """Card creation pipeline — yields SSE-formatted event strings.

    Sequence:
    1. Call LLM.complete() with timeout → yields field_update events
    2. Apply safety filter to each field
    3. Persist card to DB with FSRS initial state
    4. Refresh card to get DB-assigned id
    5. TTS audio generation (soft failure — never blocks card creation)
    6. Yield complete event with card_id

    On any failure: yield error event and return (never raise).
    TTS failure is non-fatal — card is saved with audio_url=None.
    """
    try:
        # Step 1: Call LLM with 10s timeout (NFR4 — local Qwen SLA)
        messages = _build_messages(request.target_word, target_language)
        try:
            raw_response = await asyncio.wait_for(
                llm.complete(messages, max_tokens=512),
                timeout=10.0,
            )
        except TimeoutError:
            logger.warning("cards.llm_timeout", target_word=request.target_word)
            yield _sse_event("error", {"message": "Local Qwen timeout after 10s"})
            return
        except Exception as exc:
            logger.error("cards.llm_error", exc_type=type(exc).__name__)
            yield _sse_event("error", {"message": f"LLM error: {type(exc).__name__}"})
            return

        # Step 2: Parse LLM response
        try:
            card_data = _parse_llm_response(raw_response)
        except ValueError:
            logger.error("cards.parse_failed", raw_preview=raw_response[:100])
            yield _sse_event("error", {"message": "Failed to parse LLM response"})
            return

        # Step 3: Safety filter + emit field_update events (in order per spec)
        fields_to_emit: list[tuple[str, str | dict | list]] = [
            ("card_type", card_data["card_type"]),
            ("translation", card_data["translation"]),
            ("forms", card_data["forms"]),
            ("example_sentences", card_data["example_sentences"]),
        ]

        for field_name, value in fields_to_emit:
            text_for_check = value if isinstance(value, str) else json.dumps(value)
            is_safe, blocked_term = safety.check_text(text_for_check)
            if not is_safe:
                logger.warning("cards.safety_blocked", field=field_name, term=blocked_term)
                yield _sse_event(
                    "error",
                    {"message": f"Content blocked by safety filter in field: {field_name}"},
                )
                return
            yield _sse_event("field_update", {"field": field_name, "value": value})

        # Step 4: Persist card — FSRS initial state is all defaults from Card model
        card = Card(
            target_word=request.target_word,
            translation=card_data["translation"],
            forms=json.dumps(card_data["forms"]),
            example_sentences=json.dumps(card_data["example_sentences"]),
            card_type=card_data["card_type"],
            target_language=target_language,
            # FSRS columns: all default values from db/models.py are correct
            # stability=0.0, difficulty=0.0, fsrs_state="New", due=now, reps=0, lapses=0
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)

        # Step 5: Audio generation (TTS) — soft failure — never blocks card creation
        try:
            AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            audio_bytes = await asyncio.wait_for(
                speech.synthesize(request.target_word, target_language),
                timeout=AUDIO_SYNTHESIS_TIMEOUT,
            )
            if not audio_bytes:
                raise RuntimeError("synthesize() returned empty audio bytes")
            audio_path = AUDIO_DIR / f"{card.id}.wav"
            await asyncio.to_thread(audio_path.write_bytes, audio_bytes)
            card.audio_url = f"/cards/{card.id}/audio"
            await session.commit()
            logger.info(
                "cards.audio_generated",
                card_id=card.id,
                audio_bytes=len(audio_bytes),
            )
            yield _sse_event("field_update", {"field": "audio", "value": card.audio_url})
        except Exception as exc:
            logger.warning(
                "cards.audio_failed",
                card_id=card.id,
                exc_type=type(exc).__name__,
            )
            # TTS failure is non-fatal: card is already saved with audio_url=None

        logger.info("cards.created", card_id=card.id, target_word=request.target_word)
        yield _sse_event("complete", {"card_id": card.id})

    except Exception as exc:
        # Catch-all: never let exceptions escape the generator (would corrupt SSE stream)
        logger.error("cards.unexpected_error", exc_type=type(exc).__name__)
        yield _sse_event("error", {"message": "Unexpected error during card creation"})


# ── CRUD helpers ──────────────────────────────────────────────────────────────


async def get_card(card_id: int, session: AsyncSession) -> Card:
    """Fetch a card by ID. Raises ValueError if not found (router converts to 404)."""
    result = await session.execute(select(Card).where(Card.id == card_id))
    card = result.scalar_one_or_none()
    if card is None:
        raise ValueError(f"Card {card_id} does not exist")
    return card


async def update_card(
    card_id: int,
    update_data: dict,
    session: AsyncSession,
) -> Card:
    """Partially update a card. Only keys present in update_data are changed.

    Raises ValueError if card not found.
    """
    card = await get_card(card_id, session)

    if "translation" in update_data:
        card.translation = update_data["translation"]
    if "personal_note" in update_data:
        card.personal_note = update_data["personal_note"]
    if "deck_id" in update_data:
        card.deck_id = update_data["deck_id"]
    if "forms" in update_data:
        forms_val = update_data["forms"]
        card.forms = json.dumps(forms_val) if forms_val is not None else None
    if "example_sentences" in update_data:
        es_val = update_data["example_sentences"]
        card.example_sentences = json.dumps(es_val) if es_val is not None else None
    if "image_skipped" in update_data:
        card.image_skipped = update_data["image_skipped"]
        if update_data["image_skipped"]:
            card.image_url = None  # clear image when skipped
    if "image_url" in update_data:
        card.image_url = update_data["image_url"]

    card.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(card)
    return card


async def generate_card_image(
    card_id: int,
    image_service: "ImageService",
    session: AsyncSession,
) -> Card:
    """Generate and store an image for a card.

    Raises ValueError on safety rejection, timeout, or API error.
    Never modifies card if generation fails — card stays intact.
    """
    card = await get_card(card_id, session)  # raises ValueError if not found

    try:
        image_bytes = await image_service.generate(card.target_word)
    except httpx.TimeoutException:
        logger.warning("cards.image_generation_timeout", card_id=card_id)
        raise ValueError("Image generation timed out — please try again")
    except RuntimeError as exc:
        logger.warning("cards.image_generation_error", card_id=card_id, exc=str(exc))
        raise ValueError(f"Image generation failed: {exc}")

    # Safety check — detect content type from magic bytes
    content_type = safety.detect_image_content_type(image_bytes) or "application/octet-stream"
    is_safe, reason = safety.check_image(content_type, len(image_bytes))
    if not is_safe:
        logger.warning("cards.image_safety_rejected", card_id=card_id, reason=reason)
        raise ValueError("Image filtered — please try again")

    # Store image — delete stale files from prior generations with different extensions
    ext = _CONTENT_TYPE_EXT.get(content_type, "png")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for stale_ext in _CONTENT_TYPE_EXT.values():
        if stale_ext != ext:
            stale_path = IMAGE_DIR / f"{card_id}.{stale_ext}"
            await asyncio.to_thread(stale_path.unlink, True)  # missing_ok=True

    image_path = IMAGE_DIR / f"{card_id}.{ext}"
    await asyncio.to_thread(image_path.write_bytes, image_bytes)

    try:
        card.image_url = f"/cards/{card_id}/image"
        card.image_skipped = False  # generation success clears any prior skip
        card.updated_at = datetime.now(UTC)
        await session.commit()
    except Exception:
        # Clean up the written file if the DB commit fails to avoid orphaned files
        await asyncio.to_thread(image_path.unlink, True)
        raise
    await session.refresh(card)
    logger.info("cards.image_generated", card_id=card_id, size=len(image_bytes), ext=ext)
    return card


async def delete_card(card_id: int, session: AsyncSession) -> None:
    """Delete a card by ID. Raises ValueError if not found."""
    card = await get_card(card_id, session)
    await session.delete(card)
    await session.commit()
