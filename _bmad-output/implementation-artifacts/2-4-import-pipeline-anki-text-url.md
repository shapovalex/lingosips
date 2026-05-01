# Story 2.4: Import Pipeline — Anki, Text & URL

Status: review

## Story

As a user,
I want to import vocabulary from an Anki .apkg file, plain text/TSV, or a URL — with AI enriching missing fields in the background while I keep using the app —
so that my existing vocabulary investments are upgraded instantly.

> **Key clarification — genanki is write-only:** The `genanki` library (already a dep) is used only for EXPORTING Anki packages (Story 2.5). For READING .apkg files in this story, use Python's built-in `zipfile` + `sqlite3` — an .apkg file is a renamed ZIP containing `collection.anki2` (a SQLite database). Never use genanki for parsing.

## Acceptance Criteria

1. **Given** I open the Import screen
   **When** it loads
   **Then** three input sources are shown: Anki .apkg file picker (with drag-and-drop), plain text/TSV paste/file picker, and URL input
   **And** the screen uses an enum-driven state machine (never boolean flags): `idle | parsing | preview | enriching | complete | error`

2. **Given** I upload an Anki .apkg file
   **When** `POST /import/preview/anki` processes it
   **Then** a deck preview renders: total card count, which fields are present in the source, and how many cards are missing each field (translation, audio, example)
   **And** all cards are pre-selected (checkbox) with an option to deselect individual cards

3. **Given** I paste text or provide a URL
   **When** `POST /import/preview/text` or `POST /import/preview/url` processes it
   **Then** candidate words/phrases are detected and shown in a checklist preview — I can select which to import
   **And** TSV format (`word\ttranslation`) pre-fills translation from the second column; plain text treats each line as a new card with no translation

4. **Given** I confirm import (click "Import & Enrich")
   **When** `POST /import/start` is called
   **Then** job status is persisted to the `jobs` table with `status="pending"` BEFORE any async enrichment work begins
   **And** card records are created in SQLite immediately with available fields (empty/null for missing fields)
   **And** `BackgroundTasks` launches enrichment asynchronously — the HTTP response returns `{job_id, card_count}` immediately
   **And** `useAppStore.activeImportJobId` is set to the returned `job_id`

5. **Given** enrichment is running in the background
   **When** I navigate to any other screen
   **Then** enrichment continues uninterrupted (backend BackgroundTasks, unaffected by navigation)
   **And** the Import icon in the sidebar/bottom nav shows a persistent progress ring
   **And** the progress ring reads from `useAppStore.importProgress` (updated by `useImportProgress` hook)

6. **Given** `GET /import/{job_id}/progress` is subscribed via SSE
   **Then** `progress` events emit: `{"done": N, "total": M, "current_item": "enriching 'melancólico'..."}`
   **And** a final `complete` event emits: `{"enriched": N, "unresolved": M}`
   **And** on `complete`, `useAppStore` receives the result and fires `addNotification({ type: "success", message: "N cards enriched · M fields could not be resolved" })`
   **And** `activeImportJobId` is cleared after the completion notification

7. **Given** enrichment completes
   **When** the job finishes
   **Then** cards with unresolved fields (LLM failed to generate translation/forms/example) are flagged via `personal_note` = `"[Import: enrichment incomplete — please review]"` — NOT silently dropped
   **And** the Toast notification includes the honest unresolved count

8. **Given** `GET /import/{job_id}` is called for a non-existent job_id
   **Then** a `404` response with RFC 7807 body is returned: `{"type": "/errors/job-not-found", ...}`

**API tests required:** job persists before async work, progress SSE complete sequence, partial enrichment failure flags cards not drops, 404 on unknown job_id, navigate-away safety (enrichment survives connection drop).

## Tasks / Subtasks

> **TDD MANDATORY**: Write all failing tests BEFORE writing any implementation code. Every task marked [TDD] requires the test class created and failing first.

---

### Backend — T1: Core import logic — .apkg parsing [TDD — FIRST]

- [x] **T1.1: Create `tests/core/test_imports.py`** — write failing `TestParseApkg` class:
  ```python
  import io, zipfile, sqlite3, json, tempfile, os
  import pytest
  from lingosips.core.imports import parse_apkg, CardPreviewItem

  class TestParseApkg:
      def _make_apkg(self, notes: list[dict]) -> bytes:
          """Build minimal valid .apkg bytes for testing."""
          with tempfile.TemporaryDirectory() as tmpdir:
              db_path = os.path.join(tmpdir, "collection.anki2")
              conn = sqlite3.connect(db_path)
              conn.execute("""CREATE TABLE notes (
                  id INTEGER PRIMARY KEY, flds TEXT, tags TEXT, mid INTEGER
              )""")
              # col table with minimal models JSON
              model_id = 1234567890
              models = {str(model_id): {"flds": [{"name": "Front"}, {"name": "Back"}], "name": "Basic"}}
              conn.execute("CREATE TABLE col (models TEXT)")
              conn.execute("INSERT INTO col VALUES (?)", (json.dumps(models),))
              for note in notes:
                  flds = "\x1f".join([note.get("front", ""), note.get("back", "")])
                  conn.execute("INSERT INTO notes (flds, tags, mid) VALUES (?, '', ?)", (flds, model_id))
              conn.commit()
              conn.close()
              buf = io.BytesIO()
              with zipfile.ZipFile(buf, "w") as zf:
                  zf.write(db_path, "collection.anki2")
              return buf.getvalue()

      def test_parse_valid_apkg_returns_card_list(self):
          apkg = self._make_apkg([
              {"front": "hola", "back": "hello"},
              {"front": "agua", "back": "water"},
          ])
          result = parse_apkg(apkg)
          assert len(result.cards) == 2
          assert result.cards[0].target_word == "hola"
          assert result.cards[0].translation == "hello"
          assert result.total_cards == 2

      def test_parse_apkg_missing_back_flags_translation_missing(self):
          apkg = self._make_apkg([{"front": "melancólico", "back": ""}])
          result = parse_apkg(apkg)
          assert "translation" in result.cards[0].fields_missing

      def test_parse_empty_apkg_returns_empty_list(self):
          apkg = self._make_apkg([])
          result = parse_apkg(apkg)
          assert result.total_cards == 0
          assert result.cards == []

      def test_parse_apkg_invalid_zip_raises_value_error(self):
          with pytest.raises(ValueError, match="Invalid .apkg"):
              parse_apkg(b"not a zip file")
  ```

- [x] **T1.2: Create `src/lingosips/core/imports.py`** — implement `parse_apkg()`:
  ```python
  """Import pipeline business logic — parsing and enrichment.

  IMPORTANT: genanki is for EXPORT (Story 2.5), not for reading .apkg files.
  An .apkg is a ZIP file containing 'collection.anki2' (SQLite DB).
  Parse it with Python's built-in zipfile + sqlite3.
  """
  import io, json, sqlite3, tempfile, zipfile, os
  from dataclasses import dataclass, field
  from datetime import UTC, datetime

  from sqlmodel.ext.asyncio.session import AsyncSession
  import structlog

  from lingosips.services.llm.base import AbstractLLMProvider
  from lingosips.services.speech.base import AbstractSpeechProvider

  logger = structlog.get_logger(__name__)

  @dataclass
  class CardPreviewItem:
      target_word: str
      translation: str | None
      example_sentence: str | None
      has_audio: bool
      fields_missing: list[str]  # e.g. ["translation", "forms", "example_sentences", "audio"]
      selected: bool = True      # default all selected for import

  @dataclass
  class ImportPreview:
      source_type: str  # "anki" | "text" | "url"
      total_cards: int
      fields_present: list[str]   # fields that exist in at least one source card
      fields_missing_summary: dict[str, int]  # field_name → count of cards missing it
      cards: list[CardPreviewItem]

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

          cards.append(CardPreviewItem(
              target_word=target_word,
              translation=translation,
              example_sentence=None,
              has_audio=False,  # Anki audio not imported in this story
              fields_missing=missing,
              selected=True,
          ))

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
  ```

---

### Backend — T2: Core import logic — Text/TSV & URL parsing [TDD — FIRST]

