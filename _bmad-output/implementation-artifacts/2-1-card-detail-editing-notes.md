# Story 2.1: Card Detail, Editing & Notes

Status: done

## Story

As a user,
I want to view card details, add personal notes, edit any AI-generated field, and delete cards,
so that I can customize my vocabulary cards to match my learning context.

## Acceptance Criteria

1. **Given** a card exists in my collection
   **When** I navigate to `/cards/{card_id}`
   **Then** `CardDetail` renders showing all fields: target word, translation, grammatical forms, example sentences, audio player, personal note, and FSRS due status

2. **Given** I click any AI-generated field in CardDetail
   **When** I edit the text
   **Then** it saves inline on blur (`PATCH /cards/{card_id}` with only the updated field)
   **And** the updated value is reflected immediately without a page reload

3. **Given** I add or edit a personal note
   **When** I finish editing (blur)
   **Then** the note persists to the `cards` table and is shown on future card views

4. **Given** I click "Delete card"
   **When** the delete action is triggered
   **Then** a confirmation Dialog appears with text "Delete card · This cannot be undone" and Cancel / Delete actions

5. **Given** I confirm deletion
   **When** `DELETE /cards/{card_id}` is called
   **Then** the card is removed from SQLite and no longer appears in any deck or practice queue
   **And** I am navigated back to the home page

6. **Given** `GET /cards/{card_id}` is called with a non-existent ID
   **Then** a `404` response with RFC 7807 body is returned: `{"type": "/errors/card-not-found", "title": "Card not found", "status": 404, "detail": "Card {id} does not exist"}`

7. API tests must cover: successful fetch, successful update of each editable field, 404 on missing card, 422 on invalid field values, and deletion removing the card from FSRS queue.

## Tasks / Subtasks

> **TDD MANDATORY**: Write failing tests BEFORE writing implementation. All tasks marked [TDD] require tests first.

---

### Backend Tasks

