"""Import pipeline business logic — parsing and enrichment.

IMPORTANT: genanki is for EXPORT (Story 2.5), not for reading .apkg files.
An .apkg is a ZIP file containing 'collection.anki2' (SQLite DB).
Parse it with Python's built-in zipfile + sqlite3.
"""

import io
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# ── Domain types ──────────────────────────────────────────────────────────────


@dataclass
class CardPreviewItem:
    target_word: str
    translation: str | None
    example_sentence: str | None
    has_audio: bool
    fields_missing: list[str]  # e.g. ["translation", "forms", "example_sentences", "audio"]
    selected: bool = True  # default all selected for import


@dataclass
class ImportPreview:
    source_type: str  # "anki" | "text" | "url"
    total_cards: int
    fields_present: list[str]  # fields that exist in at least one source card
    fields_missing_summary: dict[str, int]  # field_name → count of cards missing it
    cards: list[CardPreviewItem]


# ── CardImportItem (used by API layer for /import/start) ──────────────────────


class CardImportItem(BaseModel):
    """Input model for a single card to import. Pydantic model for API deserialization."""

    target_word: str
    translation: str | None = None
    example_sentence: str | None = None


# ── .apkg parsing ─────────────────────────────────────────────────────────────


def parse_apkg(file_bytes: bytes) -> ImportPreview:
    """Parse an Anki .apkg file into an ImportPreview.

    .apkg format: ZIP archive containing 'collection.anki2' (SQLite DB).
    Relevant tables:
      - col: JSON column 'models' mapping model_id → {flds: [{name: ...}]}
      - notes: 'flds' column = fields joined by ASCII 0x1F (unit separator)
      - notes: 'mid' = model ID (to look up field names)

    Raises ValueError if the file is not a valid .apkg.
    """
    try:
        buf = io.BytesIO(file_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            if "collection.anki2" not in zf.namelist():
                raise ValueError("Invalid .apkg: missing collection.anki2")
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extract("collection.anki2", tmpdir)
                db_path = os.path.join(tmpdir, "collection.anki2")
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row

                # Load model field names from the col table
                col_row = conn.execute("SELECT models FROM col").fetchone()
                models: dict = json.loads(col_row["models"]) if col_row else {}

                notes = conn.execute("SELECT id, flds, mid FROM notes").fetchall()
                conn.close()
    except zipfile.BadZipFile:
        raise ValueError("Invalid .apkg: not a valid ZIP archive")

    cards: list[CardPreviewItem] = []
    fields_missing_counts: dict[str, int] = {}

    for note in notes:
        mid = str(note["mid"])
        field_names = [f["name"] for f in models.get(mid, {}).get("flds", [])]
        raw_fields = note["flds"].split("\x1f")

        # Map field names to values (first field = front/target, second = back/translation)
        field_map: dict[str, str] = {}
        for i, name in enumerate(field_names):
            if i < len(raw_fields):
                field_map[name.lower()] = raw_fields[i].strip()

        # Try common Anki field name variants for front/back
        front_keys = ["front", "word", "target", "expression", "vocabulary"]
        back_keys = ["back", "translation", "meaning", "definition"]

        target_word = next(
            (field_map[k] for k in front_keys if k in field_map and field_map[k]), None
        )
        if not target_word and raw_fields:
            target_word = raw_fields[0].strip()  # fallback: first field
        if not target_word:
            continue  # skip empty notes

        translation = next(
            (field_map[k] for k in back_keys if k in field_map and field_map[k]), None
        )
        if not translation and len(raw_fields) > 1:
            translation = raw_fields[1].strip() or None  # fallback: second field

        missing: list[str] = []
        if not translation:
            missing.append("translation")
            fields_missing_counts["translation"] = fields_missing_counts.get("translation", 0) + 1
        # forms and audio are always enriched (Anki doesn't store them in our schema format)
        missing.extend(["forms", "example_sentences", "audio"])
        for f in ["forms", "example_sentences", "audio"]:
            fields_missing_counts[f] = fields_missing_counts.get(f, 0) + 1

        cards.append(
            CardPreviewItem(
                target_word=target_word,
                translation=translation,
                example_sentence=None,
                has_audio=False,  # Anki audio not imported in this story
                fields_missing=missing,
                selected=True,
            )
        )

    fields_present = ["target_word"]
    if any(c.translation for c in cards):
        fields_present.append("translation")

    return ImportPreview(
        source_type="anki",
        total_cards=len(cards),
        fields_present=fields_present,
        fields_missing_summary=fields_missing_counts,
        cards=cards,
    )


# ── Text/TSV parsing ──────────────────────────────────────────────────────────

TextFormat = Literal["auto", "plain", "tsv"]


def parse_text_import(text: str, format: TextFormat = "auto") -> ImportPreview:
    """Parse plain text or TSV into ImportPreview.

    TSV format: 'word\\ttranslation' per line (3rd+ columns ignored).
    Plain format: one word/phrase per line, no translation.
    Auto: detect TSV if any line contains a tab character.
    """
    # Filter blank/whitespace-only lines but preserve original content (tabs intact for TSV)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ImportPreview(
            source_type="text",
            total_cards=0,
            fields_present=[],
            fields_missing_summary={},
            cards=[],
        )

    # Auto-detect
    effective_format: str = format
    if format == "auto":
        effective_format = "tsv" if any("\t" in line for line in lines) else "plain"

    cards: list[CardPreviewItem] = []
    for line in lines:
        if effective_format == "tsv":
            parts = line.split("\t", maxsplit=2)
            target_word = parts[0].strip()
            translation: str | None = parts[1].strip() if len(parts) > 1 else None
        else:
            target_word = line.strip()
            translation = None
        if not target_word:
            continue
        missing = ["forms", "example_sentences", "audio"]
        if not translation:
            missing.insert(0, "translation")
        cards.append(
            CardPreviewItem(
                target_word=target_word,
                translation=translation or None,
                example_sentence=None,
                has_audio=False,
                fields_missing=missing,
                selected=True,
            )
        )

    fields_missing_counts: dict[str, int] = {}
    for card in cards:
        for f in card.fields_missing:
            fields_missing_counts[f] = fields_missing_counts.get(f, 0) + 1

    return ImportPreview(
        source_type="text",
        total_cards=len(cards),
        fields_present=(["target_word"] + (["translation"] if effective_format == "tsv" else [])),
        fields_missing_summary=fields_missing_counts,
        cards=cards,
    )