- [x] **T2.1: Add failing tests to `tests/core/test_imports.py`**:
  ```python
  import pytest
  from unittest.mock import AsyncMock, patch
  from lingosips.core.imports import parse_text_import, parse_url_import, TextFormat

  class TestParseTextImport:
      def test_tsv_two_column_extracts_word_and_translation(self):
          result = parse_text_import("hola\thello\nagua\twater", format="tsv")
          assert len(result.cards) == 2
          assert result.cards[0].target_word == "hola"
          assert result.cards[0].translation == "hello"
          assert result.cards[1].translation == "water"

      def test_plain_text_each_line_is_one_card(self):
          result = parse_text_import("melancólico\nagua\nhola", format="plain")
          assert len(result.cards) == 3
          assert all(c.translation is None for c in result.cards)

      def test_auto_detect_tsv_when_tabs_present(self):
          result = parse_text_import("hola\thello\nagua\twater", format="auto")
          assert result.cards[0].translation == "hello"

      def test_auto_detect_plain_when_no_tabs(self):
          result = parse_text_import("hola\nagua\nhello", format="auto")
          assert all(c.translation is None for c in result.cards)

      def test_empty_lines_skipped(self):
          result = parse_text_import("hola\n\nagua\n\n", format="plain")
          assert len(result.cards) == 2

      def test_tsv_three_column_ignores_extra(self):
          result = parse_text_import("hola\thello\tnotes", format="tsv")
          assert result.cards[0].target_word == "hola"
          assert result.cards[0].translation == "hello"

  class TestParseUrlImport:
      @pytest.mark.anyio
      async def test_url_fetches_and_returns_word_list(self):
          html_content = "hola agua melancólico"
          with patch("lingosips.core.imports.httpx.AsyncClient") as mock_client:
              mock_instance = mock_client.return_value.__aenter__.return_value
              mock_instance.get = AsyncMock(return_value=type("R", (), {
                  "text": html_content, "status_code": 200
              })())
              result = await parse_url_import("http://example.com/words")
          assert len(result.cards) >= 1
          assert result.source_type == "url"

      @pytest.mark.anyio
      async def test_url_fetch_error_raises_value_error(self):
          import httpx
          with patch("lingosips.core.imports.httpx.AsyncClient") as mock_client:
              mock_instance = mock_client.return_value.__aenter__.return_value
              mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
              with pytest.raises(ValueError, match="Could not fetch URL"):
                  await parse_url_import("http://unreachable.example.com")
  ```

- [x] **T2.2: Implement `parse_text_import()` and `parse_url_import()` in `core/imports.py`**:
  ```python
  import httpx
  from typing import Literal

  TextFormat = Literal["auto", "plain", "tsv"]

  def parse_text_import(text: str, format: TextFormat = "auto") -> ImportPreview:
      """Parse plain text or TSV into ImportPreview.

      TSV format: 'word\\ttranslation' per line (3rd+ columns ignored).
      Plain format: one word/phrase per line, no translation.
      Auto: detect TSV if any line contains a tab character.
      """
      lines = [line.strip() for line in text.splitlines() if line.strip()]
      if not lines:
          return ImportPreview(source_type="text", total_cards=0,
                               fields_present=[], fields_missing_summary={}, cards=[])

      # Auto-detect
      if format == "auto":
          format = "tsv" if any("\t" in line for line in lines) else "plain"

      cards: list[CardPreviewItem] = []
      for line in lines:
          if format == "tsv":
              parts = line.split("\t", maxsplit=2)
              target_word = parts[0].strip()
              translation = parts[1].strip() if len(parts) > 1 else None
          else:
              target_word = line
              translation = None
          if not target_word:
              continue
          missing = ["forms", "example_sentences", "audio"]
          if not translation:
              missing.insert(0, "translation")
          cards.append(CardPreviewItem(
              target_word=target_word,
              translation=translation or None,
              example_sentence=None,
              has_audio=False,
              fields_missing=missing,
              selected=True,
          ))

      fields_missing_counts = {}
      for card in cards:
          for f in card.fields_missing:
              fields_missing_counts[f] = fields_missing_counts.get(f, 0) + 1

      return ImportPreview(
          source_type="text",
          total_cards=len(cards),
          fields_present=["target_word"] + (["translation"] if format == "tsv" else []),
          fields_missing_summary=fields_missing_counts,
          cards=cards,
      )

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
      import re
      clean = re.sub(r"<[^>]+>", " ", text)  # strip HTML tags
      clean = re.sub(r"&\w+;", " ", clean)   # strip HTML entities
      # Split into lines and use parse_text_import logic
      return parse_text_import(clean, format="auto")
  ```

---

### Backend — T3: Import API endpoints — Preview [TDD — FIRST]

- [x] **T3.1: Create `tests/api/test_imports.py`** — write failing `TestImportPreview` class:
  ```python
  import io, zipfile, sqlite3, json, tempfile, os
  import pytest
  from httpx import AsyncClient

  def _make_minimal_apkg() -> bytes:
      """Minimal valid .apkg with 2 cards."""
      with tempfile.TemporaryDirectory() as tmpdir:
          db_path = os.path.join(tmpdir, "collection.anki2")
          conn = sqlite3.connect(db_path)
          model_id = 1234567890
          models = {str(model_id): {"flds": [{"name": "Front"}, {"name": "Back"}], "name": "Basic"}}
          conn.execute("CREATE TABLE col (models TEXT)")
          conn.execute("INSERT INTO col VALUES (?)", (json.dumps(models),))
          conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, flds TEXT, tags TEXT, mid INTEGER)")
          conn.execute("INSERT INTO notes (flds, tags, mid) VALUES (?, '', ?)", ("hola\x1fhello", model_id))
          conn.execute("INSERT INTO notes (flds, tags, mid) VALUES (?, '', ?)", ("agua\x1fwater", model_id))
          conn.commit(); conn.close()
          buf = io.BytesIO()
          with zipfile.ZipFile(buf, "w") as zf:
              zf.write(db_path, "collection.anki2")
          return buf.getvalue()

  class TestAnkiPreview:
      @pytest.mark.anyio
      async def test_upload_valid_apkg_returns_preview(self, client: AsyncClient) -> None:
          apkg_bytes = _make_minimal_apkg()
          response = await client.post(
              "/import/preview/anki",
              files={"file": ("test.apkg", apkg_bytes, "application/octet-stream")},
          )
          assert response.status_code == 200
          body = response.json()
          assert body["source_type"] == "anki"
          assert body["total_cards"] == 2
          assert len(body["cards"]) == 2
          assert body["cards"][0]["target_word"] == "hola"
          assert body["cards"][0]["translation"] == "hello"
          assert all(c["selected"] is True for c in body["cards"])

      @pytest.mark.anyio
      async def test_upload_invalid_file_returns_422(self, client: AsyncClient) -> None:
          response = await client.post(
              "/import/preview/anki",
              files={"file": ("bad.apkg", b"not a zip", "application/octet-stream")},
          )
          assert response.status_code == 422
          body = response.json()
          assert body["type"] == "/errors/invalid-import-file"

      @pytest.mark.anyio
      async def test_upload_empty_apkg_returns_zero_cards(self, client: AsyncClient) -> None:
          with tempfile.TemporaryDirectory() as tmpdir:
              db_path = os.path.join(tmpdir, "collection.anki2")
              conn = sqlite3.connect(db_path)
              model_id = 1
              models = {str(model_id): {"flds": [{"name": "Front"}, {"name": "Back"}], "name": "Basic"}}
              conn.execute("CREATE TABLE col (models TEXT)")
              conn.execute("INSERT INTO col VALUES (?)", (json.dumps(models),))
              conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, flds TEXT, tags TEXT, mid INTEGER)")
              conn.commit(); conn.close()
              buf = io.BytesIO()
              with zipfile.ZipFile(buf, "w") as zf:
                  zf.write(db_path, "collection.anki2")
              response = await client.post(
                  "/import/preview/anki",
                  files={"file": ("empty.apkg", buf.getvalue(), "application/octet-stream")},
              )
          assert response.status_code == 200
          assert response.json()["total_cards"] == 0

  class TestTextPreview:
      @pytest.mark.anyio
      async def test_tsv_text_returns_preview_with_translations(self, client: AsyncClient) -> None:
          response = await client.post(
              "/import/preview/text",
              json={"text": "hola\thello\nagua\twater", "format": "tsv"},
          )
          assert response.status_code == 200
          body = response.json()
          assert body["source_type"] == "text"
          assert body["total_cards"] == 2
          assert body["cards"][0]["translation"] == "hello"

      @pytest.mark.anyio
      async def test_plain_text_returns_preview_no_translation(self, client: AsyncClient) -> None:
          response = await client.post(
              "/import/preview/text",
              json={"text": "melancólico\nhola", "format": "plain"},
          )
          assert response.status_code == 200
          assert all(c["translation"] is None for c in response.json()["cards"])

      @pytest.mark.anyio
      async def test_empty_text_returns_zero_cards(self, client: AsyncClient) -> None:
          response = await client.post("/import/preview/text", json={"text": "", "format": "plain"})
          assert response.status_code == 200
          assert response.json()["total_cards"] == 0

      @pytest.mark.anyio
      async def test_missing_text_field_returns_422(self, client: AsyncClient) -> None:
          response = await client.post("/import/preview/text", json={"format": "plain"})
          assert response.status_code == 422

  class TestUrlPreview:
      @pytest.mark.anyio
      async def test_url_preview_fetches_and_returns_words(self, client: AsyncClient) -> None:
          from unittest.mock import AsyncMock, patch
          import httpx
          mock_response = type("R", (), {"text": "hola agua melancólico", "status_code": 200,
                                         "raise_for_status": lambda self: None})()
          with patch("lingosips.core.imports.httpx.AsyncClient") as mock_cls:
              mock_instance = mock_cls.return_value.__aenter__.return_value
              mock_instance.get = AsyncMock(return_value=mock_response)
              response = await client.post(
                  "/import/preview/url",
                  json={"url": "http://example.com/words"},
              )
          assert response.status_code == 200
          assert response.json()["source_type"] == "url"

      @pytest.mark.anyio
      async def test_unreachable_url_returns_422(self, client: AsyncClient) -> None:
          from unittest.mock import AsyncMock, patch
          import httpx
          with patch("lingosips.core.imports.httpx.AsyncClient") as mock_cls:
              mock_instance = mock_cls.return_value.__aenter__.return_value
              mock_instance.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
              response = await client.post(
                  "/import/preview/url",
                  json={"url": "http://unreachable.invalid"},
              )
          assert response.status_code == 422
          assert response.json()["type"] == "/errors/url-fetch-failed"
  ```

