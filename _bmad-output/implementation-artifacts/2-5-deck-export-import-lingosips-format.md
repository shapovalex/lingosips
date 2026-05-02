# Story 2.5: Deck Export & Import (.lingosips Format)

Status: done

## Story

As a user,
I want to export any deck to a shareable `.lingosips` file and import a `.lingosips` file from another user,
so that I can share curated vocabulary decks with others.

## Acceptance Criteria

1. **Given** I am on a deck detail page
   **When** I click "Export deck"
   **Then** a `.lingosips` file is downloaded — a ZIP containing `deck.json` (all card metadata + FSRS state) and `audio/` folder (pronunciation audio files)
   **And** the file contains human-readable JSON inside the ZIP

2. **Given** I open Import and choose a `.lingosips` file
   **When** it is parsed
   **Then** a preview shows: deck name, card count, target language, and up to 5 sample cards

3. **Given** I confirm the import
   **When** it completes
   **Then** all cards are added to a new deck with their FSRS state and audio intact
   **And** the deck appears in DeckGrid immediately (TanStack Query cache invalidated for `["decks"]`)

4. **Given** the `.lingosips` file is malformed or missing required fields
   **When** I try to import it
   **Then** a specific RFC 7807 error message describes what is invalid (not a generic "something went wrong")

5. **Given** a `.lingosips` file contains audio files
   **When** it is imported
   **Then** audio files are stored at `~/.lingosips/audio/{new_card_id}.wav` and `card.audio_url` is set to `/cards/{new_card_id}/audio`

6. **Given** the deck name in the `.lingosips` file already exists for the same target language
   **When** I try to import it
   **Then** `409 Conflict` with RFC 7807 body is returned and the user sees a specific error

API tests: export produces valid ZIP with correct structure; import from valid file succeeds; 422 on malformed ZIP with field-level error detail; 422 on missing `deck.json`; 409 on duplicate deck name.

## Tasks / Subtasks

- [x] T1: Add `GET /decks/{deck_id}` endpoint (AC: deck detail page prerequisite)
  - [x] T1.1: Write failing test `TestGetDeck` in `tests/api/test_decks.py` (success + 404)
  - [x] T1.2: Add `@router.get("/{deck_id}", response_model=DeckResponse)` to `api/decks.py` — delegate to existing `core_decks.get_deck()`
  - [x] T1.3: Confirm tests pass

- [x] T2: Backend export — `GET /decks/{deck_id}/export` (AC: 1)
  - [x] T2.1: Write failing tests `TestExportDeck` in `tests/api/test_decks.py` and `TestExportDeckCore` in `tests/core/test_decks.py`:
    - Valid deck → valid ZIP with `deck.json` + audio files
    - Deck with no audio → ZIP with `deck.json` + empty `audio/` dir
    - Empty deck (no cards) → `deck.json` with `"cards": []`
    - 404 on unknown deck_id
  - [x] T2.2: Add `export_deck_to_zip(deck_id, session) -> io.BytesIO` to `core/decks.py`
    - Query deck + all its cards
    - Build `deck.json` per the §DeckJsonFormat spec below
    - For each card where `audio_url` is set: read `~/.lingosips/audio/{card.id}.wav` if file exists, add to ZIP as `audio/{card.id}.wav`; set `"audio_file": "{card.id}.wav"` in card JSON
    - Create in-memory ZIP (`io.BytesIO`, `zipfile.ZipFile` with `ZIP_DEFLATED`)
    - Return the BytesIO buffer (seek to 0 before returning)
  - [x] T2.3: Add `@router.get("/{deck_id}/export")` to `api/decks.py`
    - Calls `core_decks.export_deck_to_zip()`
    - Returns `StreamingResponse(zip_bytes, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{safe_name}.lingosips"'})`
    - 404 on unknown deck_id (ValueError from core → HTTPException)
    - Use `deck.name` sanitized: strip non-alphanumeric chars for filename safety
  - [x] T2.4: Confirm all backend export tests pass