# ── URL import ────────────────────────────────────────────────────────────────


async def parse_url_import(url: str) -> ImportPreview:
    """Fetch URL content and extract words as import candidates.

    Returns one card per line/word found. Uses httpx.AsyncClient (already a dep).
    Raises ValueError if URL cannot be fetched.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        raise ValueError(f"Could not fetch URL: {exc}") from exc

    # Strip HTML tags (minimal, no BeautifulSoup dep — not in project deps)
    clean = re.sub(r"<[^>]+>", " ", text)  # strip HTML tags
    clean = re.sub(r"&\w+;", " ", clean)  # strip HTML entities
    preview = parse_text_import(clean, format="auto")
    # Override source_type for URL imports
    return ImportPreview(
        source_type="url",
        total_cards=preview.total_cards,
        fields_present=preview.fields_present,
        fields_missing_summary=preview.fields_missing_summary,
        cards=preview.cards,
    )


# ── Background enrichment ─────────────────────────────────────────────────────


async def create_cards_and_job(
    cards_data: list[CardImportItem],
    target_language: str,
    deck_id: int | None,
    session: object,
) -> tuple[int, list[int]]:
    """Persist job + card stubs atomically. Returns (job_id, card_ids).

    CRITICAL: job must be committed to DB BEFORE returning (and before background
    task starts). The background task uses job_id to update progress — race condition
    if job not persisted first.
    """
    from lingosips.db.models import Card, Job

    now = datetime.now(UTC)
    # 1. Create Job first
    job = Job(
        job_type="import_enrichment",
        status="pending",
        progress_done=0,
        progress_total=len(cards_data),
        updated_at=now,
        created_at=now,
    )
    session.add(job)
    await session.flush()  # get job.id without committing

    # 2. Create Card stubs
    card_ids: list[int] = []
    for item in cards_data:
        card = Card(
            target_word=item.target_word,
            translation=item.translation,
            target_language=target_language,
            deck_id=deck_id,
            due=now,
            created_at=now,
            updated_at=now,
        )
        session.add(card)
        await session.flush()
        card_ids.append(card.id)

    await session.commit()
    return job.id, card_ids


async def run_enrichment(
    job_id: int,
    card_ids: list[int],
    db_engine_url: str,
    llm_api_key: str | None,
    llm_model: str | None,
) -> None:
    """Background enrichment task. Creates its own DB session (request context is gone).

    For each card: call LLM to fill missing fields, update progress.
    On any per-card failure: mark card with personal_note flag — never skip or delete the card.

    CRITICAL: always update job.status to "running" before starting loop,
    and "complete"/"failed" at end — even if all cards fail.
    """
    from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker as sa_sessionmaker

    from lingosips.db.models import Card, Job

    engine = create_async_engine(db_engine_url)
    async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)

    unresolved = 0
    try:
        async with async_session() as session:
            job = await session.get(Job, job_id)
            if not job:
                logger.error("import.enrichment.job_not_found", job_id=job_id)
                return
            job.status = "running"
            job.updated_at = datetime.now(UTC)
            session.add(job)
            await session.commit()

        for i, card_id in enumerate(card_ids):
            async with async_session() as session:
                card = await session.get(Card, card_id)
                if not card:
                    unresolved += 1
                    continue
                try:
                    # Only enrich if translation is missing
                    if not card.translation:
                        if llm_api_key and llm_model:
                            from lingosips.services.llm.openrouter import OpenRouterProvider

                            provider = OpenRouterProvider(api_key=llm_api_key, model=llm_model)
                        else:
                            from lingosips.services.llm.qwen_local import QwenLocalProvider

                            provider = QwenLocalProvider()
                        prompt = (
                            f"Translate '{card.target_word}' to English. "
                            f"Reply with only the translation word or phrase."
                        )
                        import asyncio

                        result = await asyncio.wait_for(
                            provider.complete([{"role": "user", "content": prompt}]),
                            timeout=15.0,
                        )
                        card.translation = result.strip()[:200] if result else None

                    card.updated_at = datetime.now(UTC)
                    session.add(card)

                    # Update job progress
                    job = await session.get(Job, job_id)
                    job.progress_done = i + 1
                    job.current_item = f"enriching '{card.target_word}'..."
                    job.updated_at = datetime.now(UTC)
                    session.add(job)
                    await session.commit()

                except Exception as exc:
                    logger.warning("import.enrichment.card_failed", card_id=card_id, error=str(exc))
                    # Flag the card — do NOT delete it
                    card.personal_note = "[Import: enrichment incomplete — please review]"
                    card.updated_at = datetime.now(UTC)
                    session.add(card)
                    unresolved += 1
                    job = await session.get(Job, job_id)
                    job.progress_done = i + 1
                    job.updated_at = datetime.now(UTC)
                    session.add(job)
                    await session.commit()

        # Mark job complete
        async with async_session() as session:
            job = await session.get(Job, job_id)
            job.status = "complete"
            job.progress_done = len(card_ids)
            job.error_message = f"unresolved:{unresolved}" if unresolved else None
            job.updated_at = datetime.now(UTC)
            session.add(job)
            await session.commit()

    except Exception as exc:
        logger.error("import.enrichment.fatal", job_id=job_id, error=str(exc))
        try:
            async with async_session() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(exc)[:500]
                    job.updated_at = datetime.now(UTC)
                    session.add(job)
                    await session.commit()
        except Exception:
            pass
    finally:
        await engine.dispose()
