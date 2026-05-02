"""Tests for core/imports.py — Anki, Text, and URL import parsing.

TDD: these tests are written BEFORE implementation to drive core/imports.py.
AC: 2, 3
"""

import io
import json
import os
import tempfile
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

# ── .apkg parsing tests ────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestParseApkg:
    def _make_apkg(self, notes: list[dict]) -> bytes:
        """Build minimal valid .apkg bytes for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "collection.anki2")
            import sqlite3

            conn = sqlite3.connect(db_path)
            conn.execute("""CREATE TABLE notes (
                id INTEGER PRIMARY KEY, flds TEXT, tags TEXT, mid INTEGER
            )""")
            # col table with minimal models JSON
            model_id = 1234567890
            models = {
                str(model_id): {
                    "flds": [{"name": "Front"}, {"name": "Back"}],
                    "name": "Basic",
                }
            }
            conn.execute("CREATE TABLE col (models TEXT)")
            conn.execute("INSERT INTO col VALUES (?)", (json.dumps(models),))
            for note in notes:
                flds = "\x1f".join([note.get("front", ""), note.get("back", "")])
                conn.execute(
                    "INSERT INTO notes (flds, tags, mid) VALUES (?, '', ?)",
                    (flds, model_id),
                )
            conn.commit()
            conn.close()
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.write(db_path, "collection.anki2")
            return buf.getvalue()

    def test_parse_valid_apkg_returns_card_list(self) -> None:
        from lingosips.core.imports import parse_apkg

        apkg = self._make_apkg(
            [
                {"front": "hola", "back": "hello"},
                {"front": "agua", "back": "water"},
            ]
        )
        result = parse_apkg(apkg)
        assert len(result.cards) == 2
        assert result.cards[0].target_word == "hola"
        assert result.cards[0].translation == "hello"
        assert result.total_cards == 2

    def test_parse_apkg_missing_back_flags_translation_missing(self) -> None:
        from lingosips.core.imports import parse_apkg

        apkg = self._make_apkg([{"front": "melancólico", "back": ""}])
        result = parse_apkg(apkg)
        assert "translation" in result.cards[0].fields_missing

    def test_parse_empty_apkg_returns_empty_list(self) -> None:
        from lingosips.core.imports import parse_apkg

        apkg = self._make_apkg([])
        result = parse_apkg(apkg)
        assert result.total_cards == 0
        assert result.cards == []

    def test_parse_apkg_invalid_zip_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_apkg

        with pytest.raises(ValueError, match="Invalid .apkg"):
            parse_apkg(b"not a zip file")

    def test_parse_apkg_valid_zip_missing_collection_raises_value_error(self) -> None:
        """Valid ZIP file that lacks collection.anki2 should raise ValueError."""
        from lingosips.core.imports import parse_apkg

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other_file.txt", "not an anki db")
        with pytest.raises(ValueError, match="missing collection.anki2"):
            parse_apkg(buf.getvalue())

    def test_parse_apkg_note_with_no_known_field_names_uses_raw_fallback(self) -> None:
        """Note without recognized field names should fall back to raw_fields[0]."""
        from lingosips.core.imports import parse_apkg

        # Use field names that don't match front_keys or back_keys
        apkg = self._make_apkg_with_fields(
            field_names=["Term", "Definition"],
            notes=[("volcán", "volcano")],
        )
        result = parse_apkg(apkg)
        # Should still extract via fallback (raw_fields[0])
        assert result.total_cards == 1
        assert result.cards[0].target_word == "volcán"

    def test_parse_apkg_note_with_empty_first_field_is_skipped(self) -> None:
        """Note with empty first field should be skipped entirely."""
        from lingosips.core.imports import parse_apkg

        apkg = self._make_apkg_with_fields(
            field_names=["SomeUnknown", "Back"],
            notes=[("", "this should be skipped")],
        )
        result = parse_apkg(apkg)
        assert result.total_cards == 0
        assert result.cards == []

    def _make_apkg_with_fields(self, field_names: list[str], notes: list[tuple[str, str]]) -> bytes:
        """Build .apkg with custom field names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "collection.anki2")
            import sqlite3

            conn = sqlite3.connect(db_path)
            model_id = 9999
            models = {
                str(model_id): {
                    "flds": [{"name": n} for n in field_names],
                    "name": "Custom",
                }
            }
            conn.execute("CREATE TABLE col (models TEXT)")
            conn.execute("INSERT INTO col VALUES (?)", (json.dumps(models),))
            conn.execute(
                "CREATE TABLE notes (id INTEGER PRIMARY KEY, flds TEXT, tags TEXT, mid INTEGER)"
            )
            for front, back in notes:
                flds = "\x1f".join([front, back])
                conn.execute(
                    "INSERT INTO notes (flds, tags, mid) VALUES (?, '', ?)", (flds, model_id)
                )
            conn.commit()
            conn.close()
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.write(db_path, "collection.anki2")
            return buf.getvalue()