- [x] **T3.2: Create `src/lingosips/api/imports.py`** — add preview endpoints:
  ```python
  """Import pipeline API — preview and job management.

  LAYER RULE: All parsing logic lives in core/imports.py.
  This router only validates inputs, delegates, and returns responses.
  """
  from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
  from pydantic import BaseModel, field_validator
  from sqlmodel.ext.asyncio.session import AsyncSession
  from fastapi import Depends

  from lingosips.core import imports as core_imports
  from lingosips.db.session import get_session
  from lingosips.services.registry import get_llm_provider, get_speech_provider
  from lingosips.services.llm.base import AbstractLLMProvider
  from lingosips.services.speech.base import AbstractSpeechProvider
  import structlog

  router = APIRouter(prefix="/import", tags=["import"])
  logger = structlog.get_logger(__name__)

  # --- Response models ---
  class CardPreviewItemResponse(BaseModel):
      target_word: str
      translation: str | None
      example_sentence: str | None
      has_audio: bool
      fields_missing: list[str]
      selected: bool

  class ImportPreviewResponse(BaseModel):
      source_type: str
      total_cards: int
      fields_present: list[str]
      fields_missing_summary: dict[str, int]
      cards: list[CardPreviewItemResponse]

  # --- Preview endpoints ---
  @router.post("/preview/anki", response_model=ImportPreviewResponse)
  async def preview_anki(file: UploadFile = File(...)) -> ImportPreviewResponse:
      """Parse uploaded .apkg file and return preview (no cards created)."""
      file_bytes = await file.read()
      try:
          preview = core_imports.parse_apkg(file_bytes)
      except ValueError as exc:
          raise HTTPException(
              status_code=422,
              detail={"type": "/errors/invalid-import-file", "title": str(exc), "status": 422},
          )
      return ImportPreviewResponse(
          source_type=preview.source_type,
          total_cards=preview.total_cards,
          fields_present=preview.fields_present,
          fields_missing_summary=preview.fields_missing_summary,
          cards=[CardPreviewItemResponse(**vars(c)) for c in preview.cards],
      )

  class TextPreviewRequest(BaseModel):
      text: str
      format: str = "auto"  # "auto" | "plain" | "tsv"

      @field_validator("format")
      @classmethod
      def valid_format(cls, v: str) -> str:
          if v not in ("auto", "plain", "tsv"):
              raise ValueError("format must be 'auto', 'plain', or 'tsv'")
          return v

  @router.post("/preview/text", response_model=ImportPreviewResponse)
  async def preview_text(request: TextPreviewRequest) -> ImportPreviewResponse:
      """Parse plain text or TSV and return preview (no cards created)."""
      preview = core_imports.parse_text_import(request.text, format=request.format)
      return ImportPreviewResponse(**{k: v for k, v in vars(preview).items()},
                                   cards=[CardPreviewItemResponse(**vars(c)) for c in preview.cards])

  class UrlPreviewRequest(BaseModel):
      url: str

  @router.post("/preview/url", response_model=ImportPreviewResponse)
  async def preview_url(request: UrlPreviewRequest) -> ImportPreviewResponse:
      """Fetch URL and return word candidates as preview (no cards created)."""
      try:
          preview = await core_imports.parse_url_import(request.url)
      except ValueError as exc:
          raise HTTPException(
              status_code=422,
              detail={"type": "/errors/url-fetch-failed", "title": str(exc), "status": 422},
          )
      return ImportPreviewResponse(**{k: v for k, v in vars(preview).items()},
                                   cards=[CardPreviewItemResponse(**vars(c)) for c in preview.cards])
  ```

---

### Backend — T4: Import start + SSE progress endpoint [TDD — FIRST]

- [x] **T4.1: Add failing tests** — `TestImportStart` and `TestImportProgress` classes to `tests/api/test_imports.py`:
  ```python
  from lingosips.db.models import Job, Card

  class TestImportStart:
      @pytest.mark.anyio
      async def test_start_creates_job_before_enrichment(
          self, client: AsyncClient, session: AsyncSession
      ) -> None:
          from unittest.mock import patch, AsyncMock
          with patch("lingosips.core.imports.run_enrichment", new_callable=AsyncMock) as mock_enrich:
              response = await client.post("/import/start", json={
                  "source_type": "text",
                  "cards": [{"target_word": "hola", "translation": "hello"}],
                  "target_language": "es",
                  "enrich": True,
              })
          assert response.status_code == 200
          body = response.json()
          assert "job_id" in body
          assert body["card_count"] == 1
          # Verify job exists in DB immediately
          job = await session.get(Job, body["job_id"])
          assert job is not None
          assert job.job_type == "import_enrichment"
          assert job.status in ("pending", "running", "complete")

      @pytest.mark.anyio
      async def test_start_creates_card_records_immediately(
          self, client: AsyncClient, session: AsyncSession
      ) -> None:
          from unittest.mock import patch, AsyncMock
          with patch("lingosips.core.imports.run_enrichment", new_callable=AsyncMock):
              response = await client.post("/import/start", json={
                  "source_type": "text",
                  "cards": [{"target_word": "agua", "translation": "water"}],
                  "target_language": "es",
                  "enrich": False,
              })
          assert response.status_code == 200
          # Card should exist immediately (not after enrichment)
          from sqlmodel import select
          stmt = select(Card).where(Card.target_word == "agua")
          result = await session.exec(stmt)
          card = result.first()
          assert card is not None
          assert card.target_language == "es"

      @pytest.mark.anyio
      async def test_start_empty_cards_returns_422(self, client: AsyncClient) -> None:
          response = await client.post("/import/start", json={
              "source_type": "text", "cards": [], "target_language": "es", "enrich": True
          })
          assert response.status_code == 422

      @pytest.mark.anyio
      async def test_start_missing_target_language_returns_422(self, client: AsyncClient) -> None:
          response = await client.post("/import/start", json={
              "source_type": "text",
              "cards": [{"target_word": "hola"}],
              "enrich": True,
          })
          assert response.status_code == 422

  class TestImportProgress:
      @pytest.mark.anyio
      async def test_progress_sse_emits_progress_and_complete(
          self, client: AsyncClient, session: AsyncSession
      ) -> None:
          # Create a completed job directly
          from lingosips.db.models import Job
          from datetime import UTC, datetime
          job = Job(job_type="import_enrichment", status="complete",
                    progress_done=3, progress_total=3, updated_at=datetime.now(UTC))
          session.add(job); await session.commit(); await session.refresh(job)

          response = await client.get(
              f"/import/{job.id}/progress",
              headers={"Accept": "text/event-stream"},
          )
          assert response.status_code == 200
          # Should contain a complete or progress event in the body
          text = response.text
          assert "complete" in text or "progress" in text

      @pytest.mark.anyio
      async def test_progress_unknown_job_returns_404(self, client: AsyncClient) -> None:
          response = await client.get("/import/99999/progress")
          assert response.status_code == 404
          assert response.json()["type"] == "/errors/job-not-found"

      @pytest.mark.anyio
      async def test_get_job_status_unknown_returns_404(self, client: AsyncClient) -> None:
          response = await client.get("/import/99999")
          assert response.status_code == 404
          assert response.json()["type"] == "/errors/job-not-found"
  ```