- [x] T3: Backend import — `POST /import/preview/lingosips` + `POST /import/start/lingosips` (AC: 2, 4, 5, 6)
  - [x] T3.1: Write failing tests in `tests/api/test_imports.py` (`TestLingosipsPreview`) and `tests/core/test_imports.py` (`TestParseLingosipsFile`):
    - Valid .lingosips → correct preview response
    - Malformed ZIP → 422 with specific error
    - Missing `deck.json` → 422
    - Missing required fields in `deck.json` → 422
    - Cards with malformed FSRS fields → 422
  - [x] T3.2: Add `parse_lingosips_file(file_bytes: bytes) -> LingosipsImportPreview` to `core/imports.py`
    - Use stdlib `zipfile.ZipFile(io.BytesIO(file_bytes))` — NOT `genanki`
    - Validate: is valid ZIP, contains `deck.json`, has required keys (`format_version`, `deck`, `cards`)
    - Each card needs at minimum `target_word` + `target_language`
    - Raise `ValueError` with descriptive message for each validation failure
    - Return `LingosipsImportPreview` (deck_name, target_language, total_cards, sample_cards[0:5])
  - [x] T3.3: Write failing tests `TestLingosipsImportStart` in `tests/api/test_imports.py` and `TestImportLingosipsDeck` in `tests/core/test_imports.py`:
    - Valid file → deck created, cards created, audio stored, correct response
    - Audio files in ZIP → stored at correct paths, audio_url set
    - Deck name conflict → 409
    - Malformed file → 422
  - [x] T3.4: Add `import_lingosips_deck(file_bytes: bytes, session: AsyncSession) -> tuple[int, int]` to `core/imports.py`
    - Calls `parse_lingosips_file()` first (re-validates)
    - Creates deck via `core_decks.create_deck()` — raises ValueError on name conflict (→ 409 in router)
    - Creates all cards synchronously in a single session flush
    - For each card with `audio_file`: extract audio bytes from ZIP → write to `AUDIO_DIR / f"{new_card.id}.wav"` using `asyncio.to_thread` → set `card.audio_url = f"/cards/{new_card.id}/audio"`
    - `await session.commit()` once after all cards created (not per-card)
    - Returns `(deck_id, card_count)`
  - [x] T3.5: Add `POST /import/preview/lingosips` and `POST /import/start/lingosips` to `api/imports.py`
    - Both use `UploadFile = File(...)` multipart — same pattern as `preview_anki`
    - `/preview/lingosips` → calls `core.parse_lingosips_file()` → returns `ImportPreviewResponse`
    - `/start/lingosips` → calls `core.import_lingosips_deck()` → returns `LingosipsImportStartResponse(deck_id, card_count)`
    - ValueError → 422 RFC 7807; ValueError("already exists") → 409 RFC 7807
  - [x] T3.6: Confirm all backend import tests pass

- [x] T4: Frontend — DeckExportImport component (AC: 1)
  - [x] T4.1: Write failing tests `DeckExportImport.test.tsx`:
    - `idle` state shows "Export deck" button
    - `exporting` state shows loading state on button
    - `error` state shows error notification
    - Keyboard accessible (button receives focus)
  - [x] T4.2: Create `frontend/src/features/decks/DeckExportImport.tsx`
    - State machine: `type ExportState = "idle" | "exporting" | "error"`
    - Export handler uses raw `fetch()` (NOT `client.ts` — binary response needed): `fetch("/decks/${deckId}/export")` → blob → `URL.createObjectURL` → anchor click → `URL.revokeObjectURL`
    - On success: state → `"idle"` (download is self-completing)
    - On error: state → `"error"` + `useAppStore.getState().addNotification({type: "error", message: "Export failed — please try again"})`
    - Button disabled in `"exporting"` state
    - `aria-label="Export deck as .lingosips file"`
  - [x] T4.3: Export `DeckExportImport` from `frontend/src/features/decks/index.ts`
  - [x] T4.4: Confirm tests pass

- [x] T5: Frontend — Deck detail page (AC: 1)
  - [x] T5.1: Replace stub in `frontend/src/routes/decks.$deckId.tsx`
    - `useQuery(["decks", deckId], () => get("/decks/{deckId}"))` for deck info
    - Show: deck name, target language badge, card count, due card count
    - Render `DeckExportImport` component with `{deckId, deckName}` props
    - Card listing remains stub (`"Card browsing coming in a future story"`)
    - Handle loading + not-found states
  - [x] T5.2: Confirm deck detail page renders and export button works manually

- [x] T6: Frontend — Import .lingosips panel (AC: 2, 3, 4, 5)
  - [x] T6.1: Write failing tests `LingosipsImportPanel.test.tsx`
  - [x] T6.2: Create `frontend/src/features/import/LingosipsImportPanel.tsx`
    - File picker accepting `.lingosips` files (HTML: `accept=".lingosips"`)
    - Drag-and-drop support (same pattern as `AnkiImportPanel.tsx`)
    - On file select: call parent `onFileSelected(file)` callback
  - [x] T6.3: Update `frontend/src/features/import/ImportPage.tsx`
    - Add "lingosips" tab alongside Anki / Text / URL tabs
    - Add `"importing"` to `ImportState` type: `"idle" | "parsing" | "preview" | "enriching" | "importing" | "complete" | "error"`
    - For lingosips source: preview via `POST /import/preview/lingosips` (FormData, same as Anki)
    - On confirm: `POST /import/start/lingosips` (FormData) → response has `{deck_id, card_count}` (NOT `job_id`)
    - Transition: `preview → importing → complete` (no SSE, no enrichment, no progress ring)
    - On `complete`: `useAppStore.getState().addNotification({type: "success", message: "N cards imported"})`
    - Invalidate TanStack Query `["decks"]` on success so DeckGrid refreshes
  - [x] T6.4: Update `frontend/src/features/import/index.ts` — export `LingosipsImportPanel`
  - [x] T6.5: Confirm frontend tests pass (existing 192 Vitest tests must still pass)