# ── Text/TSV parsing tests ─────────────────────────────────────────────────────


@pytest.mark.anyio
class TestParseTextImport:
    def test_tsv_two_column_extracts_word_and_translation(self) -> None:
        from lingosips.core.imports import parse_text_import

        result = parse_text_import("hola\thello\nagua\twater", format="tsv")
        assert len(result.cards) == 2
        assert result.cards[0].target_word == "hola"
        assert result.cards[0].translation == "hello"
        assert result.cards[1].translation == "water"

    def test_plain_text_each_line_is_one_card(self) -> None:
        from lingosips.core.imports import parse_text_import

        result = parse_text_import("melancólico\nagua\nhola", format="plain")
        assert len(result.cards) == 3
        assert all(c.translation is None for c in result.cards)

    def test_auto_detect_tsv_when_tabs_present(self) -> None:
        from lingosips.core.imports import parse_text_import

        result = parse_text_import("hola\thello\nagua\twater", format="auto")
        assert result.cards[0].translation == "hello"

    def test_auto_detect_plain_when_no_tabs(self) -> None:
        from lingosips.core.imports import parse_text_import

        result = parse_text_import("hola\nagua\nhello", format="auto")
        assert all(c.translation is None for c in result.cards)

    def test_empty_lines_skipped(self) -> None:
        from lingosips.core.imports import parse_text_import

        result = parse_text_import("hola\n\nagua\n\n", format="plain")
        assert len(result.cards) == 2

    def test_tsv_three_column_ignores_extra(self) -> None:
        from lingosips.core.imports import parse_text_import

        result = parse_text_import("hola\thello\tnotes", format="tsv")
        assert result.cards[0].target_word == "hola"
        assert result.cards[0].translation == "hello"

    def test_whitespace_only_lines_are_skipped(self) -> None:
        """Lines with only whitespace are filtered before any processing."""
        from lingosips.core.imports import parse_text_import

        # "   " is stripped to "", filtered by `if line.strip()`
        result = parse_text_import("hola\n   \nagua\n\t", format="plain")
        assert len(result.cards) == 2
        assert result.cards[0].target_word == "hola"
        assert result.cards[1].target_word == "agua"

    def test_tsv_empty_first_column_row_is_skipped(self) -> None:
        """TSV row whose first column is empty after strip is skipped (line 196)."""
        from lingosips.core.imports import parse_text_import

        # "\thello" → parts[0].strip() == "" → target_word is empty → skip
        result = parse_text_import("\thello\nhola\tworld", format="tsv")
        assert len(result.cards) == 1
        assert result.cards[0].target_word == "hola"
        assert result.cards[0].translation == "world"


# ── URL parsing tests ──────────────────────────────────────────────────────────