- [x] **T1: Add `patch` + update `del` functions in `frontend/src/lib/client.ts`** (prerequisite for frontend tasks)
  - [x] T1.1: Add `patch<T>` function:
    ```typescript
    export async function patch<T>(path: string, body: unknown): Promise<T> {
      const response = await fetch(`${BASE_URL}${path}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
      })
      return handleResponse<T>(response)
    }
    ```
  - [x] T1.2: Update `del<T>` to handle 204 No Content (current implementation calls `response.json()` which throws on empty body):
    ```typescript
    export async function del<T = void>(path: string): Promise<T> {
      const response = await fetch(`${BASE_URL}${path}`, {
        method: "DELETE",
        headers: { Accept: "application/json" },
      })
      // Handle 204 No Content — no body to parse
      if (response.status === 204) return undefined as T
      return handleResponse<T>(response)
    }
    ```

- [x] **T2: Write failing backend tests for `GET /cards/{card_id}` [TDD — FIRST]** (AC: 1, 6)
  - [x] T2.1: Add `class TestGetCard:` to `tests/api/test_cards.py`
  - [x] T2.2: Test cases (run in class with `@pytest.mark.anyio`):
    - `test_get_card_success` — seed a card, call `GET /cards/{card.id}`, verify `200` + all fields in response (id, target_word, translation, forms dict, example_sentences list, audio_url, personal_note, fsrs_state, due, target_language)
    - `test_get_card_not_found_returns_404_rfc7807` — call `GET /cards/99999`, verify `404` + `{"type": "/errors/card-not-found", "status": 404}`
    - `test_get_card_forms_parsed_as_object_not_string` — seed card with forms JSON, verify response `forms` is a dict (not a raw JSON string)
    - `test_get_card_example_sentences_parsed_as_list` — seed card with example_sentences JSON, verify response `example_sentences` is a list
    - `test_get_card_fields_are_snake_case` — verify response uses snake_case keys only (no camelCase)
  - [x] T2.3: Add `seed_card` fixture that inserts a `Card` directly into the test DB session (no LLM mock needed):
    ```python
    @pytest.fixture
    async def seed_card(session: AsyncSession) -> Card:
        import json
        from lingosips.db.models import Card
        card = Card(
            target_word="melancólico",
            translation="melancholic",
            forms=json.dumps({"gender": "masculine", "article": "el", "plural": "melancólicos", "conjugations": {}}),
            example_sentences=json.dumps(["Tenía un aire melancólico.", "Era un día melancólico."]),
            target_language="es",
        )
        session.add(card)
        await session.commit()
        await session.refresh(card)
        return card
    ```

- [x] **T3: Write failing backend tests for `PATCH /cards/{card_id}` [TDD — FIRST]** (AC: 2, 3, 7)
  - [x] T3.1: Add `class TestPatchCard:` to `tests/api/test_cards.py`
  - [x] T3.2: Test cases:
    - `test_patch_translation_updates_field` — seed card, PATCH `{"translation": "gloomy"}`, verify `200` + response `translation == "gloomy"` + DB updated
    - `test_patch_personal_note_persists` — seed card, PATCH `{"personal_note": "my note"}`, verify `200` + note stored
    - `test_patch_example_sentences_updates_list` — PATCH `{"example_sentences": ["New sentence."]}`, verify response has the list
    - `test_patch_forms_updates_object` — PATCH `{"forms": {"gender": "feminine", "article": "la", "plural": "melancólicas", "conjugations": {}}}`, verify response forms.gender == "feminine"
    - `test_patch_only_updates_provided_fields` — PATCH only `translation`, verify `personal_note` and `example_sentences` unchanged in DB
    - `test_patch_card_not_found_returns_404` — PATCH `/cards/99999`, verify `404` RFC 7807
    - `test_patch_empty_translation_returns_422` — PATCH `{"translation": ""}`, verify `422`
    - `test_patch_returns_updated_card_response` — verify PATCH returns the full `CardResponse` shape (not just the changed field)

- [x] **T4: Write failing backend tests for `DELETE /cards/{card_id}` [TDD — FIRST]** (AC: 5, 7)
  - [x] T4.1: Add `class TestDeleteCard:` to `tests/api/test_cards.py`
  - [x] T4.2: Test cases:
    - `test_delete_card_returns_204` — seed card, DELETE, verify `204 No Content`
    - `test_delete_card_removes_from_db` — seed card, DELETE, then `GET /cards/{id}` returns `404`
    - `test_delete_card_not_found_returns_404` — DELETE `/cards/99999`, verify `404` RFC 7807
    - `test_delete_card_removes_from_practice_queue` — seed card with `due=now`, verify in practice queue, DELETE card, verify no longer in queue (AC: 7)

- [x] **T5: Add Pydantic models to `src/lingosips/api/cards.py`** (AC: 1, 2, 6)
  - [x] T5.1: Add at top of file (after existing imports), before router definition:
    ```python
    import json
    from datetime import datetime

    from pydantic import BaseModel, Field

    class CardFormsData(BaseModel):
        """Grammatical forms for a card — parsed from DB JSON string."""
        gender: str | None = None
        article: str | None = None
        plural: str | None = None
        conjugations: dict = Field(default_factory=dict)

    class CardResponse(BaseModel):
        """Full card response shape — returned by GET and PATCH /cards/{card_id}."""
        id: int
        target_word: str
        translation: str | None
        forms: CardFormsData | None
        example_sentences: list[str]
        audio_url: str | None
        personal_note: str | None
        image_url: str | None
        image_skipped: bool
        card_type: str
        deck_id: int | None
        target_language: str
        fsrs_state: str
        due: datetime
        stability: float
        difficulty: float
        reps: int
        lapses: int
        last_review: datetime | None
        created_at: datetime
        updated_at: datetime

    class CardUpdateRequest(BaseModel):
        """Partial update request for PATCH /cards/{card_id}.
        Only fields present in the request body are updated (checked via model_fields_set).
        """
        translation: str | None = Field(default=None, min_length=1, max_length=2000)
        forms: CardFormsData | None = None
        example_sentences: list[str] | None = None
        personal_note: str | None = Field(default=None, max_length=5000)
        deck_id: int | None = None
    ```
  - [x] T5.2: Import `Card` from `lingosips.db.models` and add `_card_to_response()` helper function just before the router definition:
    ```python
    from lingosips.db.models import Card

    def _card_to_response(card: Card) -> CardResponse:
        """Convert a Card ORM instance to a CardResponse, parsing JSON fields."""
        forms = None
        if card.forms:
            try:
                forms = CardFormsData(**json.loads(card.forms))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass  # Return None if forms JSON is malformed

        example_sentences: list[str] = []
        if card.example_sentences:
            try:
                parsed = json.loads(card.example_sentences)
                if isinstance(parsed, list):
                    example_sentences = [str(s) for s in parsed]
            except (json.JSONDecodeError, TypeError):
                pass

        return CardResponse(
            id=card.id,
            target_word=card.target_word,
            translation=card.translation,
            forms=forms,
            example_sentences=example_sentences,
            audio_url=card.audio_url,
            personal_note=card.personal_note,
            image_url=card.image_url,
            image_skipped=card.image_skipped,
            card_type=card.card_type,
            deck_id=card.deck_id,
            target_language=card.target_language,
            fsrs_state=card.fsrs_state,
            due=card.due,
            stability=card.stability,
            difficulty=card.difficulty,
            reps=card.reps,
            lapses=card.lapses,
            last_review=card.last_review,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )
    ```
  - [x] T5.3: **IMPORTANT**: The existing `api/cards.py` already imports `Card` from `core/cards.py` (`from lingosips.core.cards import AUDIO_DIR, CardCreateRequest`). The new `Card` import is from `lingosips.db.models`. Ensure no import name collision — the SQLModel `Card` and the Pydantic `CardCreateRequest` are different things. Rename or alias as needed if collision occurs.

- [x] **T6: Add core functions to `src/lingosips/core/cards.py`** (AC: 1, 2, 3, 5, 6)
  - [x] T6.1: Add `get_card()`:
    ```python
    async def get_card(card_id: int, session: AsyncSession) -> Card:
        """Fetch a card by ID. Raises ValueError if not found (router converts to 404)."""
        from sqlalchemy import select
        from lingosips.db.models import Card

        result = await session.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()
        if card is None:
            raise ValueError(f"Card {card_id} does not exist")
        return card
    ```
  - [x] T6.2: Add `update_card()` — use `model_fields_set` for partial update semantics:
    ```python
    async def update_card(
        card_id: int,
        update_data: dict,   # keyed by field name, only fields the caller wants to change
        session: AsyncSession,
    ) -> Card:
        """Partially update a card. Only keys present in update_data are changed.
        Raises ValueError if card not found.
        """
        import json
        from datetime import UTC, datetime
        from lingosips.db.models import Card

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

        card.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(card)
        return card
    ```
  - [x] T6.3: Add `delete_card()`:
    ```python
    async def delete_card(card_id: int, session: AsyncSession) -> None:
        """Delete a card by ID. Raises ValueError if not found."""
        from lingosips.db.models import Card

        card = await get_card(card_id, session)
        await session.delete(card)
        await session.commit()
    ```
  - [x] T6.4: **Import guard**: `get_card` is called by both `update_card` and `delete_card`. Keep it as a module-level function so it can be called without circular imports. The `Card` SQLModel import goes inside functions (or at module top if no circular issue — check imports in the existing file first).

- [x] **T7: Add 3 new endpoints to `src/lingosips/api/cards.py`** (AC: 1, 2, 3, 5, 6)
  - [x] T7.1: Add `GET /cards/{card_id}` (place after the audio endpoint):
    ```python
    @router.get("/{card_id}", response_model=CardResponse)
    async def get_card(
        card_id: int,
        session: AsyncSession = Depends(get_session),
    ) -> CardResponse:
        """Fetch full card details by ID.

        Returns CardResponse with all fields, including forms/example_sentences
        parsed from their DB JSON string representation.
        404 RFC 7807 if card does not exist.
        """
        try:
            card = await core_cards.get_card(card_id, session)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "/errors/card-not-found",
                    "title": "Card not found",
                    "status": 404,
                    "detail": f"Card {card_id} does not exist",
                },
            )
        return _card_to_response(card)
    ```
  - [x] T7.2: Add `PATCH /cards/{card_id}`:
    ```python
    @router.patch("/{card_id}", response_model=CardResponse)
    async def patch_card(
        card_id: int,
        request: CardUpdateRequest,
        session: AsyncSession = Depends(get_session),
    ) -> CardResponse:
        """Partially update a card — only fields present in the request body are changed.

        Uses model_fields_set to detect which fields were explicitly provided.
        Returns the full updated CardResponse.
        404 if card does not exist, 422 if field validation fails.
        """
        # Build update dict from only the fields explicitly provided in the request
        update_data: dict = {}
        if "translation" in request.model_fields_set:
            update_data["translation"] = request.translation
        if "personal_note" in request.model_fields_set:
            update_data["personal_note"] = request.personal_note
        if "deck_id" in request.model_fields_set:
            update_data["deck_id"] = request.deck_id
        if "forms" in request.model_fields_set:
            update_data["forms"] = request.forms.model_dump() if request.forms else None
        if "example_sentences" in request.model_fields_set:
            update_data["example_sentences"] = request.example_sentences

        try:
            card = await core_cards.update_card(card_id, update_data, session)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "/errors/card-not-found",
                    "title": "Card not found",
                    "status": 404,
                    "detail": f"Card {card_id} does not exist",
                },
            )
        return _card_to_response(card)
    ```
  - [x] T7.3: Add `DELETE /cards/{card_id}`:
    ```python
    from fastapi import Response  # add to existing imports

    @router.delete("/{card_id}", status_code=204)
    async def delete_card(
        card_id: int,
        session: AsyncSession = Depends(get_session),
    ) -> Response:
        """Delete a card by ID.

        Returns 204 No Content on success.
        404 RFC 7807 if card does not exist.
        """
        try:
            await core_cards.delete_card(card_id, session)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "/errors/card-not-found",
                    "title": "Card not found",
                    "status": 404,
                    "detail": f"Card {card_id} does not exist",
                },
            )
        return Response(status_code=204)
    ```
  - [x] T7.4: **Route ordering matters in FastAPI**: The audio endpoint is `GET /{card_id}/audio`. The new `GET /{card_id}` endpoint. FastAPI routes are matched in order of declaration. Since `/audio` is a sub-path and `/cards/{card_id}` is the parent, place the `/{card_id}` endpoint BEFORE `/{card_id}/audio` to avoid route shadowing. Verify route ordering after adding new endpoints.
  - [x] T7.5: Regenerate `frontend/src/lib/api.d.ts` after backend is complete:
    ```bash
    # Start dev server first
    uv run uvicorn src.lingosips.api.app:app --port 7843 &
    npx openapi-typescript http://localhost:7843/openapi.json -o frontend/src/lib/api.d.ts
    # Stop dev server
    kill %1
    ```
    Verify `api.d.ts` includes `CardResponse`, `CardUpdateRequest`, `CardFormsData` schemas.

---

### Frontend Tasks

- [x] **T8: Write `frontend/src/features/cards/CardDetail.test.tsx` [TDD — write FIRST]** (AC: 1–5)
  - [x] T8.1: Set up mocks and helpers:
    ```typescript
    import { vi, describe, it, expect, beforeEach, afterEach } from "vitest"
    import { render, screen, waitFor, fireEvent } from "@testing-library/react"
    import userEvent from "@testing-library/user-event"
    import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

    vi.mock("@/lib/client", () => ({
      get: vi.fn(),
      patch: vi.fn(),
      del: vi.fn(),
      ApiError: class ApiError extends Error {
        constructor(public status: number, public type: string, public title: string, public detail?: string) {
          super(title)
        }
      },
    }))
    // Mock TanStack Router navigate
    vi.mock("@tanstack/react-router", () => ({
      useNavigate: () => vi.fn(),
      Link: ({ children, to }: { children: React.ReactNode; to: string }) => <a href={to}>{children}</a>,
    }))

    function renderDetail(cardId: number) {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      })
      return render(
        <QueryClientProvider client={queryClient}>
          <CardDetail cardId={cardId} />
        </QueryClientProvider>
      )
    }

    const MOCK_CARD = {
      id: 1,
      target_word: "melancólico",
      translation: "melancholic",
      forms: { gender: "masculine", article: "el", plural: "melancólicos", conjugations: {} },
      example_sentences: ["Tenía un aire melancólico.", "Era un día melancólico."],
      audio_url: "/cards/1/audio",
      personal_note: null,
      image_url: null,
      image_skipped: false,
      card_type: "word",
      deck_id: null,
      target_language: "es",
      fsrs_state: "New",
      due: "2026-05-01T00:00:00Z",
      stability: 0,
      difficulty: 0,
      reps: 0,
      lapses: 0,
      last_review: null,
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z",
    }
    ```
  - [x] T8.2: Test loading state: mock `get` as never resolving → verify loading skeleton or "Loading..." text visible
  - [x] T8.3: Test viewing state: mock `get` resolving MOCK_CARD → verify all fields rendered:
    - `await screen.findByText("melancólico")` (target word)
    - `await screen.findByText("melancholic")` (translation)
    - Verify FSRS status "Not yet practiced" (for fsrs_state="New")
  - [x] T8.4: Test error state: mock `get` rejecting with ApiError(404, ...) → verify "Card not found" error message shown
  - [x] T8.5: Test inline translation edit:
    - Mock `get` resolving MOCK_CARD, mock `patch` resolving `{ ...MOCK_CARD, translation: "gloomy" }`
    - Click translation display element
    - Verify input field appears with current value "melancholic"
    - Type new value "gloomy"
    - Trigger blur event (`fireEvent.blur(input)`)
    - Verify `patch` was called with `/cards/1` and `{ translation: "gloomy" }`
  - [x] T8.6: Test personal note edit:
    - Mock `get` with personal_note: null → click note area → textarea appears → type "my personal note" → blur
    - Verify `patch` called with `{ personal_note: "my personal note" }`
  - [x] T8.7: Test delete flow:
    - Mock `get` resolving MOCK_CARD, mock `del` resolving undefined (204)
    - Click "Delete card" button
    - Verify Dialog appears with text "Delete card · This cannot be undone"
    - Click "Delete" in Dialog
    - Verify `del` called with `/cards/1`
  - [x] T8.8: Test delete cancel:
    - Open Dialog → click "Cancel" → Dialog closes → `del` NOT called
  - [x] T8.9: Test aria attributes:
    - Delete button has `aria-label` indicating destructive action
    - Edit fields have `aria-label` per field name (e.g., `aria-label="Edit translation"`)

- [x] **T9: Create `frontend/src/routes/cards.$cardId.tsx`** (AC: 1)
  ```typescript
  import { createFileRoute } from "@tanstack/react-router"
  import { CardDetail } from "../features/cards"

  export const Route = createFileRoute("/cards/$cardId")({
    component: CardDetailPage,
  })

  function CardDetailPage() {
    const { cardId } = Route.useParams()
    return (
      <div className="min-h-full p-4 md:p-8">
        <CardDetail cardId={Number(cardId)} />
      </div>
    )
  }
  ```

- [x] **T10: Create `frontend/src/features/cards/CardDetail.tsx`** (AC: 1–5)
  - [ ] T10.1: Define state machine type:
    ```typescript
    type CardDetailState = "loading" | "viewing" | "confirm-delete" | "deleting" | "error"
    ```
    Note: `loading`/`error` derived from TanStack Query; `viewing`/`confirm-delete`/`deleting` are local state.
  - [ ] T10.2: Import `del`, `patch`, `get` from `@/lib/client`; import `useNavigate` from `@tanstack/react-router`
  - [ ] T10.3: TanStack Query fetch:
    ```typescript
    const { data: card, isLoading, isError } = useQuery({
      queryKey: ["cards", cardId],
      queryFn: () => get<CardResponse>(`/cards/${cardId}`),
    })
    ```
  - [ ] T10.4: PATCH mutation for field updates:
    ```typescript
    const updateField = useMutation({
      mutationFn: (update: Partial<CardUpdatePayload>) =>
        patch<CardResponse>(`/cards/${cardId}`, update),
      onSuccess: (updated) => {
        queryClient.setQueryData(["cards", cardId], updated)  // optimistic cache update
      },
      onError: (error: ApiError) => {
        useAppStore.getState().addNotification({ type: "error", message: error.detail ?? "Failed to save" })
      },
    })
    ```
  - [ ] T10.5: DELETE mutation:
    ```typescript
    const deleteCard = useMutation({
      mutationFn: () => del(`/cards/${cardId}`),
      onSuccess: () => {
        queryClient.removeQueries({ queryKey: ["cards", cardId] })
        queryClient.invalidateQueries({ queryKey: ["practice", "queue"] })
        navigate({ to: "/" })
      },
      onError: (error: ApiError) => {
        useAppStore.getState().addNotification({ type: "error", message: error.detail ?? "Delete failed" })
        setState("viewing")
      },
    })
    ```
  - [ ] T10.6: Inline field editing pattern — use `editingField` local state:
    ```typescript
    const [editingField, setEditingField] = useState<string | null>(null)
    const [fieldDraft, setFieldDraft] = useState<string>("")

    function startEdit(fieldName: string, currentValue: string) {
      setEditingField(fieldName)
      setFieldDraft(currentValue)
    }

    function commitEdit(fieldName: string) {
      if (editingField !== fieldName) return
      setEditingField(null)
      // Build the PATCH body for each field type:
      if (fieldName === "translation") {
        updateField.mutate({ translation: fieldDraft })
      } else if (fieldName === "personal_note") {
        updateField.mutate({ personal_note: fieldDraft || null })
      } else if (fieldName === "example_sentences") {
        const lines = fieldDraft.split("\n").map(l => l.trim()).filter(Boolean)
        updateField.mutate({ example_sentences: lines })
      } else if (fieldName === "forms") {
        try {
          const parsed = JSON.parse(fieldDraft)
          updateField.mutate({ forms: parsed })
        } catch {
          useAppStore.getState().addNotification({ type: "error", message: "Invalid JSON for forms field" })
        }
      }
    }
    ```
  - [ ] T10.7: Implement `EditableField` helper component inline in `CardDetail.tsx` (NOT exported — internal only):
    ```typescript
    function EditableField({
      fieldName,
      displayValue,
      multiline = false,
      ariaLabel,
      editingField,
      fieldDraft,
      onStartEdit,
      onChangeField,
      onBlur,
    }: EditableFieldProps) {
      if (editingField === fieldName) {
        const InputEl = multiline ? "textarea" : "input"
        return (
          <InputEl
            className="w-full rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-50 focus:border-indigo-500 focus:outline-none"
            value={fieldDraft}
            autoFocus
            onChange={(e) => onChangeField(e.target.value)}
            onBlur={() => onBlur(fieldName)}
            aria-label={`Edit ${ariaLabel}`}
          />
        )
      }
      return (
        <div
          role="button"
          tabIndex={0}
          className="cursor-text rounded px-2 py-1 hover:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          onClick={() => onStartEdit(fieldName, displayValue)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onStartEdit(fieldName, displayValue) }}
          aria-label={`${ariaLabel}: ${displayValue || "empty — click to add"}`}
        >
          {displayValue || <span className="text-zinc-500 italic">Click to add...</span>}
        </div>
      )
    }
    ```
  - [ ] T10.8: FSRS due status display logic:
    ```typescript
    function getFsrsStatus(fsrsState: string, due: string): string {
      if (fsrsState === "New") return "Not yet practiced"
      const dueDate = new Date(due)
      const now = new Date()
      if (dueDate <= now) return "Due now"
      const diffMs = dueDate.getTime() - now.getTime()
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
      return `Due in ${diffDays} day${diffDays === 1 ? "" : "s"}`
    }
    ```
  - [ ] T10.9: Delete confirmation Dialog using shadcn/ui `Dialog`:
    ```tsx
    <Dialog open={state === "confirm-delete"} onOpenChange={(open) => !open && setState("viewing")}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete card · This cannot be undone</DialogTitle>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setState("viewing")}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={() => { setState("deleting"); deleteCard.mutate() }}
            disabled={state === "deleting"}
          >
            {state === "deleting" ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    ```
  - [ ] T10.10: Audio player — use HTML `<audio>` element, NOT a library:
    ```tsx
    {card.audio_url && (
      <audio
        controls
        src={card.audio_url}
        className="h-8 w-full"
        aria-label={`Pronunciation audio for ${card.target_word}`}
      />
    )}
    ```
  - [ ] T10.11: Forms display — pretty-print JSON for editing; display as key-value pairs for viewing:
    ```typescript
    // For display: render forms as labeled pairs
    // For edit: JSON.stringify(card.forms, null, 2) as draft value in textarea
    const formsDraft = card.forms ? JSON.stringify(card.forms, null, 2) : "{}"
    ```

- [x] **T11: Update `frontend/src/features/cards/index.ts`** (AC: 1)
  ```typescript
  export { CardCreationPanel } from "./CardCreationPanel"
  export { CardDetail } from "./CardDetail"
  ```

- [x] **T12: Add "View card →" link in CardCreationPanel after save** (AC: 1)
  - [ ] T12.1: In `frontend/src/features/cards/CardCreationPanel.tsx`, in the "populated" state action row, add a TanStack Router `Link` to the card detail page. This requires storing `cardId` from the SSE `complete` event in component state.
  - [ ] T12.2: Update `CardCreationPanel` state: after `complete` event received, store `completedCardId` in local state.
  - [ ] T12.3: In the "populated" state render (save action row), add alongside the Save button:
    ```tsx
    {completedCardId && (
      <Link to="/cards/$cardId" params={{ cardId: String(completedCardId) }}
        className="text-sm text-zinc-400 hover:text-zinc-200 underline">
        View card →
      </Link>
    )}
    ```
  - [ ] T12.4: Ensure existing CardCreationPanel tests still pass — the "View card →" link is additive, not breaking.
  - [ ] T12.5: **IMPORTANT**: `CardCreationPanel.tsx` stores completedCardId in local state as `number | null`. It is reset to `null` when panel resets to "idle" state.

- [x] **T13: TypeScript + coverage validation** (AC: 7)
  - [ ] T13.1: `npx tsc --noEmit` — zero TypeScript errors (strict mode; no `any` types)
  - [ ] T13.2: `uv run pytest tests/api/test_cards.py -v` — all TestGetCard, TestPatchCard, TestDeleteCard tests pass
  - [ ] T13.3: `uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90` — stays above 90% gate
  - [ ] T13.4: `npm run test -- --coverage` — CardDetail.test.tsx all pass

- [x] **T14: Playwright E2E — Add card detail specs to `card-management.spec.ts`** (AC: 1–5)
  - [ ] T14.1: Create a Playwright helper in `e2e/fixtures/index.ts` to create a seed card:
    ```typescript
    export async function createSeedCard(request: APIRequestContext): Promise<number> {
      // Card creation via SSE — collect the stream and extract card_id from complete event
      const response = await request.post("/cards/stream", {
        data: { target_word: "prueba" },
        headers: { Accept: "text/event-stream" },
      })
      const body = await response.text()
      // Parse SSE events to find card_id
      const match = body.match(/"card_id":\s*(\d+)/)
      if (!match) throw new Error("No card_id in SSE response")
      return Number(match[1])
    }
    ```
  - [ ] T14.2: Add to `e2e/features/card-management.spec.ts`:
    - `test('view card detail via URL navigation')` — create seed card, navigate to `/cards/{id}`, verify target word visible
    - `test('edit translation inline')` — navigate to card detail, click translation, type new value, tab away, verify updated value persists (re-fetch or verify via API)
    - `test('add personal note')` — click note area, type note, blur, verify note persists
    - `test('delete card confirms then redirects')` — click Delete, confirm Dialog, verify redirect to home
    - `test('delete cancel does not remove card')` — click Delete, click Cancel, verify card still accessible
    - `test('keyboard navigation through card detail fields')` — Tab through all interactive fields, verify focus ring visible

---

## Dev Notes

### §WhatAlreadyExists — DO NOT Recreate

| Existing | Location | What it provides |
|---|---|---|
| `Card` SQLModel | `src/lingosips/db/models.py` | All columns including `personal_note`, `forms` (JSON str), `example_sentences` (JSON str), `audio_url`, `fsrs_state`, `due`, `deck_id`, `image_url`, `image_skipped` — all fields needed for `CardResponse` |
| `GET /cards/{card_id}/audio` endpoint | `src/lingosips/api/cards.py:47` | Existing audio endpoint — **do NOT modify**; new `GET /cards/{card_id}` goes before it |
| `AUDIO_DIR` constant | `src/lingosips/core/cards.py` AND imported in `src/lingosips/api/cards.py` | Both imports exist — do not confuse |
| `get_session` Depends | `src/lingosips/db/session.py` | Used by all new endpoints |
| `Dialog` shadcn/ui | `frontend/src/components/ui/dialog.tsx` | Already installed — `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` available |
| `Button` shadcn/ui | `frontend/src/components/ui/button.tsx` | `variant="destructive"` for Delete button, `variant="ghost"` for Cancel |
| `useAppStore.addNotification()` | `frontend/src/lib/stores/useAppStore.ts` | Error notification → Zustand → Toast flow — use this, never `alert()` |
| `QueryClient` + `QueryClientProvider` | `frontend/src/main.tsx` | Already configured globally |
| `ApiError` class | `frontend/src/lib/client.ts:12` | Already defined — use in `onError` handlers |
| `get()` function | `frontend/src/lib/client.ts:45` | Use for `GET /cards/{card_id}` |
| `del()` function | `frontend/src/lib/client.ts:70` | **Must be updated in T1** to handle 204 — currently calls `response.json()` which throws on empty body |
| `patch()` function | `frontend/src/lib/client.ts` | **Does NOT exist yet** — must be added in T1 |
| `conftest.py` fixtures | `tests/conftest.py` | `session`, `client`, `test_engine` — use these; do NOT create new session factory |
| `mock_llm_provider` fixture | `tests/api/test_cards.py:37` | Pattern: `app.dependency_overrides[dep] = lambda: mock` + `.pop()` at teardown (NOT `.clear()`) |
| `parse_sse_events()` helper | `tests/api/test_cards.py:85` | Reuse if you need to create cards via SSE in tests |
| TanStack Router `useNavigate` | `@tanstack/react-router` | Use for post-delete navigation |
| TanStack Router `Link` | `@tanstack/react-router` | Use for "View card →" link in CardCreationPanel |
| `useQuery` key `["cards", cardId]` | Architecture + project-context.md | Canonical key format for single card |
| `useQueryClient` for invalidation | `@tanstack/react-query` | Invalidate `["practice", "queue"]` after delete |
| `CardCreationPanel.tsx` | `frontend/src/features/cards/CardCreationPanel.tsx` | Existing 5-state component — T12 adds `completedCardId` state and "View card →" Link |

### §BackendDesign — Exact API Shapes

**`GET /cards/{card_id}` → 200 `CardResponse`:**
```json
{
  "id": 42,
  "target_word": "melancólico",
  "translation": "melancholic",
  "forms": {
    "gender": "masculine",
    "article": "el",
    "plural": "melancólicos",
    "conjugations": {}
  },
  "example_sentences": ["Tenía un aire melancólico.", "Era un día melancólico."],
  "audio_url": "/cards/42/audio",
  "personal_note": null,
  "image_url": null,
  "image_skipped": false,
  "card_type": "word",
  "deck_id": null,
  "target_language": "es",
  "fsrs_state": "New",
  "due": "2026-05-01T00:00:00Z",
  "stability": 0.0,
  "difficulty": 0.0,
  "reps": 0,
  "lapses": 0,
  "last_review": null,
  "created_at": "2026-05-01T00:00:00Z",
  "updated_at": "2026-05-01T00:00:00Z"
}
```

**CRITICAL**: `forms` and `example_sentences` are stored as JSON strings in SQLite but MUST be returned as parsed objects/arrays in `CardResponse`. The `_card_to_response()` helper handles this conversion. Never expose raw JSON strings in API responses.

**`PATCH /cards/{card_id}` → 200 `CardResponse`:**

Request body (send only what changed — Pydantic `model_fields_set` determines which fields to update):
```json
{ "translation": "gloomy" }
```

Response: same `CardResponse` shape as GET, with updated fields.

**`DELETE /cards/{card_id}` → 204 No Content:**

No response body. On success, the caller's `del()` function receives `undefined`.

**Route ordering in `api/cards.py`:**
```
@router.get("/{card_id}")          ← NEW (line ~60 — before audio)
@router.get("/{card_id}/audio")    ← EXISTING (line ~68)
@router.patch("/{card_id}")        ← NEW (line ~85)
@router.delete("/{card_id}")       ← NEW (line ~100)
@router.post("/stream")            ← EXISTING (keep at top or wherever it was)
```

FastAPI evaluates routes in declaration order. `/{card_id}/audio` is more specific, but `/{card_id}` matches any integer — if declared first, FastAPI will try to match both patterns and correctly prefers the more specific `/audio` sub-path. Place `/{card_id}` before `/{card_id}/audio` as they are different specificity levels and FastAPI handles this correctly.

### §PartialUpdatePattern — Why `model_fields_set` Matters

```python
# WRONG — all fields would overwrite DB values even if not sent
card.translation = request.translation   # request.translation is None if not sent → overwrites

# CORRECT — only update fields the client explicitly provided
if "translation" in request.model_fields_set:
    card.translation = request.translation

# This is critical for clearing a field:
# { "personal_note": null } → model_fields_set contains "personal_note", sets to None (clears)
# {}                        → model_fields_set is empty, note unchanged
```

### §JSONFieldHandling — forms and example_sentences in the DB

**DB storage (always strings):**
```python
card.forms = '{"gender": "masculine", "article": "el", "plural": "melancólicos", "conjugations": {}}'
card.example_sentences = '["Tenía un aire melancólico.", "Era un día melancólico."]'
```

**CardResponse (always parsed):**
```python
forms: CardFormsData | None     # parsed dict
example_sentences: list[str]    # parsed list
```

**PATCH request body → DB storage:**
```python
# If client sends {"forms": {"gender": "feminine", ...}}
# Router reads: request.forms = CardFormsData(gender="feminine", ...)
# Core writes: card.forms = json.dumps(request.forms.model_dump())

# If client sends {"example_sentences": ["New sentence 1.", "New sentence 2."]}
# Core writes: card.example_sentences = json.dumps(["New sentence 1.", "New sentence 2."])
```

### §InlineEditPattern — Frontend Field Editing UX

When a user clicks a field:
1. `setEditingField("translation")` — tracks which field is active
2. `setFieldDraft(card.translation ?? "")` — populate textarea/input with current value
3. Render `<input>` or `<textarea>` with `autoFocus`
4. On blur: call `commitEdit("translation")` → build PATCH body → `updateField.mutate(...)`
5. `setEditingField(null)` — revert to display mode immediately (optimistic)
6. TanStack Query cache updated via `onSuccess: (updated) => queryClient.setQueryData(["cards", cardId], updated)`

**Field-specific draft format:**
- `translation`: string (raw text)
- `personal_note`: string (raw text, allow empty → sends `null`)
- `example_sentences`: newline-separated string; on commit → `split("\n").filter(Boolean)`
- `forms`: JSON string (pretty-printed); on commit → `JSON.parse(draft)` with error handling

**Error on forms JSON parse failure:**
```typescript
// Do NOT silently drop the edit — show a notification
useAppStore.getState().addNotification({
  type: "error",
  message: "Forms field contains invalid JSON — edit not saved"
})
// Revert to viewing (field goes back to display mode)
```

### §CardDetailLayout — Visual Structure

```
← Back to home          [Delete card]
─────────────────────────────────────
melancólico               (target_word — non-editable display)
es · word                 (language · card_type)
─────────────────────────────────────
Translation               [FSRS: Not yet practiced]
  melancholic ← click to edit inline

Grammatical Forms
  {"gender":"masculine","article":"el","plural":"melancólicos"}  ← JSON textarea on edit

Example Sentences
  Tenía un aire melancólico.      ← one per line textarea on edit
  Era un día melancólico.

Audio
  [▶ play audio]                  ← <audio controls> element

Personal Note
  Click to add...                 ← <textarea> on click
```

Component structure: no shadcn/ui `Card` wrapping needed — plain `div` sections with `border-b border-zinc-800` separators. This is a page, not a card widget.

### §TestPatterns — Following Established Conventions

**From `tests/api/test_cards.py` (MUST follow same patterns):**

```python
# Use autouse fixture to clean DB between tests
@pytest.fixture(autouse=True)
async def truncate_cards(self, test_engine):
    async with test_engine.begin() as conn:
        await conn.execute(text("DELETE FROM cards"))

# Use seed_card fixture for integration tests (avoids LLM mock)
async def test_get_card_success(self, client: AsyncClient, seed_card: Card) -> None:
    response = await client.get(f"/cards/{seed_card.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == seed_card.id
    assert body["target_word"] == "melancólico"
    assert isinstance(body["forms"], dict)  # must be parsed, not a string

# RFC 7807 shape for 404
async def test_get_card_not_found(self, client: AsyncClient) -> None:
    response = await client.get("/cards/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "/errors/card-not-found"
    assert body["status"] == 404
    assert "99999" in body["detail"]

# Use .pop() NOT .clear() for dependency override teardown
app.dependency_overrides.pop(get_llm_provider, None)  # safe pop — don't break session override
```

**Frontend test pattern (from Story 1.10 learnings):**
```typescript
// Use findByText (async) not getByText (sync) for TanStack Query results
await screen.findByText("melancholic")

// Mock get using vi.mocked — never use (get as any)
vi.mocked(get).mockResolvedValue(MOCK_CARD)

// queryClient.clear() in afterEach to prevent test bleed
afterEach(() => queryClient.clear())

// Mock patch and del:
vi.mocked(patch).mockResolvedValue({ ...MOCK_CARD, translation: "gloomy" })
vi.mocked(del).mockResolvedValue(undefined)
```

### §ProjectStructureNotes — File Locations

**New files to create:**
```
src/lingosips/api/
└── cards.py                           ← MODIFIED: add CardResponse, CardUpdateRequest, CardFormsData,
                                         _card_to_response(), GET/PATCH/DELETE endpoints

src/lingosips/core/
└── cards.py                           ← MODIFIED: add get_card(), update_card(), delete_card()

tests/api/
└── test_cards.py                      ← MODIFIED: add TestGetCard, TestPatchCard, TestDeleteCard classes

frontend/src/features/cards/
├── CardDetail.tsx                     ← NEW: card detail + inline editing + delete confirmation
├── CardDetail.test.tsx                ← NEW: RTL tests for CardDetail
├── CardCreationPanel.tsx              ← MODIFIED: add completedCardId state + "View card →" Link
└── index.ts                           ← MODIFIED: export CardDetail

frontend/src/routes/
└── cards.$cardId.tsx                  ← NEW: TanStack Router dynamic route for card detail

frontend/src/lib/
├── client.ts                          ← MODIFIED: add patch(), update del() for 204
└── api.d.ts                           ← REGENERATED: after backend endpoints added

frontend/e2e/features/
└── card-management.spec.ts            ← MODIFIED: add card detail + edit + delete specs

frontend/e2e/fixtures/
└── index.ts                           ← MODIFIED: add createSeedCard() helper
```

**Component location:**
- `CardDetail.tsx` lives in `features/cards/` (not in `components/` — it is domain-specific, not shared)
- NOT exported from `components/ui/` — it is NOT a shadcn primitive
- The `EditableField` helper is internal to `CardDetail.tsx` — NOT exported from `index.ts`

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| `response.json()` in `del()` on 204 | Check `response.status === 204` and return `undefined` |
| `const [isEditing, setIsEditing] = useState(false)` | `const [editingField, setEditingField] = useState<string \| null>(null)` |
| Storing `CardResponse` in Zustand | TanStack Query owns card data — Zustand only for notifications and UI state |
| `card.forms = request.forms` | `card.forms = json.dumps(request.forms.model_dump()) if request.forms else None` |
| Updating all fields in PATCH regardless of body | Use `model_fields_set` to detect explicitly-provided fields only |
| `app.dependency_overrides.clear()` in test teardown | `app.dependency_overrides.pop(get_llm_provider, None)` — safe pop, never .clear() |
| `getByText()` for TanStack Query async data | `await screen.findByText()` — always await async query results |
| Adding business logic to `api/cards.py` router | All logic in `core/cards.py` — router only validates, delegates, converts errors |
| `SQLModel.metadata.create_all()` anywhere | Never — Alembic owns schema |
| Modal for edit fields | Inline editing only — Dialog reserved for delete confirmation only |
| Showing raw JSON string for `forms` in API response | Always parse JSON strings before returning `CardResponse` |

### §PreviousStoryIntelligence — From Stories 1.9, 1.10 Code Reviews

1. **Ruff E501 (line > 100 chars)**: All Python lines must stay ≤ 100 chars. Long docstrings and comments are the most common offenders. Watch all new functions in `core/cards.py` and `api/cards.py`.

2. **Ruff I001 (import sort) + E402 (import not at top)**: New imports in `api/cards.py` must be placed at the top of the file in isort order (stdlib → third-party → local), never mid-file. The `import json` and `from datetime import datetime` imports must go at the very top with other stdlib imports.

3. **Ruff F401 (unused import)**: Don't import `pytest` in test classes unless `@pytest.mark.foo` is used. Don't import `Response` from fastapi unless actually used in a route.

4. **aria-live always in DOM**: Not applicable to `CardDetail` (no live regions needed), but remember for any future component that uses `aria-live`.

5. **State machine over booleans**: `CardDetailState = "viewing" | "confirm-delete" | "deleting" | "error"` — never `const [isDeleting, setIsDeleting] = useState(false)`.

6. **`del()` vs `delete`**: `delete` is a reserved word in JS/TS. The existing client exports `del`. Use `del`, not `delete`.

7. **PATCH body only sends changed field**: The frontend sends the minimum payload — `{ translation: "new value" }` not the full card object. This is correct REST semantics and matches the backend's `model_fields_set` handling.

8. **`autoFocus` on edit inputs**: Use React's `autoFocus` prop on the inline `<input>`/`<textarea>`, not `useEffect` + `ref.focus()` — simpler and works correctly with SSR.

9. **TanStack Router file-based routing**: The route file `cards.$cardId.tsx` uses `$cardId` (not `:cardId`) as the TanStack Router dynamic segment syntax. `Route.useParams()` returns `{ cardId: string }` — convert to `Number()` before passing to component.

10. **Test teardown**: `afterEach(() => { queryClient.clear() })` in `CardDetail.test.tsx` to prevent test state bleed.

### §DeepContextFromPriorStories — What the DB Actually Stores

From `src/lingosips/core/cards.py` (existing implementation):
```python
# Card persisted with JSON-encoded fields:
card = Card(
    target_word=request.target_word,
    translation=card_data["translation"],
    forms=json.dumps(card_data["forms"]),           # stored as str
    example_sentences=json.dumps(card_data["example_sentences"]),  # stored as str
    target_language=target_language,
)
```

So when building `CardResponse` from a `Card` ORM object:
- `card.translation` → string (safe to return directly)
- `card.forms` → JSON string `'{"gender": "masculine", ...}'` → must parse to dict
- `card.example_sentences` → JSON string `'["Sentence 1", "Sentence 2"]'` → must parse to list

The `_card_to_response()` helper in T5.2 handles this correctly with try/except for malformed JSON (defensive parsing — a card with malformed JSON is still accessible, just with None/[] for that field).

### §RouteFileGeneration — TanStack Router routeTree

TanStack Router uses file-based route generation. Adding `routes/cards.$cardId.tsx` will require:
1. Creating the file
2. Running the TanStack Router CLI: `npx @tanstack/router-cli generate` (or it runs automatically via Vite plugin during `npm run dev`)
3. The `routeTree.gen.ts` file will be auto-updated — do NOT manually edit it

If the CLI doesn't auto-generate, check `vite.config.ts` for the TanStack Router Vite plugin configuration. If it's not running, run the generate command manually.

### References

- Story 2.1 acceptance criteria: [Source: _bmad-output/planning-artifacts/epics.md#Story 2.1]
- FR3 (personal note), FR4 (manual edit), FR6 (delete): [Source: _bmad-output/planning-artifacts/epics.md#Functional Requirements]
- `Card` SQLModel columns (forms, example_sentences, personal_note, fsrs_state, etc.): [Source: src/lingosips/db/models.py]
- `api/cards.py` existing endpoints + `AUDIO_DIR` import: [Source: src/lingosips/api/cards.py]
- `core/cards.py` JSON encoding pattern for forms/example_sentences: [Source: src/lingosips/core/cards.py:147-157]
- `client.ts` — `get`, `post`, `put`, `del` functions + `ApiError` class: [Source: frontend/src/lib/client.ts]
- `Dialog` shadcn/ui component: [Source: frontend/src/components/ui/dialog.tsx — already installed in Story 1.1]
- `useAppStore.addNotification()` error flow: [Source: _bmad-output/project-context.md#Error flow pattern]
- TanStack Query key `["cards", cardId]`: [Source: _bmad-output/project-context.md#TanStack Query key conventions]
- `model_fields_set` for PATCH partial updates: [Source: Pydantic v2 documentation — used to distinguish "not provided" from "provided as null"]
- `mock_llm_provider` fixture `.pop()` pattern: [Source: tests/api/test_cards.py:54]
- RFC 7807 error shape: [Source: _bmad-output/project-context.md#API Design Rules]
- Router delegates to core — no logic in router: [Source: _bmad-output/project-context.md#Layer Architecture & Boundaries]
- State machine (enum-driven, no booleans): [Source: _bmad-output/project-context.md#Component state machines]
- TDD mandatory, tests before implementation: [Source: _bmad-output/planning-artifacts/architecture.md#TDD Process]
- Ruff line length E501, import order I001/E402: [Source: 1-10-service-status-indicator.md#Review Findings]
- `del()` in client.ts returns via `response.json()` — breaks on 204: [Source: frontend/src/lib/client.ts:70-76 — current implementation]
- `patch()` does not exist in client.ts: [Source: frontend/src/lib/client.ts — only get, post, put, del defined]
- Route file naming convention `cards.$cardId.tsx`: [Source: _bmad-output/planning-artifacts/architecture.md#Frontend directory structure → routes/decks.$deckId.tsx]
- TanStack Router `useParams()`: [Source: TanStack Router docs — `Route.useParams()` returns typed params]
- `Dialog` UX rule (destructive confirmations only): [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Modal & Overlay Patterns]
- `variant="destructive"` for delete button: [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Button Hierarchy]
- `CardDetail.tsx` in features/cards/ (not components/): [Source: _bmad-output/planning-artifacts/architecture.md#Frontend directory structure → features/cards/CardDetail.tsx]
- Invalidate `["practice", "queue"]` on delete: [Source: _bmad-output/planning-artifacts/epics.md#Story 2.1 AC5]
- `autoFocus` on inline edit inputs: [Source: Project-context.md — React best practices for focus management]

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5

### Debug Log References

- UV_PROJECT_ENVIRONMENT verified as `/Users/oleksii/ai-projects/lingosips/.venv` (correct).
- Route ordering: `GET /{card_id}` placed before `GET /{card_id}/audio` — FastAPI correctly differentiates sub-paths.
- `CardCreationPanel.test.tsx` required `@tanstack/react-router` mock after `Link` import was added (T12). Added mock to fix 13 regressions.
- `seed_card` fixture: `Card` imported at module level (`from lingosips.db.models import Card`) to satisfy ruff F821.
- `api.d.ts` regenerated via `openapi-typescript` on port 7843 — confirmed `CardResponse`, `CardUpdateRequest`, `CardFormsData` schemas present.
- TanStack Router CLI (`@tanstack/router-cli generate`) ran to update `routeTree.gen.ts` with `/cards/$cardId` route.
- Added `DialogDescription` (sr-only) to silence Radix UI accessibility warning in tests.

### Completion Notes List

- ✅ T1: `patch<T>()` added to `client.ts`; `del<T>()` updated to short-circuit on 204 No Content.
- ✅ T2–T4: 17 new backend tests written (TDD — RED first), all pass after implementation.
- ✅ T5–T7: `CardFormsData`, `CardResponse`, `CardUpdateRequest` Pydantic models added to `api/cards.py`. `_card_to_response()` helper converts JSON string fields (forms, example_sentences) to parsed types. Three endpoints added: `GET/PATCH/DELETE /cards/{card_id}`. Route order: GET/{card_id} → GET/{card_id}/audio → PATCH → DELETE.
- ✅ T6: `get_card()`, `update_card()`, `delete_card()` added to `core/cards.py`. `model_fields_set` semantics in PATCH (only explicitly-provided fields updated).
- ✅ T8–T10: `CardDetail.tsx` implements enum state machine (`viewing | confirm-delete | deleting`), `EditableField` internal helper, TanStack Query for server state, PATCH mutation with optimistic cache update, DELETE mutation with navigation. All 11 RTL tests pass.
- ✅ T11–T12: `index.ts` exports `CardDetail`. `CardCreationPanel` tracks `completedCardId` from SSE complete event and shows "View card →" `Link` in populated state.
- ✅ T13: TypeScript strict check — 0 errors. Backend coverage 90.76% (gate: 90%). Frontend 133/133 tests pass. Ruff: all checks passed.
- ✅ T14: `card-management.spec.ts` created with 6 E2E specs covering AC1–5. `createSeedCard()` helper added to fixtures.

### File List

**Modified:**
- `frontend/src/lib/client.ts` — added `patch<T>()`, fixed `del<T>()` for 204
- `frontend/src/lib/api.d.ts` — regenerated (includes CardResponse, CardUpdateRequest, CardFormsData)
- `frontend/src/features/cards/index.ts` — exports CardDetail
- `frontend/src/features/cards/CardCreationPanel.tsx` — completedCardId state + "View card →" Link
- `frontend/src/features/cards/CardCreationPanel.test.tsx` — added @tanstack/react-router mock
- `src/lingosips/api/cards.py` — complete rewrite: CardFormsData, CardResponse, CardUpdateRequest, _card_to_response(), GET/PATCH/DELETE endpoints
- `src/lingosips/core/cards.py` — added get_card(), update_card(), delete_card()
- `tests/api/test_cards.py` — added Card import, seed_card fixture, TestGetCard, TestPatchCard, TestDeleteCard
- `frontend/src/routeTree.gen.ts` — auto-regenerated with /cards/$cardId route

**Created:**
- `frontend/src/features/cards/CardDetail.tsx` — card detail page component
- `frontend/src/features/cards/CardDetail.test.tsx` — RTL tests for CardDetail
- `frontend/src/routes/cards.$cardId.tsx` — TanStack Router dynamic route
- `frontend/e2e/features/card-management.spec.ts` — Playwright E2E specs
- `frontend/e2e/fixtures/index.ts` — added createSeedCard() helper

### Change Log

- **2026-05-01**: Story 2.1 implemented — card detail view, inline editing, personal notes, delete with confirmation. Added GET/PATCH/DELETE /cards/{card_id} backend endpoints with RFC 7807 error responses. Added CardDetail React component with enum-driven state machine. Added "View card →" navigation link in CardCreationPanel. (261 backend tests, 133 frontend tests — all pass.)
- **2026-05-01**: Code review completed — 8 patch findings applied, 0 deferred, 0 dismissed.

### Review Findings

- [x] [Review][Patch] `_card_to_response` doesn't catch `pydantic.ValidationError` [`src/lingosips/api/cards.py`] — Added `ValidationError` to the except clause so malformed-type forms JSON never causes an unhandled 500.
- [x] [Review][Patch] `CardDetailState` type incorrectly includes `"error"` as a local state value [`frontend/src/features/cards/CardDetail.tsx:71`] — Removed `"error"` from the type; loading/error are TanStack Query-derived, not local `useState` per spec.
- [x] [Review][Patch] PATCH `onError` fallback deviates from spec — `err.title` instead of `"Failed to save"` [`frontend/src/features/cards/CardDetail.tsx`] — Changed to `err.detail ?? "Failed to save"` per T10.4.
- [x] [Review][Patch] `← Back to home` uses plain `<a href="/">` instead of TanStack Router `Link` [`frontend/src/features/cards/CardDetail.tsx:260,279`] — Replaced both occurrences with `<Link to="/">` for SPA client-side navigation.
- [x] [Review][Patch] `conftest.py` uses `app.dependency_overrides.clear()` instead of `.pop()` [`tests/conftest.py:76`] — Changed to `app.dependency_overrides.pop(get_session, None)` per §AntiPatterns.
- [x] [Review][Patch] Misleading comment in `createSeedCard()` says "PATCH /cards" instead of "POST /cards/stream" [`frontend/e2e/fixtures/index.ts`] — Corrected comment.
- [x] [Review][Patch] Missing frontend test for PATCH `onError` notification path (T10.4) [`frontend/src/features/cards/CardDetail.test.tsx`] — Added `"shows error notification when patch fails"` test.
- [x] [Review][Patch] Missing frontend test for DELETE `onError` state-reset + notification path (T10.5) [`frontend/src/features/cards/CardDetail.test.tsx`] — Added `"resets state and shows notification when delete fails"` test.
- [x] [Review][Patch] Missing test for "View card →" link render in populated state (T12) [`frontend/src/features/cards/CardCreationPanel.test.tsx`] — Added `"renders 'View card →' link in populated state when card_id is set"` test.