- [x] **T4.2: Add `ImportStartRequest` and `run_enrichment()` to `core/imports.py`**:
  ```python
  from datetime import UTC, datetime
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
  from sqlalchemy import select as sql_select
  from lingosips.db.models import Card, Job

  class CardImportItem(BaseModel):
      target_word: str
      translation: str | None = None
      example_sentence: str | None = None

  # Used to create background task sessions (separate from request sessions)
  # Exposed here so run_enrichment can create its own async sessions
  _db_url: str | None = None  # set by app.py lifespan from db/session.py engine.url

  async def create_cards_and_job(
      cards_data: list["CardImportItem"],
      target_language: str,
      deck_id: int | None,
      session: AsyncSession,
  ) -> tuple[int, list[int]]:
      """Persist job + card stubs atomically. Returns (job_id, card_ids).

      CRITICAL: job must be committed to DB BEFORE returning (and before background task starts).
      The background task uses job_id to update progress — race condition if job not persisted first.
      """
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

      For each card: call LLM to fill missing fields, call TTS for audio, update progress.
      On any per-card failure: mark card with personal_note flag — never skip or delete the card.

      CRITICAL: always update job.status to "running" before starting loop,
      and "complete"/"failed" at end — even if all cards fail.
      """
      from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession as SAAsyncSession
      from sqlalchemy.orm import sessionmaker as sa_sessionmaker

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

          # Import providers (lazy import to avoid circular deps)
          from lingosips.services.credentials import (
              get_credential, OPENROUTER_API_KEY, OPENROUTER_MODEL
          )
          from lingosips.services.registry import get_llm_provider as get_provider_sync

          for i, card_id in enumerate(card_ids):
              async with async_session() as session:
                  card = await session.get(Card, card_id)
                  if not card:
                      unresolved += 1
                      continue
                  try:
                      # Only enrich if field is missing
                      if not card.translation:
                          # Use LLM — get provider via credentials (same logic as registry)
                          api_key = llm_api_key or get_credential(OPENROUTER_API_KEY)
                          model = llm_model or get_credential(OPENROUTER_MODEL)
                          if api_key and model:
                              from lingosips.services.llm.openrouter import OpenRouterProvider
                              provider = OpenRouterProvider(api_key=api_key, model=model)
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
                      logger.warning("import.enrichment.card_failed",
                                     card_id=card_id, error=str(exc))
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
  ```

- [x] **T4.3: Add `/import/start`, `/import/{job_id}/progress`, `/import/{job_id}` endpoints to `api/imports.py`**:
  ```python
  import asyncio
  from fastapi.responses import StreamingResponse

  class ImportStartRequest(BaseModel):
      source_type: str
      cards: list[core_imports.CardImportItem]
      target_language: str
      deck_id: int | None = None
      enrich: bool = True

      @field_validator("cards")
      @classmethod
      def cards_not_empty(cls, v):
          if not v:
              raise ValueError("cards must not be empty")
          return v

  class ImportStartResponse(BaseModel):
      job_id: int
      card_count: int

  class JobStatusResponse(BaseModel):
      job_id: int
      status: str
      progress_done: int
      progress_total: int
      current_item: str | None
      error_message: str | None

  @router.post("/start", response_model=ImportStartResponse)
  async def start_import(
      request: ImportStartRequest,
      background_tasks: BackgroundTasks,
      session: AsyncSession = Depends(get_session),
      llm: AbstractLLMProvider = Depends(get_llm_provider),
  ) -> ImportStartResponse:
      """Create cards + job, then launch enrichment as a background task."""
      from lingosips.db.session import engine  # import engine URL for background task
      job_id, card_ids = await core_imports.create_cards_and_job(
          cards_data=request.cards,
          target_language=request.target_language,
          deck_id=request.deck_id,
          session=session,
      )
      if request.enrich:
          db_url = str(engine.url)
          # Get credentials for background task (provider instance dies with request)
          from lingosips.services.credentials import get_credential, OPENROUTER_API_KEY, OPENROUTER_MODEL
          llm_api_key = get_credential(OPENROUTER_API_KEY)
          llm_model = get_credential(OPENROUTER_MODEL)
          background_tasks.add_task(
              core_imports.run_enrichment,
              job_id=job_id,
              card_ids=card_ids,
              db_engine_url=db_url,
              llm_api_key=llm_api_key,
              llm_model=llm_model,
          )
      logger.info("import.started", job_id=job_id, card_count=len(card_ids))
      return ImportStartResponse(job_id=job_id, card_count=len(card_ids))

  @router.get("/{job_id}/progress")
  async def import_progress(
      job_id: int,
      session: AsyncSession = Depends(get_session),
  ) -> StreamingResponse:
      """SSE stream of enrichment progress. Polls job table every 500ms.

      SSE envelope identical to other channels:
        event: progress\\ndata: {"done": N, "total": M, "current_item": "..."}\\n\\n
        event: complete\\ndata: {"enriched": N, "unresolved": M}\\n\\n
        event: error\\ndata: {"message": "..."}\\n\\n
      """
      # Validate job exists
      job = await session.get(Job, job_id)
      if not job:
          raise HTTPException(
              status_code=404,
              detail={"type": "/errors/job-not-found",
                      "title": f"Job {job_id} not found", "status": 404},
          )
      # Close the request session before streaming (SSE uses its own sessions)
      await session.close()

      async def event_generator():
          from lingosips.db.session import engine as db_engine
          from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
          from sqlalchemy.orm import sessionmaker as sa_sessionmaker

          async_session = sa_sessionmaker(
              db_engine, class_=SAAsyncSession, expire_on_commit=False
          )
          try:
              while True:
                  async with async_session() as poll_session:
                      current_job = await poll_session.get(Job, job_id)
                      if not current_job:
                          yield _sse_event("error", {"message": f"Job {job_id} disappeared"})
                          return

                      if current_job.status == "complete":
                          # Parse unresolved count from error_message encoding
                          unresolved = 0
                          if current_job.error_message and current_job.error_message.startswith("unresolved:"):
                              try:
                                  unresolved = int(current_job.error_message.split(":")[1])
                              except (IndexError, ValueError):
                                  pass
                          enriched = current_job.progress_total - unresolved
                          yield _sse_event("complete", {"enriched": enriched, "unresolved": unresolved})
                          return
                      elif current_job.status == "failed":
                          yield _sse_event("error", {"message": current_job.error_message or "Import failed"})
                          return
                      else:
                          yield _sse_event("progress", {
                              "done": current_job.progress_done,
                              "total": current_job.progress_total,
                              "current_item": current_job.current_item or "processing...",
                          })
                  await asyncio.sleep(0.5)  # poll every 500ms
          except asyncio.CancelledError:
              pass  # client disconnected — enrichment continues in background
          finally:
              pass  # engine managed by app lifespan

      return StreamingResponse(event_generator(), media_type="text/event-stream")

  def _sse_event(event_type: str, data: dict) -> str:
      import json
      return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

  @router.get("/{job_id}", response_model=JobStatusResponse)
  async def get_job_status(
      job_id: int,
      session: AsyncSession = Depends(get_session),
  ) -> JobStatusResponse:
      """Get current job status (for reconnect after page reload)."""
      from lingosips.db.models import Job
      job = await session.get(Job, job_id)
      if not job:
          raise HTTPException(
              status_code=404,
              detail={"type": "/errors/job-not-found",
                      "title": f"Job {job_id} not found", "status": 404},
          )
      return JobStatusResponse(
          job_id=job.id,
          status=job.status,
          progress_done=job.progress_done,
          progress_total=job.progress_total,
          current_item=job.current_item,
          error_message=job.error_message,
      )
  ```

---

### Backend — T5: Register router in app.py

- [x] **T5.1: Add import router to `src/lingosips/api/app.py`**:
  ```python
  # Add to existing imports section:
  from lingosips.api import imports as imports_router

  # Add to router registration (after cards, before practice):
  app.include_router(imports_router.router)
  ```
  **CRITICAL**: Also expose `engine` from `db/session.py` — the import background task needs `engine.url`. Verify `db/session.py` exports `engine` at module level.

- [x] **T5.2: Verify `src/lingosips/db/session.py` exports `engine`** at module level (not inside a function). If it's only inside a lifespan handler, restructure to expose it:
  ```python
  # db/session.py — engine must be module-level for background tasks
  from pathlib import Path
  from sqlalchemy.ext.asyncio import create_async_engine
  from sqlmodel.ext.asyncio.session import AsyncSession
  from sqlalchemy.orm import sessionmaker

  DB_PATH = Path.home() / ".lingosips" / "lingosips.db"
  DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

  engine = create_async_engine(DATABASE_URL, echo=False)  # module-level — importable by background tasks

  async def get_session():
      async with AsyncSession(engine) as session:
          yield session
  ```