@pytest.mark.anyio
class TestParseUrlImport:
    async def test_url_fetches_and_returns_word_list(self) -> None:
        from lingosips.core.imports import parse_url_import

        html_content = "hola agua melancólico"
        with patch("lingosips.core.imports.httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(
                return_value=type(
                    "R",
                    (),
                    {
                        "text": html_content,
                        "status_code": 200,
                        "raise_for_status": lambda self: None,
                    },
                )()
            )
            result = await parse_url_import("http://example.com/words")
        assert len(result.cards) >= 1
        assert result.source_type == "url"

    async def test_url_fetch_error_raises_value_error(self) -> None:
        import httpx

        from lingosips.core.imports import parse_url_import

        with patch("lingosips.core.imports.httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            with pytest.raises(ValueError, match="Could not fetch URL"):
                await parse_url_import("http://unreachable.example.com")

    async def test_url_import_returns_url_source_type(self) -> None:
        """parse_url_import must return source_type='url' (not 'text')."""
        from lingosips.core.imports import parse_url_import

        with patch("lingosips.core.imports.httpx.AsyncClient") as mock_client:
            mock_instance = mock_client.return_value.__aenter__.return_value
            mock_instance.get = AsyncMock(
                return_value=type(
                    "R",
                    (),
                    {
                        "text": "hola agua",
                        "status_code": 200,
                        "raise_for_status": lambda self: None,
                    },
                )()
            )
            result = await parse_url_import("http://example.com/words")
        assert result.source_type == "url"  # Must override "text" from parse_text_import


# ── Direct create_cards_and_job tests ─────────────────────────────────────────


@pytest.mark.anyio
class TestCreateCardsAndJob:
    async def test_create_cards_and_job_returns_job_id_and_card_ids(self, session) -> None:
        from lingosips.core.imports import CardImportItem, create_cards_and_job

        job_id, card_ids = await create_cards_and_job(
            cards_data=[
                CardImportItem(target_word="hola", translation="hello"),
                CardImportItem(target_word="agua", translation=None),
            ],
            target_language="es",
            deck_id=None,
            session=session,
        )
        assert isinstance(job_id, int)
        assert len(card_ids) == 2
        assert all(isinstance(cid, int) for cid in card_ids)

    async def test_create_cards_and_job_persists_job_to_db(self, session) -> None:
        from lingosips.core.imports import CardImportItem, create_cards_and_job
        from lingosips.db.models import Job

        job_id, _ = await create_cards_and_job(
            cards_data=[CardImportItem(target_word="volcán")],
            target_language="es",
            deck_id=None,
            session=session,
        )
        # Need a new session read — commit was done inside create_cards_and_job
        # so the session should reflect the committed state
        await session.refresh(await session.get(Job, job_id))
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.job_type == "import_enrichment"
        assert job.status == "pending"
        assert job.progress_total == 1

    async def test_create_cards_and_job_persists_cards_to_db(self, session) -> None:
        from sqlalchemy import select

        from lingosips.core.imports import CardImportItem, create_cards_and_job
        from lingosips.db.models import Card

        _, card_ids = await create_cards_and_job(
            cards_data=[CardImportItem(target_word="melancólico", translation="melancholy")],
            target_language="es",
            deck_id=None,
            session=session,
        )
        result = await session.execute(select(Card).where(Card.id == card_ids[0]))
        card = result.scalars().first()
        assert card is not None
        assert card.target_word == "melancólico"
        assert card.translation == "melancholy"
        assert card.target_language == "es"


# ── run_enrichment tests ──────────────────────────────────────────────────────


@pytest.mark.anyio
class TestRunEnrichment:
    """Tests for run_enrichment — uses a temporary file-based SQLite DB because
    run_enrichment creates its own engine from a URL string."""

    async def _setup_db(self, tmp_path, notes: list[dict]) -> tuple[str, int, list[int]]:
        """Create temp DB, insert a job + cards, return (db_url, job_id, card_ids)."""
        from datetime import UTC, datetime

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker
        from sqlmodel import SQLModel

        import lingosips.db.models  # noqa: F401 — registers models
        from lingosips.db.models import Card, Job

        db_url = f"sqlite+aiosqlite:///{tmp_path}/enrichment_test.db"
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        now = datetime.now(UTC)
        async with async_session() as s:
            job = Job(
                job_type="import_enrichment",
                status="pending",
                progress_done=0,
                progress_total=len(notes),
                updated_at=now,
                created_at=now,
            )
            s.add(job)
            await s.flush()
            card_ids = []
            for note in notes:
                card = Card(
                    target_word=note["target_word"],
                    translation=note.get("translation"),
                    target_language="es",
                    due=now,
                    created_at=now,
                    updated_at=now,
                )
                s.add(card)
                await s.flush()
                card_ids.append(card.id)
            await s.commit()
            await s.refresh(job)
            job_id = job.id
        await engine.dispose()
        return db_url, job_id, card_ids

    async def test_run_enrichment_marks_job_complete_when_cards_have_translations(
        self, tmp_path
    ) -> None:
        """Cards that already have translations skip LLM; job reaches 'complete'."""

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Job

        db_url, job_id, card_ids = await self._setup_db(
            tmp_path,
            [
                {"target_word": "hola", "translation": "hello"},
                {"target_word": "agua", "translation": "water"},
            ],
        )
        await run_enrichment(
            job_id=job_id,
            card_ids=card_ids,
            db_engine_url=db_url,
            llm_api_key=None,
            llm_model=None,
        )

        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            job = await s.get(Job, job_id)
            assert job is not None
            assert job.status == "complete"
            assert job.progress_done == 2
            assert job.error_message is None  # no unresolved
        await engine.dispose()

    async def test_run_enrichment_no_cards_marks_job_complete(self, tmp_path) -> None:
        """run_enrichment with empty card_ids still marks job complete."""
        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Job

        db_url, job_id, card_ids = await self._setup_db(tmp_path, [])
        await run_enrichment(
            job_id=job_id,
            card_ids=[],
            db_engine_url=db_url,
            llm_api_key=None,
            llm_model=None,
        )

        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            job = await s.get(Job, job_id)
            assert job.status == "complete"
            assert job.progress_done == 0
        await engine.dispose()

    async def test_run_enrichment_job_not_found_returns_gracefully(self, tmp_path) -> None:
        """run_enrichment with a non-existent job_id logs and returns without crash."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlmodel import SQLModel

        import lingosips.db.models  # noqa: F401

        db_url = f"sqlite+aiosqlite:///{tmp_path}/not_found_test.db"
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        await engine.dispose()

        from lingosips.core.imports import run_enrichment

        # Should not raise — just logs and returns
        await run_enrichment(
            job_id=99999,
            card_ids=[],
            db_engine_url=db_url,
            llm_api_key=None,
            llm_model=None,
        )

    async def test_run_enrichment_uses_qwen_when_translation_missing(self, tmp_path) -> None:
        """Cards missing translation trigger the QwenLocalProvider path (mocked)."""
        from unittest.mock import AsyncMock, patch

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Card, Job

        db_url, job_id, card_ids = await self._setup_db(
            tmp_path,
            [{"target_word": "melancólico", "translation": None}],
        )

        with patch("lingosips.services.llm.qwen_local.QwenLocalProvider") as mock_provider_cls:
            mock_instance = mock_provider_cls.return_value
            mock_instance.complete = AsyncMock(return_value="melancholy")

            await run_enrichment(
                job_id=job_id,
                card_ids=card_ids,
                db_engine_url=db_url,
                llm_api_key=None,  # no API key → QwenLocalProvider
                llm_model=None,
            )

        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            card = await s.get(Card, card_ids[0])
            assert card.translation == "melancholy"
            job = await s.get(Job, job_id)
            assert job.status == "complete"
        await engine.dispose()

    async def test_run_enrichment_handles_card_enrichment_failure(self, tmp_path) -> None:
        """Card that fails enrichment is flagged with personal_note; job still completes."""
        from unittest.mock import AsyncMock, patch

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Card, Job

        db_url, job_id, card_ids = await self._setup_db(
            tmp_path,
            [{"target_word": "volcán", "translation": None}],
        )

        with patch("lingosips.services.llm.qwen_local.QwenLocalProvider") as mock_provider_cls:
            mock_instance = mock_provider_cls.return_value
            mock_instance.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

            await run_enrichment(
                job_id=job_id,
                card_ids=card_ids,
                db_engine_url=db_url,
                llm_api_key=None,
                llm_model=None,
            )

        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            card = await s.get(Card, card_ids[0])
            assert card.personal_note is not None
            assert "enrichment incomplete" in card.personal_note
            job = await s.get(Job, job_id)
            assert job.status == "complete"
            assert job.error_message and "unresolved:1" in job.error_message
        await engine.dispose()

    async def test_run_enrichment_uses_openrouter_when_api_key_provided(self, tmp_path) -> None:
        """run_enrichment uses OpenRouterProvider when api_key+model are set (lines 349-352)."""
        from unittest.mock import AsyncMock, patch

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Card, Job

        db_url, job_id, card_ids = await self._setup_db(
            tmp_path,
            [{"target_word": "perro", "translation": None}],
        )

        with patch("lingosips.services.llm.openrouter.OpenRouterProvider") as mock_cls:
            mock_instance = mock_cls.return_value
            mock_instance.complete = AsyncMock(return_value="dog")

            await run_enrichment(
                job_id=job_id,
                card_ids=card_ids,
                db_engine_url=db_url,
                llm_api_key="test-openrouter-key",  # triggers OpenRouterProvider branch
                llm_model="anthropic/claude-3-haiku",
            )

        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            card = await s.get(Card, card_ids[0])
            assert card.translation == "dog"
            job = await s.get(Job, job_id)
            assert job.status == "complete"
        await engine.dispose()

    async def test_run_enrichment_fatal_error_marks_job_failed(self, tmp_path) -> None:
        """Fatal exception in run_enrichment marks job as 'failed' (lines 404-414)."""
        from unittest.mock import patch

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Job

        db_url, job_id, _ = await self._setup_db(tmp_path, [])

        # Patch commit so the final "mark complete" commit (call #2) raises,
        # triggering the outer except block; call #3 (inside outer except) succeeds.
        original_commit = SAAsyncSession.commit
        commit_calls = 0

        async def failing_second_commit(self):
            nonlocal commit_calls
            commit_calls += 1
            if commit_calls == 2:  # "mark complete" commit → trigger outer except
                raise RuntimeError("Simulated DB failure on final commit")
            return await original_commit(self)

        with patch.object(SAAsyncSession, "commit", failing_second_commit):
            await run_enrichment(
                job_id=job_id,
                card_ids=[],
                db_engine_url=db_url,
                llm_api_key=None,
                llm_model=None,
            )

        # The outer except should have written job.status = "failed" via commit #3
        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            job = await s.get(Job, job_id)
            assert job is not None
            assert job.status == "failed"
            assert job.error_message is not None
            assert "Simulated DB failure" in job.error_message
        await engine.dispose()

    async def test_run_enrichment_inner_except_handles_secondary_db_failure(self, tmp_path) -> None:
        """Inner except:pass handles DB failure inside outer except block (lines 415-416)."""
        from unittest.mock import patch

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import sessionmaker as sa_sessionmaker

        from lingosips.core.imports import run_enrichment
        from lingosips.db.models import Job

        db_url, job_id, _ = await self._setup_db(tmp_path, [])

        # Both commit #2 and #3 raise → inner except: pass catches #3
        original_commit = SAAsyncSession.commit
        commit_calls = 0

        async def double_failing_commit(self):
            nonlocal commit_calls
            commit_calls += 1
            if commit_calls >= 2:
                raise RuntimeError("DB completely unavailable")
            return await original_commit(self)

        with patch.object(SAAsyncSession, "commit", double_failing_commit):
            # Should not raise — inner except: pass absorbs the secondary failure
            await run_enrichment(
                job_id=job_id,
                card_ids=[],
                db_engine_url=db_url,
                llm_api_key=None,
                llm_model=None,
            )

        # Job stuck in "running" state since both commits #2 and #3 failed
        engine = create_async_engine(db_url)
        async_session = sa_sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
        async with async_session() as s:
            job = await s.get(Job, job_id)
            assert job is not None
            assert job.status == "running"  # never reached "complete" or "failed"
        await engine.dispose()


# ── Helpers for .lingosips test fixtures ──────────────────────────────────────


def _make_lingosips_file(
    deck_name: str = "Test Deck",
    target_language: str = "es",
    cards: list[dict] | None = None,
    format_version: str = "1",
    extra_keys: dict | None = None,
    audio_files: dict[str, bytes] | None = None,
) -> bytes:
    """Build a minimal valid .lingosips ZIP file for testing."""
    if cards is None:
        cards = [
            {
                "target_word": "hola",
                "translation": "hello",
                "forms": None,
                "example_sentences": None,
                "personal_note": None,
                "image_skipped": False,
                "card_type": "word",
                "target_language": target_language,
                "stability": 2.5,
                "difficulty": 5.0,
                "due": "2026-05-15T10:00:00+00:00",
                "last_review": "2026-05-01T10:00:00+00:00",
                "reps": 3,
                "lapses": 0,
                "fsrs_state": "Review",
                "audio_file": None,
            }
        ]
    deck_json: dict = {
        "format_version": format_version,
        "deck": {"name": deck_name, "target_language": target_language},
        "cards": cards,
    }
    if extra_keys:
        deck_json.update(extra_keys)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("deck.json", json.dumps(deck_json, ensure_ascii=False, indent=2))
        if audio_files:
            for filename, data in audio_files.items():
                zf.writestr(f"audio/{filename}", data)
    return buf.getvalue()


# ── TestParseLingosipsFile ─────────────────────────────────────────────────────


@pytest.mark.anyio
class TestParseLingosipsFile:
    def test_valid_file_returns_preview(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        file_bytes = _make_lingosips_file()
        preview = parse_lingosips_file(file_bytes)
        assert preview.deck_name == "Test Deck"
        assert preview.target_language == "es"
        assert preview.total_cards == 1
        assert len(preview.sample_cards) == 1
        assert preview.sample_cards[0].target_word == "hola"

    def test_not_a_zip_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        with pytest.raises(ValueError, match="valid .lingosips archive"):
            parse_lingosips_file(b"not a zip")

    def test_missing_deck_json_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other.txt", "data")
        with pytest.raises(ValueError, match="missing required deck.json"):
            parse_lingosips_file(buf.getvalue())

    def test_missing_format_version_key_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            payload = {"deck": {"name": "X", "target_language": "es"}, "cards": []}
            zf.writestr("deck.json", json.dumps(payload))
        with pytest.raises(ValueError, match="missing required key: format_version"):
            parse_lingosips_file(buf.getvalue())

    def test_missing_deck_key_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("deck.json", json.dumps({"format_version": "1", "cards": []}))
        with pytest.raises(ValueError, match="missing required key: deck"):
            parse_lingosips_file(buf.getvalue())

    def test_missing_cards_key_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "deck.json",
                json.dumps({"format_version": "1", "deck": {"name": "X", "target_language": "es"}}),
            )
        with pytest.raises(ValueError, match="missing required key: cards"):
            parse_lingosips_file(buf.getvalue())

    def test_card_missing_target_word_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        file_bytes = _make_lingosips_file(cards=[{"translation": "hello"}])
        with pytest.raises(ValueError, match="Card 0: missing required field 'target_word'"):
            parse_lingosips_file(file_bytes)

    def test_card_empty_target_word_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        file_bytes = _make_lingosips_file(cards=[{"target_word": "   ", "target_language": "es"}])
        with pytest.raises(ValueError, match="Card 0: missing required field 'target_word'"):
            parse_lingosips_file(file_bytes)

    def test_unsupported_format_version_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            payload = {
                "format_version": "2",
                "deck": {"name": "X", "target_language": "es"},
                "cards": [],
            }
            zf.writestr("deck.json", json.dumps(payload))
        with pytest.raises(ValueError, match="Unsupported format_version"):
            parse_lingosips_file(buf.getvalue())

    def test_format_version_integer_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # format_version as integer (not string) — spec requires string "1"
            payload = {
                "format_version": 1,
                "deck": {"name": "X", "target_language": "es"},
                "cards": [],
            }
            zf.writestr("deck.json", json.dumps(payload))
        with pytest.raises(ValueError, match="Unsupported format_version"):
            parse_lingosips_file(buf.getvalue())

    def test_sample_cards_limited_to_five(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        many_cards = [{"target_word": f"word{i}", "target_language": "es"} for i in range(10)]
        file_bytes = _make_lingosips_file(cards=many_cards)
        preview = parse_lingosips_file(file_bytes)
        assert preview.total_cards == 10
        assert len(preview.sample_cards) == 5  # capped at 5

    def test_has_audio_true_when_card_has_audio_file(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        cards = [
            {
                "target_word": "hola",
                "target_language": "es",
                "audio_file": "42.wav",
            }
        ]
        file_bytes = _make_lingosips_file(cards=cards)
        preview = parse_lingosips_file(file_bytes)
        assert preview.has_audio is True

    def test_has_audio_false_when_no_audio(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        file_bytes = _make_lingosips_file()  # default cards have audio_file=None
        preview = parse_lingosips_file(file_bytes)
        assert preview.has_audio is False

    def test_missing_deck_name_field_raises_value_error(self) -> None:
        from lingosips.core.imports import parse_lingosips_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "deck.json",
                json.dumps({"format_version": "1", "deck": {"target_language": "es"}, "cards": []}),
            )
        with pytest.raises(ValueError, match="missing required deck field: name"):
            parse_lingosips_file(buf.getvalue())


# ── TestImportLingosipsDeck ────────────────────────────────────────────────────


@pytest.mark.anyio
class TestImportLingosipsDeck:
    async def test_import_valid_file_creates_deck_and_cards(self, session) -> None:
        from lingosips.core.imports import import_lingosips_deck

        file_bytes = _make_lingosips_file(deck_name="Imported Deck", target_language="es")
        deck_id, card_count = await import_lingosips_deck(file_bytes, session)
        assert card_count == 1
        assert isinstance(deck_id, int)

        # Verify deck was created
        from sqlalchemy import select

        from lingosips.db.models import Deck

        deck = (await session.execute(select(Deck).where(Deck.id == deck_id))).scalar_one()
        assert deck.name == "Imported Deck"
        assert deck.target_language == "es"

    async def test_import_cards_have_correct_fsrs_state(self, session) -> None:
        from sqlalchemy import select

        from lingosips.core.imports import import_lingosips_deck
        from lingosips.db.models import Card

        cards = [
            {
                "target_word": "melancólico",
                "translation": "melancholic",
                "target_language": "es",
                "stability": 2.5,
                "difficulty": 5.0,
                "due": "2026-05-15T10:00:00+00:00",
                "last_review": "2026-05-01T10:00:00+00:00",
                "reps": 3,
                "lapses": 1,
                "fsrs_state": "Review",
                "audio_file": None,
            }
        ]
        file_bytes = _make_lingosips_file(deck_name="FSRS Deck", cards=cards)
        deck_id, _ = await import_lingosips_deck(file_bytes, session)

        result = await session.execute(select(Card).where(Card.deck_id == deck_id))
        card = result.scalars().first()
        assert card is not None
        assert card.target_word == "melancólico"
        assert card.stability == 2.5
        assert card.reps == 3
        assert card.lapses == 1
        assert card.fsrs_state == "Review"

    async def test_import_duplicate_deck_name_raises_value_error(self, session) -> None:
        from lingosips.core.imports import import_lingosips_deck

        file_bytes = _make_lingosips_file(deck_name="Duplicate Deck")
        await import_lingosips_deck(file_bytes, session)
        with pytest.raises(ValueError, match="conflict"):
            await import_lingosips_deck(file_bytes, session)

    async def test_import_malformed_file_raises_value_error(self, session) -> None:
        from lingosips.core.imports import import_lingosips_deck

        with pytest.raises(ValueError, match="valid .lingosips archive"):
            await import_lingosips_deck(b"not a zip", session)

    async def test_import_audio_files_stored_and_url_set(self, session, tmp_path) -> None:
        from unittest.mock import patch

        from sqlalchemy import select

        from lingosips.core.imports import import_lingosips_deck
        from lingosips.db.models import Card

        cards = [
            {
                "target_word": "hola",
                "target_language": "es",
                "stability": 0.0,
                "difficulty": 0.0,
                "due": "2026-05-15T10:00:00+00:00",
                "last_review": None,
                "reps": 0,
                "lapses": 0,
                "fsrs_state": "New",
                "audio_file": "99.wav",
            }
        ]
        audio_data = b"RIFF fake wav"
        file_bytes = _make_lingosips_file(
            deck_name="Audio Import Deck",
            cards=cards,
            audio_files={"99.wav": audio_data},
        )

        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        with patch("lingosips.core.imports.AUDIO_DIR", audio_dir):
            deck_id, card_count = await import_lingosips_deck(file_bytes, session)

        assert card_count == 1
        result = await session.execute(select(Card).where(Card.deck_id == deck_id))
        card = result.scalars().first()
        assert card is not None
        assert card.audio_url is not None
        assert card.audio_url.startswith("/cards/")
        # Check audio file was written to disk
        written_file = audio_dir / f"{card.id}.wav"
        assert written_file.exists()
        assert written_file.read_bytes() == audio_data

    async def test_import_audio_file_missing_in_zip_skips_gracefully(
        self, session, tmp_path
    ) -> None:
        from unittest.mock import patch

        from sqlalchemy import select

        from lingosips.core.imports import import_lingosips_deck
        from lingosips.db.models import Card

        cards = [
            {
                "target_word": "agua",
                "target_language": "es",
                "stability": 0.0,
                "difficulty": 0.0,
                "due": "2026-05-15T10:00:00+00:00",
                "last_review": None,
                "reps": 0,
                "lapses": 0,
                "fsrs_state": "New",
                "audio_file": "missing.wav",  # not in ZIP
            }
        ]
        file_bytes = _make_lingosips_file(deck_name="Missing Audio Deck", cards=cards)

        audio_dir = tmp_path / "audio2"
        audio_dir.mkdir()
        with patch("lingosips.core.imports.AUDIO_DIR", audio_dir):
            deck_id, _ = await import_lingosips_deck(file_bytes, session)

        result = await session.execute(select(Card).where(Card.deck_id == deck_id))
        card = result.scalars().first()
        assert card is not None
        assert card.audio_url is None  # gracefully skipped