- [x] T7: E2E tests (AC: 1–5)
  - [x] T7.1: Add to `frontend/e2e/features/deck-management.spec.ts`:
    - Export: navigate to deck detail → click Export → verify file download initiated
    - Import: navigate to Import → lingosips tab → upload exported file → confirm → verify deck in DeckGrid
    - Error: upload malformed .lingosips → verify specific error shown
  - [x] T7.2: Regenerate `frontend/src/lib/api.d.ts` from updated OpenAPI schema

## Dev Notes

### §FileChangeSummary — Which Files Change and Why

| File | Change | Why |
|---|---|---|
| `src/lingosips/api/decks.py` | **UPDATE** | Add `GET /{deck_id}` + `GET /{deck_id}/export` endpoints |
| `src/lingosips/core/decks.py` | **UPDATE** | Add `export_deck_to_zip()` function |
| `src/lingosips/api/imports.py` | **UPDATE** | Add `POST /preview/lingosips` + `POST /start/lingosips` |
| `src/lingosips/core/imports.py` | **UPDATE** | Add `LingosipsImportPreview` type, `parse_lingosips_file()`, `import_lingosips_deck()` |
| `tests/api/test_decks.py` | **UPDATE** | Add `TestGetDeck`, `TestExportDeck` |
| `tests/api/test_imports.py` | **UPDATE** | Add `TestLingosipsPreview`, `TestLingosipsImportStart` |
| `tests/core/test_decks.py` | **UPDATE** | Add `TestExportDeckCore` |
| `tests/core/test_imports.py` | **UPDATE** | Add `TestParseLingosipsFile`, `TestImportLingosipsDeck` |
| `frontend/src/features/decks/DeckExportImport.tsx` | **NEW** | Export button component (architecture-specified) |
| `frontend/src/features/decks/DeckExportImport.test.tsx` | **NEW** | TDD tests |
| `frontend/src/features/decks/index.ts` | **UPDATE** | Export `DeckExportImport` |
| `frontend/src/features/import/LingosipsImportPanel.tsx` | **NEW** | .lingosips file picker (parallel to `AnkiImportPanel.tsx`) |
| `frontend/src/routes/decks.$deckId.tsx` | **UPDATE** | Replace stub with real deck detail + export button |
| `frontend/src/features/import/ImportPage.tsx` | **UPDATE** | Add lingosips tab, add `"importing"` state |
| `frontend/src/features/import/index.ts` | **UPDATE** | Export `LingosipsImportPanel` |
| `frontend/e2e/features/deck-management.spec.ts` | **UPDATE** | Export/import E2E tests |
| `frontend/src/lib/api.d.ts` | **REGENERATED** | After adding new endpoints |

**DO NOT modify:**
- `src/lingosips/db/models.py` — no schema changes; no new Job table row needed (synchronous import)
- `src/lingosips/services/registry.py` — no new providers
- `src/lingosips/services/credentials.py` — no new credential keys
- `src/lingosips/api/app.py` — `imports_router` already registered; decks router already registered
- `frontend/src/lib/client.ts` — `get()`, `post()` untouched; export uses raw `fetch()` for binary
- `frontend/src/components/layout/` — no sidebar changes (no background job to show)

---

### §DeckJsonFormat — The deck.json Schema

`deck.json` is the mandatory file in every `.lingosips` archive:

```json
{
  "format_version": "1",
  "deck": {
    "name": "Spanish B2 Vocabulary",
    "target_language": "es",
    "settings_overrides": null
  },
  "cards": [
    {
      "target_word": "melancólico",
      "translation": "melancholic",
      "forms": "{\"gender\": \"m\", \"plural\": \"melancólicos\"}",
      "example_sentences": "[\"Es un hombre melancólico.\"]",
      "personal_note": null,
      "image_skipped": false,
      "card_type": "word",
      "target_language": "es",
      "stability": 2.5,
      "difficulty": 5.0,
      "due": "2026-05-15T10:00:00+00:00",
      "last_review": "2026-05-01T10:00:00+00:00",
      "reps": 3,
      "lapses": 0,
      "fsrs_state": "Review",
      "audio_file": "42.wav"
    }
  ]
}
```

**Critical rules for deck.json:**
- `format_version` MUST be `"1"` (string, not int) — for future compatibility detection
- `"id"` fields are **NOT exported** — IDs are assigned fresh on import
- `"audio_file"` is the filename inside the `audio/` folder in the ZIP (e.g. `"42.wav"`) or `null` if no audio
- `"image_url"` and `"image_skipped"` are exported but `image_url` is not imported (images stay with original user)
- All snake_case field names — never camelCase
- `"due"` and `"last_review"` are ISO 8601 UTC with `+00:00` offset (not `Z`) — use `datetime.isoformat()` in Python which produces `+00:00`
- `"forms"` and `"example_sentences"` are JSON **strings** (already encoded), not objects — export them as-is from `card.forms` and `card.example_sentences`