---

### Frontend — T6: Write failing tests for ImportPage [TDD — FIRST]

- [x] **T6.1: Create `frontend/src/features/import/ImportPage.test.tsx`** — all tests failing before T7:
  ```typescript
  import { render, screen, fireEvent, waitFor } from "@testing-library/react"
  import { describe, it, expect, vi, beforeEach } from "vitest"
  import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
  import { post } from "@/lib/client"
  import { ImportPage } from "./ImportPage"

  vi.mock("@/lib/client")
  vi.mock("@/lib/stores/useAppStore")

  // Required test cases (state machine coverage):
  // - "idle" state: renders 3 source tabs (Anki, Text, URL)
  // - "idle" state: file input accepts only .apkg files (accept=".apkg")
  // - "idle" state: text input renders textarea + format selector
  // - "idle" state: URL input renders URL text input
  // - "parsing" state: shows skeleton while POST /import/preview/* is pending
  // - "preview" state: shows card count + fields present/missing summary
  // - "preview" state: cards listed with checkboxes, all pre-selected
  // - "preview" state: unselecting a card removes it from import count
  // - "preview" state: "Import & Enrich" button shows correct count
  // - "enriching" state: shows progress bar after POST /import/start
  // - "complete" state: shows summary after SSE complete event
  // - "error" state: shows specific error message (not generic "Something went wrong")
  // - keyboard: Tab navigates between source tabs; Enter selects
  // - accessibility: file drop zone has aria-label="Upload Anki .apkg file"
  ```

- [x] **T6.2: Create `frontend/src/features/import/useImportProgress.test.ts`**:
  ```typescript
  // Required test cases:
  // - hook returns {done: 0, total: 0, status: "idle"} when jobId is null
  // - hook sets status="running" and updates done/total on progress SSE events
  // - hook sets status="complete" on complete SSE event
  // - hook sets status="error" on error SSE event
  // - hook cleans up EventSource on unmount
  ```

---

### Frontend — T7: Implement Import feature components

- [x] **T7.1: Create `frontend/src/features/import/ImportPage.tsx`**:
  ```typescript
  // State machine — NEVER boolean flags (project rule)
  type ImportState =
    | "idle"       // initial — show source selection tabs
    | "parsing"    // POST /import/preview/* in flight — show skeleton
    | "preview"    // preview response received — show card list with checkboxes
    | "enriching"  // POST /import/start submitted — show progress
    | "complete"   // SSE complete received — show summary
    | "error"      // any step failed — show specific error

  // Source type state
  type ImportSource = "anki" | "text" | "url"

  // Key implementation rules:
  // - File drop zone: input[type=file][accept=".apkg"] + drag events (dragover, drop)
  // - Text source: <textarea> for paste + <input type=file accept=".txt,.tsv"> for file upload
  // - URL source: <input type=url> + optional URL validation before preview
  // - Preview: card list with <ul> + <li> each containing <input type=checkbox>
  // - Import button: "Import & Enrich N cards" where N = selected.length
  // - After POST /import/start: set useAppStore.setActiveImportJobId(jobId)
  //   and transition to "enriching" state
  // - useImportProgress hook: pass jobId from /import/start response
  // - On SSE "complete": addNotification + transition to "complete"
  // - On SSE "error": transition to "error" with specific message
  ```

- [x] **T7.2: Create `frontend/src/features/import/AnkiImportPanel.tsx`**:
  ```typescript
  // Drag-and-drop .apkg upload panel
  // State: "idle" | "dragging" | "uploading" (file selected, POST in flight)
  // - Drop zone: accepts .apkg files only (validate extension before upload)
  // - Accessibility: aria-label="Upload Anki .apkg file", role="button", keyboard Enter/Space to open file dialog
  // - On file drop/select: call onFileSelected(file: File) callback
  // - Show file name + size after selection before preview
  // - Uses post() from lib/client with FormData for multipart upload:
  //     const formData = new FormData()
  //     formData.append("file", file)
  //     const preview = await post<ImportPreviewResponse>("/import/preview/anki", formData)
  //   IMPORTANT: do NOT set Content-Type header — browser sets multipart boundary automatically
  ```

- [x] **T7.3: Create `frontend/src/features/import/TextImportPanel.tsx`**:
  ```typescript
  // Text/TSV paste or file upload panel
  // - <textarea> for direct paste (placeholder: "Paste words one per line, or word\ttranslation TSV")
  // - File picker: input[type=file][accept=".txt,.tsv,.csv"]
  // - Format selector: <select> with "auto", "plain", "tsv" options
  // - Character counter: show text.length to help user know input size
  ```

- [x] **T7.4: Create `frontend/src/features/import/UrlImportPanel.tsx`**:
  ```typescript
  // URL input panel
  // - <input type="url"> for URL entry
  // - "Preview words" button triggers POST /import/preview/url
  // - Show loading skeleton while fetching
  // - On 422 (URL fetch failed): show specific error message from response body
  ```

- [x] **T7.5: Create `frontend/src/features/import/ImportPreview.tsx`**:
  ```typescript
  // Shared preview component used by all three source types
  // Props: { preview: ImportPreviewResponse, onConfirm: (selectedCards) => void, onBack: () => void }
  //
  // Display:
  // - Summary header: "X cards found · Fields present: target_word, translation · Missing: audio (X), forms (X)"
  // - Card list: <ul role="list"> with <li> per card
  //   - <input type=checkbox> checked={selected} onChange={toggleCard}
  //   - target_word (bold) + translation (if present)
  //   - "Missing: translation, audio" badge on each card missing fields
  // - "Select all" / "Deselect all" toggle button
  // - "Import & Enrich N cards" primary button (disabled if 0 selected)
  // - "Back" secondary button
  //
  // Accessibility:
  // - <fieldset><legend>Select cards to import</legend>
  // - Each checkbox: aria-label="{target_word} — {fields_missing.join(', ')}"
  ```

---

### Frontend — T8: Implement useImportProgress hook

- [x] **T8.1: Create `frontend/src/features/import/useImportProgress.ts`**:
  ```typescript
  // SSE consumer for GET /import/{job_id}/progress
  // IMPORTANT: this is a GET SSE stream — NOT streamPost (which is for POST /cards/stream)
  // Use native EventSource API (browser-native, no polyfill needed for modern browsers)

  import { useEffect, useRef } from "react"
  import { useAppStore } from "@/lib/stores/useAppStore"

  export interface ImportProgress {
    done: number
    total: number
    currentItem: string | null
    status: "idle" | "running" | "complete" | "error"
    enriched: number
    unresolved: number
    errorMessage: string | null
  }

  export function useImportProgress(jobId: number | null): ImportProgress {
    const setImportProgress = useAppStore((s) => s.setImportProgress)
    const importProgress = useAppStore((s) => s.importProgress)
    const esRef = useRef<EventSource | null>(null)

    useEffect(() => {
      if (!jobId) return

      // Close any existing connection
      esRef.current?.close()

      const es = new EventSource(`/import/${jobId}/progress`)
      esRef.current = es

      es.addEventListener("progress", (e) => {
        const data = JSON.parse(e.data)
        setImportProgress({
          done: data.done,
          total: data.total,
          currentItem: data.current_item,
          status: "running",
          enriched: 0, unresolved: 0, errorMessage: null,
        })
      })

      es.addEventListener("complete", (e) => {
        const data = JSON.parse(e.data)
        setImportProgress({
          done: data.enriched + data.unresolved,
          total: data.enriched + data.unresolved,
          currentItem: null,
          status: "complete",
          enriched: data.enriched,
          unresolved: data.unresolved,
          errorMessage: null,
        })
        // Fire completion notification
        useAppStore.getState().addNotification({
          type: "success",
          message: `${data.enriched} cards enriched · ${data.unresolved} fields could not be resolved`,
        })
        useAppStore.getState().setActiveImportJobId(null)
        es.close()
        esRef.current = null
      })

      es.addEventListener("error", (e) => {
        // SSE 'error' event can mean connection dropped OR our custom error event
        const errorEvent = e as MessageEvent
        if (errorEvent.data) {
          const data = JSON.parse(errorEvent.data)
          setImportProgress({ ...importProgress, status: "error", errorMessage: data.message })
        }
        es.close()
        esRef.current = null
      })

      return () => {
        es.close()
        esRef.current = null
      }
    }, [jobId])

    return importProgress
  }
  ```

---

### Frontend — T9: Update useAppStore + Sidebar progress ring

- [x] **T9.1: Extend `frontend/src/lib/stores/useAppStore.ts`** — add import job tracking:
  ```typescript
  // Add to AppStore interface:
  activeImportJobId: number | null
  importProgress: ImportProgress  // from useImportProgress.ts types

  // Add actions:
  setActiveImportJobId: (jobId: number | null) => void
  setImportProgress: (progress: ImportProgress) => void

  // Initial state:
  activeImportJobId: null,
  importProgress: { done: 0, total: 0, currentItem: null, status: "idle",
                    enriched: 0, unresolved: 0, errorMessage: null },
  ```

- [x] **T9.2: Update `frontend/src/components/layout/IconSidebar.tsx`** — add progress ring on Import icon:
  ```typescript
  // Import: useAppStore to read importProgress.status and done/total ratio
  // When importProgress.status === "running":
  //   - Wrap Import icon in a <div> with a CSS-based progress ring (SVG circle stroke-dashoffset)
  //   - aria-label={`Import in progress — ${done} of ${total}`}
  // When status === "idle" or "complete": no ring (or completed ring briefly)
  //
  // Implementation: simple SVG ring using Tailwind + inline style for dashoffset
  // DO NOT add a new npm dependency for this — use SVG directly
  ```

- [x] **T9.3: Update `frontend/src/components/layout/BottomNav.tsx`** — add progress indicator:
  ```typescript
  // Same logic: show small progress badge on Import nav item when activeImportJobId is set
  // Badge: small amber dot with aria-label="Import in progress"
  ```

- [x] **T9.4: Replace stub `frontend/src/routes/import.tsx`** with real implementation:
  ```typescript
  import { createFileRoute } from "@tanstack/react-router"
  import { ImportPage } from "@/features/import"

  export const Route = createFileRoute("/import")({
    component: ImportPage,
  })
  ```

- [x] **T9.5: Create `frontend/src/features/import/index.ts`**:
  ```typescript
  export { ImportPage } from "./ImportPage"
  ```

---

### Frontend — T10: E2E tests

- [x] **T10.1: Create/update `frontend/e2e/journeys/import-and-enrichment.spec.ts`**:
  ```typescript
  import { test, expect } from "@playwright/test"
  import path from "path"

  // Helper: create test .apkg file or use fixture
  test.describe("Import & AI Enrichment journey — Story 2.4", () => {
    test.beforeEach(async ({ page }) => {
      // Complete onboarding via API (reuse helper from other specs)
      await page.request.post("http://127.0.0.1:7842/settings", {
        data: { onboarding_completed: true, native_language: "en", active_target_language: "es" },
      })
      await page.goto("/import")
    })

    test("import page renders three source tabs", async ({ page }) => {
      await expect(page.getByRole("tab", { name: /Anki/i })).toBeVisible()
      await expect(page.getByRole("tab", { name: /Text/i })).toBeVisible()
      await expect(page.getByRole("tab", { name: /URL/i })).toBeVisible()
    })

    test("text TSV import: preview → confirm → job created", async ({ page }) => {
      await page.getByRole("tab", { name: /Text/i }).click()
      await page.getByRole("textbox").fill("hola\thello\nagua\twater")
      await page.getByRole("button", { name: /Preview/i }).click()
      await expect(page.getByText("2 cards found")).toBeVisible({ timeout: 5000 })
      await expect(page.getByText("hola")).toBeVisible()
      await page.getByRole("button", { name: /Import.*2 card/i }).click()
      // Job created — progress UI appears
      await expect(
        page.getByText(/enriching|cards imported|complete/i)
      ).toBeVisible({ timeout: 10000 })
    })

    test("text plain import: deselect card reduces count", async ({ page }) => {
      await page.getByRole("tab", { name: /Text/i }).click()
      await page.getByRole("textbox").fill("hola\nagua\nmelancólico")
      await page.getByRole("button", { name: /Preview/i }).click()
      await expect(page.getByText("3 cards found")).toBeVisible({ timeout: 5000 })
      // Deselect first card
      const checkboxes = page.getByRole("checkbox")
      await checkboxes.first().uncheck()
      await expect(page.getByRole("button", { name: /Import.*2 card/i })).toBeVisible()
    })

    test("invalid text gives empty preview gracefully", async ({ page }) => {
      await page.getByRole("tab", { name: /Text/i }).click()
      await page.getByRole("textbox").fill("   \n   ")
      await page.getByRole("button", { name: /Preview/i }).click()
      await expect(page.getByText(/0 cards|No words found/i)).toBeVisible({ timeout: 5000 })
    })

    test("navigate away during enrichment continues job in background", async ({ page }) => {
      // Start import
      await page.getByRole("tab", { name: /Text/i }).click()
      await page.getByRole("textbox").fill("hola\nhello\nwater")
      await page.getByRole("button", { name: /Preview/i }).click()
      await expect(page.getByText(/cards found/i)).toBeVisible({ timeout: 5000 })
      await page.getByRole("button", { name: /Import/i }).click()
      // Navigate away immediately
      await page.goto("/")
      // Import icon should show progress ring
      await expect(
        page.locator("[aria-label*='Import in progress']")
      ).toBeVisible({ timeout: 5000 })
      // Wait for completion toast
      await expect(
        page.getByText(/cards enriched/i)
      ).toBeVisible({ timeout: 30000 })
    })

    test("keyboard navigation: Tab moves between source tabs", async ({ page }) => {
      await page.keyboard.press("Tab")
      await expect(page.getByRole("tab", { name: /Anki/i })).toBeFocused()
    })
  })
  ```

---

### Backend — T11: Regenerate api.d.ts and verify

- [x] **T11.1: Run `npx openapi-typescript http://localhost:7842/openapi.json -o src/lib/api.d.ts`** after all backend changes are complete
- [x] **T11.2: Run full test suite**: `uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90 && npm run test && npx playwright test`

---

## Dev Notes

### §BackendChangeSummary — Which Files Change and Why

| File | Change Type | Why |
|---|---|---|
| `src/lingosips/api/imports.py` | **NEW** | Import preview + start + SSE progress endpoints |
| `src/lingosips/core/imports.py` | **NEW** | All parsing logic: parse_apkg, parse_text_import, parse_url_import, run_enrichment |
| `src/lingosips/api/app.py` | **UPDATE** | Register `imports_router` |
| `src/lingosips/db/session.py` | **VERIFY** | Ensure `engine` exported at module level (needed by background task) |
| `tests/api/test_imports.py` | **NEW** | TDD tests for all import endpoints |
| `tests/core/test_imports.py` | **NEW** | TDD tests for parsing logic |

**DO NOT modify:**
- `src/lingosips/db/models.py` — `Job` table already has all needed columns (`job_type`, `status`, `progress_done`, `progress_total`, `current_item`, `error_message`)
- `src/lingosips/services/registry.py` — no new providers needed for this story
- `frontend/src/lib/client.ts` — `get()`, `post()` already exist; EventSource used directly in hook (not through client.ts)
- `frontend/src/features/cards/`, `frontend/src/features/decks/` — no changes

---

### §AnkiParsingDeepDive — How .apkg Files Work

**CRITICAL**: `genanki` is a **write-only** library. Do NOT use it for reading .apkg files. It does not expose parsing APIs.

An `.apkg` file is a **ZIP archive** containing:
```
myDeck.apkg (zip)
├── collection.anki2   ← SQLite database (MAIN DATA)
├── collection.anki21  ← optional newer format (ignore if present, fall back to .anki2)
├── media              ← JSON mapping of filename → original name
└── 0, 1, 2, ...       ← binary audio/image files (skip in this story)
```

**SQLite schema in `collection.anki2`:**
```sql
-- notes: one row per card
CREATE TABLE notes (
    id    INTEGER PRIMARY KEY,  -- note ID (timestamp)
    guid  TEXT NOT NULL,        -- globally unique ID
    mid   INTEGER NOT NULL,     -- model ID (FK to col.models)
    flds  TEXT NOT NULL,        -- fields separated by \x1f (ASCII 31)
    tags  TEXT NOT NULL,        -- space-separated tags
    ...
);

-- col: single row, JSON configuration
CREATE TABLE col (
    id     INTEGER PRIMARY KEY,
    models TEXT NOT NULL   -- JSON: {modelId: {flds: [{name: "Front"}, {name: "Back"}]}}
);
```

**Field extraction pattern:**
```python
# From notes.flds, fields are \x1f separated (unit separator, not tab!)
fields = note["flds"].split("\x1f")  # ← \x1f, NOT \t

# From col.models, get field names:
models = json.loads(col_row["models"])  # {"1234567890": {"flds": [{"name": "Front"}, ...], ...}}
field_names = [f["name"] for f in models[str(note["mid"])]["flds"]]
```