**Validation on import (422 if violated):**
- File is not a valid ZIP → `"detail": "File must be a valid .lingosips archive"`
- Missing `deck.json` → `"detail": "Archive is missing required deck.json"`
- Missing `format_version` / `deck` / `cards` keys → `"detail": "deck.json missing required key: {key}"`
- Each card missing `target_word` → `"detail": "Card {idx}: missing required field 'target_word'"`

---

### §ExportImplementation — Export ZIP in Memory

```python
# In core/decks.py
import io
import json
import zipfile
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AUDIO_DIR = Path.home() / ".lingosips" / "audio"

async def export_deck_to_zip(deck_id: int, session: AsyncSession) -> tuple[io.BytesIO, str]:
    """Returns (zip_bytes, deck_name). Raises ValueError if deck not found."""
    deck = await get_deck(deck_id, session)  # raises ValueError if not found
    
    # Load all cards in deck
    result = await session.execute(
        select(Card).where(Card.deck_id == deck_id)
    )
    cards = result.scalars().all()
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        card_jsons = []
        for card in cards:
            audio_file = None
            if card.audio_url:  # has audio
                audio_path = AUDIO_DIR / f"{card.id}.wav"
                if audio_path.exists():
                    zf.write(audio_path, f"audio/{card.id}.wav")
                    audio_file = f"{card.id}.wav"
            
            card_jsons.append({
                "target_word": card.target_word,
                "translation": card.translation,
                "forms": card.forms,
                "example_sentences": card.example_sentences,
                "personal_note": card.personal_note,
                "image_skipped": card.image_skipped,
                "card_type": card.card_type,
                "target_language": card.target_language,
                "stability": card.stability,
                "difficulty": card.difficulty,
                "due": card.due.isoformat(),
                "last_review": card.last_review.isoformat() if card.last_review else None,
                "reps": card.reps,
                "lapses": card.lapses,
                "fsrs_state": card.fsrs_state,
                "audio_file": audio_file,
            })
        
        deck_json = {
            "format_version": "1",
            "deck": {
                "name": deck.name,
                "target_language": deck.target_language,
                "settings_overrides": json.loads(deck.settings_overrides) if deck.settings_overrides else None,
            },
            "cards": card_jsons,
        }
        zf.writestr("deck.json", json.dumps(deck_json, ensure_ascii=False, indent=2))
    
    buf.seek(0)
    return buf, deck.name
```

**The API route pattern:**
```python
@router.get("/{deck_id}/export")
async def export_deck(deck_id: int, session: AsyncSession = Depends(get_session)):
    try:
        zip_bytes, deck_name = await core_decks.export_deck_to_zip(deck_id, session)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={"type": "/errors/deck-not-found", "title": "Deck not found",
                    "detail": f"Deck {deck_id} does not exist"},
        )
    safe_name = re.sub(r"[^\w\-. ]", "_", deck_name).strip()
    return StreamingResponse(
        zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.lingosips"'},
    )
```

---

### §ImportImplementation — Parse and Import .lingosips

**New types to add to `core/imports.py`:**
```python
@dataclass
class LingosipsCardData:
    """Parsed card from deck.json, preserving all fields including FSRS state."""
    target_word: str
    translation: str | None
    forms: str | None          # raw JSON string as-is from deck.json
    example_sentences: str | None  # raw JSON string as-is
    personal_note: str | None
    image_skipped: bool
    card_type: str
    target_language: str
    stability: float
    difficulty: float
    due: datetime
    last_review: datetime | None
    reps: int
    lapses: int
    fsrs_state: str
    audio_file: str | None     # filename in archive's audio/ folder, or None

@dataclass
class LingosipsImportPreview:
    """Preview returned by parse_lingosips_file() — used by API response."""
    deck_name: str
    target_language: str
    total_cards: int
    sample_cards: list[LingosipsCardData]  # first 5 only
    has_audio: bool            # True if at least one card has audio_file
```

**parse_lingosips_file() — validation skeleton:**
```python
def parse_lingosips_file(file_bytes: bytes) -> LingosipsImportPreview:
    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile:
        raise ValueError("File must be a valid .lingosips archive")
    
    if "deck.json" not in zf.namelist():
        raise ValueError("Archive is missing required deck.json")
    
    raw = json.loads(zf.read("deck.json"))
    
    for key in ("format_version", "deck", "cards"):
        if key not in raw:
            raise ValueError(f"deck.json missing required key: {key}")
    
    deck_data = raw["deck"]
    for key in ("name", "target_language"):
        if key not in deck_data:
            raise ValueError(f"deck.json missing required deck field: {key}")
    
    cards = []
    for i, c in enumerate(raw["cards"]):
        if "target_word" not in c:
            raise ValueError(f"Card {i}: missing required field 'target_word'")
        cards.append(LingosipsCardData(...))  # parse FSRS datetime fields with UTC
    
    return LingosipsImportPreview(
        deck_name=deck_data["name"],
        target_language=deck_data["target_language"],
        total_cards=len(cards),
        sample_cards=cards[:5],
        has_audio=any(c.audio_file for c in cards),
    )
```