**Common Anki field name patterns** (user decks vary — try multiple):
- Front/Back (Basic model)
- Word/Definition (vocabulary decks)  
- Expression/Meaning (Japanese decks)
- Always fall back to index 0/1 if names don't match known patterns.

**Do not import audio** in this story — audio files in .apkg require matching to card IDs via the `media` JSON index, which adds significant complexity. Cards import with `audio_url=None`; enrichment can call TTS later.

---

### §BackgroundTaskPattern — DB Sessions in Background Tasks

**FastAPI dependency injection does NOT work in background tasks** — the request context is gone by the time the task runs. The background task must create its own DB sessions.

```python
# WRONG — session from Depends() is closed when request ends
async def run_enrichment(session: AsyncSession = Depends(get_session)):
    # session is already closed here ❌

# CORRECT — create own engine/session in background task
async def run_enrichment(job_id: int, card_ids: list[int], db_engine_url: str):
    engine = create_async_engine(db_engine_url)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    async with async_session() as session:
        job = await session.get(Job, job_id)  # ✅
    await engine.dispose()  # always dispose in finally block
```

**Why pass `db_engine_url` as string, not the engine object?**
SQLAlchemy engine objects contain thread-local state that can cause issues when passed across async context boundaries. Passing the URL string and creating a fresh engine in the background task is the safe pattern.

**Job persistence protocol (non-negotiable):**
```python
# CORRECT order in POST /import/start handler:
job_id, card_ids = await create_cards_and_job(...)  # 1. persist to DB
await session.commit()                               # 2. commit (not just flush)
background_tasks.add_task(run_enrichment, job_id=job_id, ...)  # 3. THEN launch
return ImportStartResponse(job_id=job_id, ...)       # 4. return to frontend

# WRONG — launching task before commit:
background_tasks.add_task(run_enrichment, ...)  # ❌ job may not exist in DB yet
job_id, _ = await create_cards_and_job(...)
```

---

### §SSEProgressPattern — GET SSE vs POST SSE

This story has **two different SSE channels** in the project:
- `POST /cards/stream` → **POST SSE** — existing, consumed via `streamPost()` in `lib/client.ts`
- `GET /import/{job_id}/progress` → **GET SSE** — new, consumed via native `EventSource`

**Why different consumption patterns:**

| Channel | Method | Why | Frontend consumer |
|---|---|---|---|
| `/cards/stream` | POST | Sends request body (word to create) | `streamPost()` in client.ts |
| `/import/{job_id}/progress` | GET | No body; job_id in URL | `EventSource` API |

`EventSource` only supports GET requests — this is by design for progress polling.

```typescript
// CORRECT — use EventSource for GET SSE
const es = new EventSource(`/import/${jobId}/progress`)
es.addEventListener("progress", handler)
es.addEventListener("complete", handler)
// Don't use 'message' event — use named events (matching SSE 'event:' field)

// WRONG — streamPost is POST-only, won't work here
const stream = streamPost("/import/123/progress", {})  // ❌
```

**SSE envelope** (identical to other channels per project spec):
```
event: progress
data: {"done": 23, "total": 400, "current_item": "enriching 'melancólico'..."}

event: complete
data: {"enriched": 395, "unresolved": 5}

event: error
data: {"message": "Import failed: LLM timeout"}
```

**Client disconnection safety:** The `except asyncio.CancelledError: pass` in the event generator handles client disconnection gracefully. Enrichment continues in the background regardless — the `BackgroundTasks` task is independent of the SSE connection.

---

### §FrontendStatePattern — ImportPage State Machine

```typescript
// CORRECT — enum-driven state (project requirement)
type ImportState = "idle" | "parsing" | "preview" | "enriching" | "complete" | "error"

// WRONG — boolean flags
const [isParsing, setIsParsing] = useState(false)
const [hasPreview, setHasPreview] = useState(false)  // ❌
```

**State transitions:**
```
idle → parsing    (on Preview button click)
parsing → preview  (on POST /import/preview/* success)
parsing → error    (on POST /import/preview/* failure)
preview → enriching (on "Import & Enrich" click + POST /import/start success)
enriching → complete (on SSE "complete" event)
enriching → error   (on SSE "error" event)
complete → idle    (on "Import more" button)
error → idle       (on "Try again" button)
```

**Skeleton in "parsing" state** — never a spinner:
```tsx
// CORRECT
{state === "parsing" && <Skeleton className="h-48 w-full" />}

// WRONG
{isParsing && <Spinner />}  // ❌ project bans undifferentiated spinners
```

---

### §MultipartUploadPattern — Anki File Upload

`POST /import/preview/anki` uses `UploadFile` (multipart form data), not JSON. The frontend must use `FormData`, not `post()` JSON:

```typescript
// CORRECT — multipart FormData for file upload
const formData = new FormData()
formData.append("file", selectedFile)
// DO NOT set Content-Type header — browser sets multipart boundary automatically
const response = await fetch("/import/preview/anki", {
  method: "POST",
  body: formData,
  // NO Content-Type header here
})
const preview = await response.json()

// WRONG — post() helper sends JSON with Content-Type: application/json
const preview = await post("/import/preview/anki", selectedFile)  // ❌
```

Alternatively add a `postForm()` helper to `lib/client.ts` that uses FormData. Either way is acceptable, but do NOT reuse `post()` for file uploads.

---

### §UnresolvedCardsPattern — Never Drop, Always Flag

**Critical business rule from AC7**: Cards with enrichment failures must be FLAGGED, never deleted or silently dropped.

```python
# CORRECT — flag with personal_note
except Exception as exc:
    card.personal_note = "[Import: enrichment incomplete — please review]"
    unresolved += 1

# WRONG — skip the card
except Exception:
    continue  # ❌ card disappears from user's collection
```

The `unresolved` count feeds into the completion toast:
```
"395 cards enriched · 5 fields could not be resolved"
```
This matches the "honest status messaging" UX requirement (UX-DR13).

---

### §PreviousStoryLearnings — From Stories 2.2 and 2.3

1. **Ruff E501 (line > 100 chars)**: Long `raise HTTPException(...)` calls in `api/imports.py`. Spread across lines. Run `ruff check --fix` before commit.

2. **Ruff I001 (import sort)**: New `api/imports.py` gains many imports. Run `ruff check --fix` on the file.

3. **`model_fields_set` not needed here** — ImportStartRequest uses explicit `None`-is-invalid semantics, so standard `if field is not None` checks are correct (unlike PATCH endpoints where `None` = explicit clear).

4. **`app.dependency_overrides.pop()` teardown**: Use safe-pop in test fixtures, not `.clear()`.

5. **`await screen.findByText()`** not `screen.getByText()` for async TanStack Query content.

6. **SPA middleware already handles `/import`**: `api/app.py` SPA fallback already covers the `/import` route. No change needed to SPA middleware.

7. **`JSON.parse()` guard**: `useImportProgress` parses `e.data` — wrap in `try/catch`:
   ```typescript
   es.addEventListener("progress", (e) => {
     try {
       const data = JSON.parse(e.data)
       setImportProgress(...)
     } catch { /* malformed event — ignore */ }
   })
   ```

8. **IPv6 / localhost** (from 2.3 debug log): Playwright config uses `127.0.0.1` not `localhost` to avoid `::1` → `127.0.0.1` mismatch.

9. **Test server isolation**: E2E tests add cards to the real test DB. Import tests should use unique target_word values to avoid interfering with other test suites.

10. **`genanki` confusion**: `genanki` is listed in `pyproject.toml` as a dependency (for Story 2.5 export). This story does NOT use it for reading — use `zipfile` + `sqlite3` only.

---

### §SessionClosingPattern — SSE Streaming with Depends(get_session)

The `/import/{job_id}/progress` endpoint uses `Depends(get_session)` for the initial job lookup, then creates its own sessions for polling. The `await session.close()` call after the lookup is important:

```python
@router.get("/{job_id}/progress")
async def import_progress(job_id: int, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)  # use injected session for initial check
    if not job:
        raise HTTPException(404, ...)
    await session.close()  # ← close before returning StreamingResponse
    # generator creates its own sessions via async_session factory
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Without `await session.close()`, the injected session stays open for the duration of the SSE stream, blocking connection pool slots.

---

### Project Structure Notes

**New files:**
```
src/lingosips/api/imports.py            ← NEW — preview, start, progress endpoints
src/lingosips/core/imports.py           ← NEW — parse_apkg, parse_text_import, parse_url_import, run_enrichment
tests/api/test_imports.py               ← NEW (TDD — written first)
tests/core/test_imports.py              ← NEW (TDD — written first)
frontend/src/features/import/
├── ImportPage.tsx                      ← NEW
├── ImportPage.test.tsx                 ← NEW (TDD — written first)
├── AnkiImportPanel.tsx                 ← NEW
├── TextImportPanel.tsx                 ← NEW
├── UrlImportPanel.tsx                  ← NEW
├── ImportPreview.tsx                   ← NEW
├── useImportProgress.ts                ← NEW
├── useImportProgress.test.ts           ← NEW
└── index.ts                            ← NEW
```

**Modified files:**
```
src/lingosips/api/app.py                ← add: from lingosips.api import imports; app.include_router(imports.router)
src/lingosips/db/session.py             ← verify engine exported at module level
frontend/src/routes/import.tsx          ← replace stub with ImportPage import
frontend/src/components/layout/IconSidebar.tsx  ← add progress ring on Import icon
frontend/src/components/layout/BottomNav.tsx    ← add progress badge on Import item
frontend/src/lib/stores/useAppStore.ts  ← add activeImportJobId + importProgress state
frontend/src/lib/api.d.ts               ← REGENERATED after backend changes
```

**DO NOT modify:**
```
src/lingosips/db/models.py              — Job table already complete (job_type, status, progress_done, etc.)
src/lingosips/services/registry.py     — no new providers
src/lingosips/services/credentials.py  — no new credential keys
frontend/src/lib/client.ts             — post(), get() already exist; EventSource used directly
frontend/src/features/cards/           — no changes
frontend/src/features/decks/           — no changes
frontend/src/features/settings/        — no changes
```

### References

- Story 2.4 acceptance criteria: [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.4`]
- UX-DR15 (import UI patterns): [Source: `_bmad-output/planning-artifacts/epics.md#UX Design Requirements`]
- UX Journey 4 (Import & AI Enrichment): [Source: `_bmad-output/planning-artifacts/ux-design-specification.md#Journey 4`]
- FR13–FR15 (import pipeline): [Source: `_bmad-output/planning-artifacts/epics.md#Functional Requirements`]
- NFR6 (background enrichment, non-blocking): [Source: `_bmad-output/planning-artifacts/epics.md#NonFunctional Requirements`]
- `Job` SQLModel table (all columns): [Source: `src/lingosips/db/models.py:79`]
- `Card` SQLModel table (target_word, translation, target_language, deck_id, etc.): [Source: `src/lingosips/db/models.py:20`]
- SSE event envelope spec (event_type + json_payload): [Source: `_bmad-output/project-context.md#API Design Rules`]
- Three SSE channels including `/import/{job_id}/progress`: [Source: `_bmad-output/project-context.md#API Design Rules`]
- Background job lifecycle (persist before async work): [Source: `_bmad-output/project-context.md#Background jobs`]
- `_sse_event()` helper pattern: [Source: `src/lingosips/core/cards.py`]
- `get_session` dependency: [Source: `src/lingosips/db/session.py`]
- Router registration pattern: [Source: `src/lingosips/api/app.py`]
- `create_card_stream()` background enrichment pattern: [Source: `src/lingosips/core/cards.py`]
- `streamPost()` (POST SSE only — NOT for GET SSE): [Source: `frontend/src/lib/client.ts`]
- `useAppStore.addNotification()` + error flow: [Source: `_bmad-output/project-context.md#Error flow pattern`]
- `useAppStore` (existing state + actions): [Source: `frontend/src/lib/stores/useAppStore.ts`]
- State machine enum-driven (never boolean flags): [Source: `_bmad-output/project-context.md#Component state machines`]
- RFC 7807 error format: [Source: `_bmad-output/project-context.md#API Design Rules`]
- Layer architecture — router delegates to core: [Source: `_bmad-output/project-context.md#Layer Architecture & Boundaries`]
- Feature isolation — import in `src/features/import/`, never cross-import: [Source: `_bmad-output/project-context.md#Feature isolation`]
- TDD mandatory: [Source: `_bmad-output/project-context.md#Testing Rules`]
- 90% coverage CI gate: [Source: `_bmad-output/project-context.md#CI gates`]
- Playwright against real backend (127.0.0.1:7842): [Source: `_bmad-output/project-context.md#E2E`]
- Skeleton loading (never spinners): [Source: `_bmad-output/project-context.md#Loading states`]
- `httpx` async HTTP client: [Source: `_bmad-output/project-context.md#Technology Stack`]
- `genanki` dep (write-only — NOT for parsing): [Source: `_bmad-output/planning-artifacts/epics.md#Additional Requirements`]
- `import.tsx` stub (replace entirely): [Source: `frontend/src/routes/import.tsx`]
- `IconSidebar.tsx` (add progress ring): [Source: `frontend/src/components/layout/IconSidebar.tsx`]
- `BottomNav.tsx` (add progress badge): [Source: `frontend/src/components/layout/BottomNav.tsx`]
- Existing router registration order: [Source: `src/lingosips/api/app.py`]

---

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 / claude-sonnet-4-5

### Debug Log References

1. **Coverage gap: lines 166-179 `api/imports.py` uncovered** — Resolved by adding `concurrency = ["greenlet", "thread"]` to `[tool.coverage.run]` in `pyproject.toml`. SQLAlchemy async uses greenlet for context switching; without this, pytest-cov lost tracking after `await session.commit()` calls.

2. **Line 196 dead code in `parse_text_import`** — The original `lines = [line.strip() for line in text.splitlines() if line.strip()]` pre-stripped all lines, making the TSV empty-first-column `continue` unreachable. Fixed by separating filter from strip: `lines = [line for line in ... if line.strip()]` with explicit `line.strip()` in the plain-text branch.

3. **SSE test isolation (`Job disappeared` error)** — `event_generator()` created its own DB sessions from the file-based `db_engine`, but test data was only in the in-memory test session. Resolved by adding a terminal-state fast path in `import_progress`: if job is already `complete`/`failed`, return a single-shot generator without polling.

4. **`CardImportItem` type compatibility** — Changed from `@dataclass` to `pydantic.BaseModel` so it can be used as a field type in `ImportStartRequest(BaseModel)` with proper JSON deserialization.

### Completion Notes List

- All 21 TDD tests in `tests/core/test_imports.py` pass (including 5 new `TestRunEnrichment` tests).
- All 22 TDD tests in `tests/api/test_imports.py` pass.
- All 192 frontend Vitest tests pass.
- Backend coverage: **93.17%** (gate: 90%) — cleared.
- `parse_apkg`: uses `zipfile` + `sqlite3` (not genanki which is write-only); handles Front/Back variants + fallback to raw_fields[0/1].
- `run_enrichment`: creates own DB sessions from engine URL string; flags failed cards with `personal_note` instead of dropping them; stores unresolved count in `error_message` as `"unresolved:N"`.
- SSE endpoint: returns single-shot terminal generator for already-complete/failed jobs (avoids test isolation issues and is more efficient in production).
- Frontend state machine: `"idle" | "parsing" | "preview" | "enriching" | "complete" | "error"` — no boolean flags.
- `useImportProgress` hook uses native `EventSource` for GET SSE; cleanup on unmount.
- Progress ring in `IconSidebar` and amber dot badge in `BottomNav` read from `useAppStore.importProgress`.
- E2E tests written in `frontend/e2e/journeys/import-and-enrichment.spec.ts`.

### File List

**New files:**
- `src/lingosips/core/imports.py`
- `src/lingosips/api/imports.py`
- `tests/core/test_imports.py`
- `tests/api/test_imports.py`
- `frontend/src/features/import/ImportPage.tsx`
- `frontend/src/features/import/ImportPage.test.tsx`
- `frontend/src/features/import/AnkiImportPanel.tsx`
- `frontend/src/features/import/TextImportPanel.tsx`
- `frontend/src/features/import/UrlImportPanel.tsx`
- `frontend/src/features/import/ImportPreview.tsx`
- `frontend/src/features/import/useImportProgress.ts`
- `frontend/src/features/import/useImportProgress.test.ts`
- `frontend/src/features/import/index.ts`
- `frontend/e2e/journeys/import-and-enrichment.spec.ts`

**Modified files:**
- `src/lingosips/api/app.py` — added imports router
- `pyproject.toml` — added `concurrency = ["greenlet", "thread"]` to coverage config
- `frontend/src/routes/import.tsx` — replaced stub with real ImportPage
- `frontend/src/components/layout/IconSidebar.tsx` — added progress ring
- `frontend/src/components/layout/BottomNav.tsx` — added progress badge
- `frontend/src/lib/stores/useAppStore.ts` — added importProgress + activeImportJobId state
- `frontend/src/lib/api.d.ts` — regenerated from OpenAPI

### Change Log

- 2026-05-01: Story implemented — all 22 backend and 21 core TDD tests pass; 93.17% backend coverage; 192 frontend tests pass. Greenlet concurrency fix for coverage tracking. TSV empty-column dead-code fix.