**import_lingosips_deck() — audio handling:**
```python
async def import_lingosips_deck(file_bytes: bytes, session: AsyncSession) -> tuple[int, int]:
    preview = parse_lingosips_file(file_bytes)  # validates and re-parses
    zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    
    # create_deck() raises ValueError if name+language already exists → router converts to 409
    deck = await core_decks.create_deck(
        name=preview.deck_name,
        target_language=preview.target_language,
        session=session,
    )
    
    all_cards_raw = json.loads(zf.read("deck.json"))["cards"]
    created_cards = []
    for card_data in all_cards_raw:
        card = Card(
            target_word=card_data["target_word"],
            translation=card_data.get("translation"),
            forms=card_data.get("forms"),
            example_sentences=card_data.get("example_sentences"),
            personal_note=card_data.get("personal_note"),
            image_skipped=card_data.get("image_skipped", False),
            card_type=card_data.get("card_type", "word"),
            target_language=card_data.get("target_language", deck.target_language),
            deck_id=deck.id,
            stability=card_data.get("stability", 0.0),
            difficulty=card_data.get("difficulty", 0.0),
            due=_parse_dt(card_data.get("due")) or datetime.now(UTC),
            last_review=_parse_dt(card_data.get("last_review")),
            reps=card_data.get("reps", 0),
            lapses=card_data.get("lapses", 0),
            fsrs_state=card_data.get("fsrs_state", "New"),
        )
        session.add(card)
        created_cards.append((card, card_data.get("audio_file")))
    
    await session.flush()  # assigns card.id values without committing
    
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for card, audio_filename in created_cards:
        if audio_filename:
            archive_path = f"audio/{audio_filename}"
            if archive_path in zf.namelist():
                audio_bytes = zf.read(archive_path)
                dest = AUDIO_DIR / f"{card.id}.wav"
                await asyncio.to_thread(dest.write_bytes, audio_bytes)
                card.audio_url = f"/cards/{card.id}/audio"
    
    await session.commit()
    return deck.id, len(created_cards)
```

**`_parse_dt()` helper** — add to `core/imports.py`:
```python
def _parse_dt(value: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string to UTC-aware datetime, or return None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None
```

---

### §APIImportRoutes — New Import Endpoints

```python
# Add to api/imports.py

class LingosipsImportStartResponse(BaseModel):
    deck_id: int
    card_count: int

@router.post("/preview/lingosips", response_model=ImportPreviewResponse)
async def preview_lingosips(file: UploadFile = File(...)) -> ImportPreviewResponse:
    file_bytes = await file.read()
    try:
        preview = core_imports.parse_lingosips_file(file_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"type": "/errors/invalid-lingosips-file",
                    "title": "Invalid .lingosips file",
                    "detail": str(exc)},
        )
    return ImportPreviewResponse(
        source_type="lingosips",
        total_cards=preview.total_cards,
        fields_present=["target_word", "translation", "forms", "example_sentences"],
        fields_missing_summary={},  # lingosips files are already enriched
        cards=[CardPreviewResponse(
            target_word=c.target_word,
            translation=c.translation,
            example_sentence=None,
            has_audio=c.audio_file is not None,
            fields_missing=[],
            selected=True,
        ) for c in preview.sample_cards],
        deck_name=preview.deck_name,
        target_language=preview.target_language,
    )

@router.post("/start/lingosips", response_model=LingosipsImportStartResponse, status_code=201)
async def start_lingosips_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> LingosipsImportStartResponse:
    file_bytes = await file.read()
    try:
        deck_id, card_count = await core_imports.import_lingosips_deck(file_bytes, session)
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "already exists" in msg.lower() else 422
        error_type = "/errors/deck-name-conflict" if status == 409 else "/errors/invalid-lingosips-file"
        raise HTTPException(
            status_code=status,
            detail={"type": error_type,
                    "title": "Deck name conflict" if status == 409 else "Invalid .lingosips file",
                    "detail": msg},
        )
    return LingosipsImportStartResponse(deck_id=deck_id, card_count=card_count)
```

**`ImportPreviewResponse` already has all needed fields** — reuse it (source_type, total_cards, fields_present, fields_missing_summary, cards). You may need to add `deck_name` and `target_language` optional fields to `ImportPreviewResponse` if not already present. Check `api/imports.py` before adding — if missing, add them as `Optional[str] = None`.

---

### §FrontendExportPattern — Binary File Download

Do NOT use `client.ts` `get()` for the export — it assumes JSON responses. Use `fetch()` directly:

```typescript
// In DeckExportImport.tsx
async function handleExport() {
  setState("exporting")
  try {
    const response = await fetch(`/decks/${deckId}/export`)
    if (!response.ok) throw new Error(`Export failed: ${response.status}`)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${deckName}.lingosips`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    setState("idle")
  } catch {
    setState("error")
    useAppStore.getState().addNotification({ type: "error", message: "Export failed — please try again" })
  }
}
```

**Do NOT create a test for the actual file download** — `URL.createObjectURL` is not available in jsdom. Test that `fetch()` is called with the correct URL and that state transitions correctly (mock `fetch` in tests).

---

### §FrontendImportState — Updated ImportPage State Machine

```typescript
// Updated — "importing" added for .lingosips (no background enrichment)
type ImportState = "idle" | "parsing" | "preview" | "enriching" | "importing" | "complete" | "error"

// State transitions for .lingosips source:
// idle → parsing    (user selects .lingosips file)
// parsing → preview  (POST /import/preview/lingosips success)
// parsing → error    (POST /import/preview/lingosips failure → 422)
// preview → importing (user clicks "Import")
// importing → complete (POST /import/start/lingosips success)
// importing → error   (POST /import/start/lingosips failure → 409/422)
// complete → idle    ("Import more" button)

// UI label for "importing" state: "Importing deck..." (NOT "Enriching" — no AI involved)
```

**On successful .lingosips import — cache invalidation is mandatory:**
```typescript
import { useQueryClient } from "@tanstack/react-query"
const queryClient = useQueryClient()
// After POST /import/start/lingosips success:
await queryClient.invalidateQueries({ queryKey: ["decks"] })
```

---

### §FrontendDeckDetailPage — Deck Detail Route Update

`decks.$deckId.tsx` currently returns a stub. Replace with:

```typescript
function DeckDetailPage() {
  const { deckId } = Route.useParams()
  const id = Number(deckId)
  const { data: deck, isLoading, isError } = useQuery({
    queryKey: ["decks", id],
    queryFn: () => get<DeckResponse>(`/decks/${id}`),
  })

  if (isLoading) return <Skeleton className="m-8 h-32 w-full" />
  if (isError || !deck) return <p className="p-8 text-red-400">Deck not found</p>

  return (
    <div className="p-4 md:p-8 space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold">{deck.name}</h1>
        <Badge>{deck.target_language.toUpperCase()}</Badge>
        <span className="text-zinc-400 text-sm">{deck.card_count} cards · {deck.due_card_count} due</span>
      </div>
      <DeckExportImport deckId={deck.id} deckName={deck.name} />
      <p className="text-zinc-400 text-sm">Card browsing — coming in a future story.</p>
    </div>
  )
}
```

**TanStack Router file-based routing**: `deckId` param accessed via `Route.useParams()`. The type is `string`; convert to `Number(deckId)` for API calls.

---

### §PreviousStoryLearnings — From Stories 2.4

1. **`genanki` is write-only** — confirmed again: `core/imports.py` docstring says "genanki is for EXPORT (Story 2.5)". For reading ZIPs use stdlib `zipfile`. For export ZIP creation, you can use `zipfile` directly (simpler than genanki for this format).

2. **`asyncio.to_thread()` for file writes** — audio writes use `asyncio.to_thread(path.write_bytes, bytes)` per `core/cards.py` pattern.

3. **Multipart upload uses FormData, not JSON client** — `POST /import/preview/lingosips` uses the same `UploadFile = File(...)` pattern as `POST /import/preview/anki`. Frontend must use `FormData` + raw `fetch()` or `fetch()` with `FormData`.

4. **`app.dependency_overrides.pop()` teardown** — use safe-pop in test fixtures, not `.clear()`.

5. **`await screen.findByText()`** not `screen.getByText()` for async TanStack Query content.

6. **`JSON.parse()` guard** — not needed here (no SSE), but keep defensive try/catch on fetch error bodies.

7. **`concurrency = ["greenlet", "thread"]` in pyproject.toml coverage config** — already fixed in Story 2.4; verify it remains in place. SQLAlchemy async uses greenlet; without it, `await session.flush()` / `commit()` lines in `import_lingosips_deck()` will show as uncovered.

8. **Session `flush()` then `commit()` pattern** — use `await session.flush()` to get card IDs before writing audio files, then `await session.commit()` after all audio writes. Never commit per-card.

9. **IPv6/localhost Playwright config** — `127.0.0.1` not `localhost` in Playwright config (already fixed in 2.4).

10. **Test server isolation** — E2E tests for import should use a unique deck name (e.g. include timestamp) to avoid conflicts with other test suites.

---

### §MissingGetDeckEndpoint — Critical Gap

`GET /decks/{deck_id}` **does not exist in `api/decks.py`**. The deck router only has:
- `GET /` (list)
- `POST /` (create)
- `PATCH /{deck_id}` (update)
- `DELETE /{deck_id}` (delete)

`core/decks.get_deck()` exists and is used internally by `update_deck()` and `delete_deck()`. Task T1 adds the missing GET endpoint. This is required for the deck detail page and is a prerequisite for T5.

---

### §AudioDirInDecks — Don't Duplicate Constants

`AUDIO_DIR = Path.home() / ".lingosips" / "audio"` is defined in `core/cards.py`. For `core/decks.py`, define it locally at module level (same definition) — this is the MVP pattern. Do not create a `core/constants.py` file for two reasons: (1) it would require a new migration-style file creation not needed by this story, (2) the existing codebase pattern uses local constants per module.

---

### §ValidationEdgeCases — Common Trap Prevention

- **Non-.wav audio files** in ZIP: only extract files in `audio/` folder with `.wav` extension. If `audio_filename` from deck.json exists but isn't in the ZIP namelist, silently skip (card gets `audio_url=None`).
- **Oversized ZIP**: No explicit size limit in MVP — document as a known limitation.
- **UTF-8 in deck names**: `safe_name` for `Content-Disposition` header must handle Unicode deck names. Use `re.sub(r"[^\w\-. ]", "_", deck_name)` — this preserves most Unicode chars while removing shell-dangerous chars.
- **`image_url` field**: Export it to `deck.json` for completeness but **never import it** — images are stored locally, the URL would be invalid on the importing user's machine. On import, set `image_url=None` unconditionally.
- **`settings_overrides` in deck.json**: Export the parsed dict (not the raw JSON string). On import, serialize back with `json.dumps()` before storing.

---

### Project Structure Notes

**Architecture specifies `DeckExportImport.tsx` in `features/decks/`** — confirmed by architecture doc:
```
├── decks/
│   ├── DeckGrid.tsx
│   ├── DeckGrid.test.tsx
│   ├── DeckCard.tsx
│   ├── DeckExportImport.tsx        # FR11–12
│   └── index.ts
```

**Import feature folder pattern** — `LingosipsImportPanel.tsx` follows `AnkiImportPanel.tsx` naming (source + "ImportPanel" suffix).

**No new API router** — export endpoint added to existing `api/decks.py` router (`/decks/{id}/export`); import endpoints added to existing `api/imports.py` router (`/import/preview/lingosips`, `/import/start/lingosips`).

**No Alembic migration** — no DB schema changes. All data fits in existing `Card` and `Deck` tables.

**`genanki` is ALREADY in `pyproject.toml`** (added in 2.4 prep for Story 2.5) but is a write-only library. This story uses `zipfile` stdlib for both export and import ZIP handling. `genanki` may be used for any future Anki-format export story.

### References

- Architecture: `DeckExportImport.tsx` location — `_bmad-output/planning-artifacts/architecture.md` §Complete Project Directory Structure
- Architecture: `.lingosips` format — `_bmad-output/planning-artifacts/architecture.md` §Important — Deck export/import file format
- DB schema: `src/lingosips/db/models.py` — `Card`, `Deck` tables (confirmed 2026-05-01)
- Audio storage: `src/lingosips/core/cards.py` line 25 — `AUDIO_DIR = Path.home() / ".lingosips" / "audio"`; line 239 — `audio_path = AUDIO_DIR / f"{card.id}.wav"`
- Import patterns: `src/lingosips/core/imports.py` — `parse_apkg()`, `import_lingosips_deck()` to add
- Story 2.4 learnings: `_bmad-output/implementation-artifacts/2-4-import-pipeline-anki-text-url.md` §PreviousStoryLearnings, §BackgroundTaskPattern
- Deck API: `src/lingosips/api/decks.py` — confirmed no `GET /{deck_id}` endpoint exists
- Project rules: `_bmad-output/project-context.md` — all naming conventions, layer architecture, testing rules

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (2026-05-01)

### Debug Log References

- Fixed `global.fetch` / `global.URL.createObjectURL` TypeScript errors in `DeckExportImport.test.tsx` by switching to `vi.stubGlobal()` pattern
- Fixed unused `React` import TS6133 error in test file by removing the unused import
- Fixed `lingosipsFileRef` state persistence issue — `let _lingosipsFile` was reset on each re-render; replaced with `useRef<File | null>(null)`
- Fixed `LingosipsImportPanel` isParsing test matcher — button text changes to "Parsing..." so updated regex to `/parsing|preview/i`

### Completion Notes List

- All 7 tasks (T1–T7) implemented following TDD: failing tests written first, then implementation
- Backend: 459 tests pass, 95.74% coverage (≥90% threshold met)
- Frontend: 208 tests pass across 18 test files
- New backend endpoints: `GET /decks/{deck_id}`, `GET /decks/{deck_id}/export`, `POST /import/preview/lingosips`, `POST /import/start/lingosips`
- Export: in-memory ZIP with `deck.json` + optional `audio/` folder; StreamingResponse with `Content-Disposition` header
- Import: `parse_lingosips_file()` validates structure with descriptive RFC 7807 errors; `import_lingosips_deck()` uses `session.flush()` to get card IDs before audio writes, single `session.commit()` after all audio
- Audio: `asyncio.to_thread()` used for file writes in async context; stored at `~/.lingosips/audio/{new_card_id}.wav`
- Frontend: `DeckExportImport.tsx` uses raw `fetch()` for binary download; `lingosipsFileRef = useRef()` persists file across renders
- TanStack Query `["decks"]` cache invalidated on successful lingosips import
- api.d.ts regenerated from FastAPI OpenAPI schema (new endpoints present)
- 3 new E2E tests added: export download, import preview flow, malformed file error

### File List

- `src/lingosips/api/decks.py` — Added `GET /{deck_id}` + `GET /{deck_id}/export` endpoints
- `src/lingosips/core/decks.py` — Added `AUDIO_DIR`, `get_deck_with_counts()`, `export_deck_to_zip()`
- `src/lingosips/api/imports.py` — Added `deck_name`/`target_language` fields to `ImportPreviewResponse`; added `LingosipsImportStartResponse`; added `POST /preview/lingosips` + `POST /start/lingosips`
- `src/lingosips/core/imports.py` — Added `LingosipsCardData`, `LingosipsImportPreview`, `_parse_dt()`, `parse_lingosips_file()`, `import_lingosips_deck()`
- `tests/api/test_decks.py` — Added `TestGetDeck` (5 tests), `TestExportDeck` (7 tests)
- `tests/core/test_decks.py` — Added `TestExportDeckCore` (5 tests)
- `tests/core/test_imports.py` — Added `_make_lingosips_file()` helper, `TestParseLingosipsFile` (11 tests), `TestImportLingosipsDeck` (6 tests)
- `tests/api/test_imports.py` — Added `_make_lingosips_bytes()` helper, `TestLingosipsPreview` (6 tests), `TestLingosipsImportStart` (4 tests)
- `frontend/src/features/decks/DeckExportImport.tsx` — NEW: export button component with fetch + blob download
- `frontend/src/features/decks/DeckExportImport.test.tsx` — NEW: 8 Vitest tests (vi.stubGlobal pattern)
- `frontend/src/features/decks/index.ts` — Added `export { DeckExportImport }`
- `frontend/src/routes/decks.$deckId.tsx` — Replaced stub with real deck detail page + DeckExportImport
- `frontend/src/features/import/LingosipsImportPanel.tsx` — NEW: drag-and-drop .lingosips file picker
- `frontend/src/features/import/LingosipsImportPanel.test.tsx` — NEW: 8 Vitest tests
- `frontend/src/features/import/ImportPage.tsx` — Added lingosips tab, "importing" state, handleLingosipsPreview, handleConfirmLingosipsImport, lingosipsFileRef
- `frontend/src/features/import/index.ts` — Added `export { LingosipsImportPanel }`
- `frontend/e2e/features/deck-management.spec.ts` — Added 3 E2E tests (export, import preview, malformed file)
- `frontend/src/lib/api.d.ts` — Regenerated from updated OpenAPI schema

### Review Findings

- [x] [Review][Patch] Ruff linter: 13 errors (E501, F401, I001) across api/imports.py, tests/ — **Fixed** auto
- [x] [Review][Patch] `parse_lingosips_file` accepts any format_version value (missing `== "1"` check) [core/imports.py] — **Fixed** + 2 tests added
- [x] [Review][Patch] Empty/whitespace `target_word` passes import validation [core/imports.py] — **Fixed** + 1 test added
- [x] [Review][Patch] Blocking disk I/O (`audio_path.exists()`, `zf.write()`) in async `export_deck_to_zip` [core/decks.py] — **Fixed** with `asyncio.to_thread()`
- [x] [Review][Patch] `datetime.now(UTC)` called inside card loop in `parse_lingosips_file` (minor efficiency) [core/imports.py] — **Fixed** (moved outside loop)
- [x] [Review][Patch] Misleading docstring: "genanki is for EXPORT" — implementation uses zipfile [core/imports.py] — **Fixed**
- [x] [Review][Patch] `due`/`last_review` fields exported without UTC offset — SQLite strips tzinfo on read-back [core/decks.py] — **Fixed** via `_to_utc_isoformat()` helper + 1 test
- [x] [Review][Patch] Frontend `DeckExportImport` uses unsanitized `deckName` for `a.download` attribute [DeckExportImport.tsx] — **Fixed** with sanitization regex + 1 test
- [x] [Review][Patch] `LingosipsImportPanel` silently discards invalid file types with no user feedback [LingosipsImportPanel.tsx] — **Fixed** with `role="alert"` error message + 2 tests
- [x] [Review][Defer] Session atomicity: `create_deck()` commits before cards flush; orphaned deck on failure — pre-existing MVP architecture trade-off, all core functions commit eagerly
- [x] [Review][Defer] 409 routing uses string match on `ValueError.message`; fragile coupling — acceptable for MVP, no other code path in import raises ValueError("conflict")

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-05-01 | Implemented Story 2.5 — .lingosips export/import format. All 7 tasks complete. 459 backend + 208 frontend tests pass. | claude-sonnet-4-5 |
| 2026-05-01 | Code review: 9 patches applied (linter fixes, format_version validation, UTC datetime export, async disk I/O, frontend filename sanitization, invalid-file-type feedback). 2 deferred. Backend: 463 tests, 95.76% coverage. Frontend: 211 tests. | claude-sonnet-4-7 |
