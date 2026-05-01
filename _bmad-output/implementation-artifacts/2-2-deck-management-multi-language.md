# Story 2.2: Deck Management & Multi-Language

Status: done

## Story

As a user,
I want to create, rename, delete, and browse decks — assign cards to decks and manage vocabulary across multiple target languages simultaneously,
so that I can organize my learning by topic, source, or language.

## Acceptance Criteria

1. **Given** I open the Decks screen
   **When** it loads
   **Then** `DeckGrid` shows all my decks with card count, due card count, and target language badge
   **And** decks are filterable by name (client-side filter on the loaded list)

2. **Given** I click "New deck"
   **When** I submit a deck name
   **Then** `POST /decks` creates the deck and it appears in DeckGrid immediately (TanStack Query cache update)

3. **Given** I rename a deck
   **When** I submit the new name
   **Then** `PATCH /decks/{deck_id}` updates it; the new name renders without a page reload

4. **Given** I delete a deck
   **When** I confirm deletion in the Dialog
   **Then** `DELETE /decks/{deck_id}` removes the deck; cards that were in it remain in the card collection (deck_id set to null, not deleted)

5. **Given** I save a card from the CardCreationPanel
   **When** the save action row is shown (populated state)
   **Then** a deck assignment dropdown lists my decks for the active language; selecting one assigns the card (`PATCH /cards/{card_id}` with `deck_id`) before the panel resets

6. **Given** I have multiple target languages configured
   **When** I switch the active target language via the language selector on the Decks page
   **Then** `PUT /settings` updates `active_target_language` and the deck browser reloads showing only decks for the selected language
   **And** the card creation panel uses the new active target language for subsequent cards

7. **Given** `POST /decks` is called with a name that already exists for the same target language
   **Then** a `409 Conflict` response is returned with an RFC 7807 body:
   `{"type": "/errors/deck-name-conflict", "title": "Deck name already exists", "status": 409, "detail": "A deck named '{name}' already exists for language '{lang}'"}`

8. **Given** I click "Discard" on a newly created card in the CardCreationPanel
   **When** the discard action triggers
   **Then** `DELETE /cards/{card_id}` removes the card from the DB (implements the TODO in `useCardStream.ts`)
   **And** the panel resets to idle state

9. **API tests must cover:** successful CRUD, 404 on missing deck, 409 on duplicate name within same language, duplicate name in different language succeeds, empty deck list returns `[]` not `null`, cards remain after deck deletion, card count and due count accurate.

## Tasks / Subtasks

> **TDD MANDATORY**: Write failing tests BEFORE writing implementation. All tasks marked [TDD] require tests first.

---

### Backend Tasks

- [x] **T1: Write failing backend tests for `GET /decks` [TDD — FIRST]** (AC: 1, 9)
  - [x] T1.1: Create `tests/api/test_decks.py` with shared fixtures:
    ```python
    """Tests for api/decks.py — CRUD + multi-language deck management."""
    import json
    import pytest
    from datetime import UTC, datetime, timedelta
    from httpx import AsyncClient
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from lingosips.api.app import app
    from lingosips.db.models import Card, Deck, Settings

    @pytest.fixture
    async def seed_settings(session: AsyncSession) -> Settings:
        """Insert a Settings row with two target languages configured."""
        s = Settings(
            native_language="en",
            active_target_language="es",
            target_languages='["es", "fr"]',
            onboarding_completed=True,
        )
        session.add(s)
        await session.commit()
        await session.refresh(s)
        return s

    @pytest.fixture
    async def seed_deck(session: AsyncSession) -> Deck:
        deck = Deck(name="Spanish Vocab", target_language="es")
        session.add(deck)
        await session.commit()
        await session.refresh(deck)
        return deck

    @pytest.fixture
    async def seed_deck_with_cards(session: AsyncSession) -> tuple[Deck, list[Card]]:
        """A deck with 3 cards, 2 of which are due."""
        deck = Deck(name="Deck With Cards", target_language="es")
        session.add(deck)
        await session.flush()  # get deck.id before creating cards
        now = datetime.now(UTC)
        cards = [
            Card(target_word="uno", target_language="es", deck_id=deck.id, due=now - timedelta(days=1)),
            Card(target_word="dos", target_language="es", deck_id=deck.id, due=now - timedelta(hours=1)),
            Card(target_word="tres", target_language="es", deck_id=deck.id, due=now + timedelta(days=3)),
        ]
        for c in cards:
            session.add(c)
        await session.commit()
        await session.refresh(deck)
        return deck, cards
    ```
  - [x] T1.2: Add `class TestListDecks:` with autouse truncation fixture:
    ```python
    class TestListDecks:
        @pytest.fixture(autouse=True)
        async def truncate(self, test_engine):
            async with test_engine.begin() as conn:
                await conn.execute(text("DELETE FROM cards"))
                await conn.execute(text("DELETE FROM decks"))
                await conn.execute(text("DELETE FROM settings"))

        async def test_list_decks_empty_returns_empty_list(self, client: AsyncClient): ...
        async def test_list_decks_filtered_by_target_language(self, client, seed_deck, ...): ...
        async def test_list_decks_other_language_not_returned(self, client, ...): ...
        async def test_list_decks_includes_accurate_card_count(self, client, seed_deck_with_cards): ...
        async def test_list_decks_includes_accurate_due_count(self, client, seed_deck_with_cards): ...
        async def test_list_decks_missing_target_language_returns_422(self, client): ...
        async def test_list_decks_ordered_by_name(self, client, ...): ...
    ```
  - [x] T1.3: Test cases verify response shape:
    ```json
    [{"id": 1, "name": "Spanish Vocab", "target_language": "es",
      "card_count": 3, "due_card_count": 2,
      "created_at": "...", "updated_at": "..."}]
    ```

- [x] **T2: Write failing backend tests for `POST /decks` [TDD — FIRST]** (AC: 2, 7, 9)
  - [x] T2.1: Add `class TestCreateDeck:` to `tests/api/test_decks.py`
  - [x] T2.2: Test cases:
    - `test_create_deck_success` — POST `{"name": "My Deck", "target_language": "es"}`, verify `201` + response shape
    - `test_create_deck_name_required_returns_422` — POST `{}`, verify `422`
    - `test_create_deck_empty_name_returns_422` — POST `{"name": "", ...}`, verify `422`
    - `test_create_deck_duplicate_name_same_language_returns_409` — seed deck, POST same name + lang, verify `409` RFC 7807
    - `test_create_deck_duplicate_name_different_language_succeeds` — seed "My Deck" for "es", POST "My Deck" for "fr", verify `201`
    - `test_create_deck_defaults_to_active_language` — create with no `target_language`, verify created with `active_target_language`
    - `test_create_deck_adds_language_to_settings_target_languages` — settings has `["es"]`, create deck for "fr", verify "fr" added to `target_languages`
    - `test_create_deck_name_stripped_of_whitespace` — POST `{"name": "  My Deck  "}`, verify saved as `"My Deck"`

- [x] **T3: Write failing backend tests for `PATCH /decks/{deck_id}` [TDD — FIRST]** (AC: 3, 9)
  - [x] T3.1: Add `class TestPatchDeck:` to `tests/api/test_decks.py`
  - [x] T3.2: Test cases:
    - `test_patch_deck_rename_success` — seed deck, PATCH `{"name": "New Name"}`, verify `200` + updated name
    - `test_patch_deck_not_found_returns_404` — PATCH `/decks/99999`, verify `404` RFC 7807
    - `test_patch_deck_duplicate_name_same_language_returns_409` — seed two decks, PATCH first to second's name, verify `409`
    - `test_patch_deck_duplicate_name_self_is_ok` — PATCH deck to its own name, verify `200` (not 409)
    - `test_patch_deck_empty_name_returns_422` — PATCH `{"name": ""}`, verify `422`
    - `test_patch_returns_updated_deck_response` — verify full DeckResponse shape returned

- [x] **T4: Write failing backend tests for `DELETE /decks/{deck_id}` [TDD — FIRST]** (AC: 4, 9)
  - [x] T4.1: Add `class TestDeleteDeck:` to `tests/api/test_decks.py`
  - [x] T4.2: Test cases:
    - `test_delete_deck_returns_204` — seed deck, DELETE, verify `204 No Content`
    - `test_delete_deck_not_found_returns_404` — DELETE `/decks/99999`, verify `404` RFC 7807
    - `test_delete_deck_cards_remain_with_null_deck_id` — seed deck + cards with deck_id, DELETE deck, verify cards still exist with `deck_id=None`
    - `test_delete_deck_and_refetch_returns_404` — DELETE then GET `/decks?target_language=es`, verify deck no longer appears

- [x] **T5: Create `src/lingosips/core/decks.py`** (AC: 1, 2, 3, 4)
  - [x] T5.1: Add `list_decks()` with card counts via a single aggregated SQL query (no N+1):
    ```python
    """Core deck management — no FastAPI, no SQLModel table-level imports except Card/Deck."""
    from datetime import UTC, datetime
    from sqlalchemy import func, case, select
    from sqlalchemy.ext.asyncio import AsyncSession
    from lingosips.db.models import Card, Deck, Settings

    async def list_decks(session: AsyncSession, target_language: str) -> list[dict]:
        """Return all decks for target_language with precomputed card_count and due_card_count."""
        now = datetime.now(UTC)
        stmt = (
            select(
                Deck,
                func.count(Card.id).label("card_count"),
                func.sum(case((Card.due <= now, 1), else_=0)).label("due_card_count"),
            )
            .outerjoin(Card, Card.deck_id == Deck.id)
            .where(Deck.target_language == target_language)
            .group_by(Deck.id)
            .order_by(Deck.name)
        )
        result = await session.execute(stmt)
        return [
            {"deck": row[0], "card_count": row[1], "due_card_count": int(row[2] or 0)}
            for row in result.all()
        ]
    ```
  - [x] T5.2: Add `get_deck()` — raises `ValueError` if not found (router converts to 404):
    ```python
    async def get_deck(deck_id: int, session: AsyncSession) -> Deck:
        result = await session.execute(select(Deck).where(Deck.id == deck_id))
        deck = result.scalar_one_or_none()
        if deck is None:
            raise ValueError(f"Deck {deck_id} does not exist")
        return deck
    ```
  - [x] T5.3: Add `create_deck()` — checks duplicate name + language, adds language to settings:
    ```python
    async def create_deck(
        name: str,
        target_language: str,
        session: AsyncSession,
    ) -> Deck:
        """Create a deck. Raises ValueError('conflict') if name+language already exists.

        Also adds target_language to Settings.target_languages if not already present.
        """
        import json
        # Duplicate check
        existing = await session.execute(
            select(Deck)
            .where(Deck.name == name, Deck.target_language == target_language)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("conflict")

        deck = Deck(name=name, target_language=target_language)
        session.add(deck)

        # Reconcile target_languages in settings (deferred from Story 1.4)
        result = await session.execute(select(Settings).limit(1))
        settings = result.scalars().first()
        if settings is not None:
            langs: list[str] = json.loads(settings.target_languages)
            if target_language not in langs:
                langs.append(target_language)
                settings.target_languages = json.dumps(langs)
                settings.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(deck)
        return deck
    ```
  - [x] T5.4: Add `update_deck()` — partial update, duplicate name check:
    ```python
    async def update_deck(
        deck_id: int,
        update_data: dict,
        session: AsyncSession,
    ) -> Deck:
        """Partially update a deck. Only keys in update_data are changed.
        Raises ValueError('not_found') if deck not found.
        Raises ValueError('conflict') on duplicate name + language.
        """
        deck = await get_deck(deck_id, session)

        if "name" in update_data:
            new_name = update_data["name"]
            # Only check for conflict if the name actually changed
            if new_name != deck.name:
                existing = await session.execute(
                    select(Deck).where(
                        Deck.name == new_name,
                        Deck.target_language == deck.target_language,
                        Deck.id != deck_id,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    raise ValueError("conflict")
            deck.name = new_name

        deck.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(deck)
        return deck
    ```
  - [x] T5.5: Add `delete_deck()` — nulls cards' deck_id before deletion:
    ```python
    async def delete_deck(deck_id: int, session: AsyncSession) -> None:
        """Delete a deck. Cards that belonged to it have deck_id set to None (not deleted).
        Raises ValueError if deck not found.
        """
        from sqlalchemy import update as sql_update
        deck = await get_deck(deck_id, session)
        # Null out deck_id on all cards in this deck (cards remain in collection)
        await session.execute(
            sql_update(Card).where(Card.deck_id == deck_id).values(deck_id=None)
        )
        await session.delete(deck)
        await session.commit()
    ```

- [x] **T6: Create `src/lingosips/api/decks.py`** (AC: 1, 2, 3, 4, 7)
  - [x] T6.1: Add Pydantic models:
    ```python
    """FastAPI router for deck CRUD — /decks endpoints.

    Router only — no business logic. Delegates to core.decks.*().
    """
    from datetime import datetime
    from fastapi import APIRouter, Depends, HTTPException, Query, Response
    from pydantic import BaseModel, Field
    from sqlalchemy.ext.asyncio import AsyncSession

    from lingosips.core import decks as core_decks
    from lingosips.core import settings as core_settings
    from lingosips.db.session import get_session

    router = APIRouter()


    class DeckResponse(BaseModel):
        """Full deck response — returned by all deck endpoints."""
        id: int
        name: str
        target_language: str
        card_count: int
        due_card_count: int
        created_at: datetime
        updated_at: datetime


    class DeckCreateRequest(BaseModel):
        name: str = Field(min_length=1, max_length=200)
        target_language: str | None = None  # defaults to active_target_language if omitted


    class DeckUpdateRequest(BaseModel):
        name: str | None = Field(default=None, min_length=1, max_length=200)
    ```
  - [x] T6.2: Add `_deck_row_to_response()` helper — converts the tuple from `list_decks()` to `DeckResponse`:
    ```python
    def _deck_row_to_response(row: dict) -> DeckResponse:
        deck = row["deck"]
        return DeckResponse(
            id=deck.id,
            name=deck.name,
            target_language=deck.target_language,
            card_count=row["card_count"],
            due_card_count=row["due_card_count"],
            created_at=deck.created_at,
            updated_at=deck.updated_at,
        )

    def _deck_to_response(deck, card_count: int = 0, due_card_count: int = 0) -> DeckResponse:
        """Convert a Deck ORM instance to DeckResponse — used by create/patch endpoints."""
        return DeckResponse(
            id=deck.id,
            name=deck.name,
            target_language=deck.target_language,
            card_count=card_count,
            due_card_count=due_card_count,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
        )
    ```
  - [x] T6.3: Add `GET /decks` endpoint:
    ```python
    @router.get("", response_model=list[DeckResponse])
    async def list_decks(
        target_language: str = Query(
            ...,
            min_length=2,
            max_length=10,
            description="BCP 47 language code — required",
        ),
        session: AsyncSession = Depends(get_session),
    ) -> list[DeckResponse]:
        """List all decks for a target language, with card and due counts.

        target_language is required (422 if absent) — no concept of "all languages at once."
        """
        rows = await core_decks.list_decks(session, target_language)
        return [_deck_row_to_response(r) for r in rows]
    ```
  - [x] T6.4: Add `POST /decks` endpoint (status_code=201):
    ```python
    @router.post("", response_model=DeckResponse, status_code=201)
    async def create_deck(
        request: DeckCreateRequest,
        session: AsyncSession = Depends(get_session),
    ) -> DeckResponse:
        """Create a new deck. Defaults target_language to active_target_language."""
        target_language = request.target_language
        if target_language is None:
            settings = await core_settings.get_or_create_settings(session)
            target_language = settings.active_target_language

        name = request.name.strip()
        try:
            deck = await core_decks.create_deck(name, target_language, session)
        except ValueError as exc:
            if "conflict" in str(exc):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "type": "/errors/deck-name-conflict",
                        "title": "Deck name already exists",
                        "status": 409,
                        "detail": (
                            f"A deck named '{name}' already exists for language '{target_language}'"
                        ),
                    },
                )
            raise
        return _deck_to_response(deck)
    ```
  - [x] T6.5: Add `PATCH /decks/{deck_id}` endpoint:
    ```python
    @router.patch("/{deck_id}", response_model=DeckResponse)
    async def patch_deck(
        deck_id: int,
        request: DeckUpdateRequest,
        session: AsyncSession = Depends(get_session),
    ) -> DeckResponse:
        """Rename a deck. Only fields present in the request body are changed."""
        update_data: dict = {}
        if "name" in request.model_fields_set and request.name is not None:
            update_data["name"] = request.name.strip()

        try:
            deck = await core_decks.update_deck(deck_id, update_data, session)
        except ValueError as exc:
            if "conflict" in str(exc):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "type": "/errors/deck-name-conflict",
                        "title": "Deck name already exists",
                        "status": 409,
                        "detail": f"A deck named '{update_data.get('name')}' already exists for this language",
                    },
                )
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "/errors/deck-not-found",
                    "title": "Deck not found",
                    "status": 404,
                    "detail": f"Deck {deck_id} does not exist",
                },
            )
        return _deck_to_response(deck)
    ```
  - [x] T6.6: Add `DELETE /decks/{deck_id}` endpoint:
    ```python
    @router.delete("/{deck_id}", status_code=204)
    async def delete_deck(
        deck_id: int,
        session: AsyncSession = Depends(get_session),
    ) -> Response:
        """Delete a deck. Cards belonging to it have deck_id nulled — not deleted."""
        try:
            await core_decks.delete_deck(deck_id, session)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "/errors/deck-not-found",
                    "title": "Deck not found",
                    "status": 404,
                    "detail": f"Deck {deck_id} does not exist",
                },
            )
        return Response(status_code=204)
    ```

- [x] **T7: Register decks router in `src/lingosips/api/app.py`** (AC: 1–4)
  - [x] T7.1: In `create_app()`, add:
    ```python
    from lingosips.api.decks import router as decks_router
    # ... (after other router imports)
    application.include_router(decks_router, prefix="/decks", tags=["decks"])
    ```
  - [x] T7.2: Place the `include_router` call **before** the static mount, after the existing routers. Order doesn't matter functionally but keep consistent with existing ordering (settings → models → cards → practice → services → **decks** → static).
  - [x] T7.3: Regenerate `frontend/src/lib/api.d.ts` after backend is complete:
    ```bash
    uv run uvicorn src.lingosips.api.app:app --port 7843 &
    npx openapi-typescript http://localhost:7843/openapi.json -o frontend/src/lib/api.d.ts
    kill %1
    ```

---

### Frontend Tasks

- [x] **T8: Write `frontend/src/features/decks/DeckGrid.test.tsx` [TDD — write FIRST]** (AC: 1, 2, 3, 4, 6)
  - [x] T8.1: Set up mocks:
    ```typescript
    import { vi, describe, it, expect, beforeEach, afterEach } from "vitest"
    import { render, screen, waitFor, fireEvent } from "@testing-library/react"
    import userEvent from "@testing-library/user-event"
    import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

    vi.mock("@/lib/client", () => ({
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
      del: vi.fn(),
      put: vi.fn(),
      ApiError: class ApiError extends Error {
        constructor(public status: number, public type: string, public title: string, public detail?: string) {
          super(title)
        }
      },
    }))
    vi.mock("@tanstack/react-router", () => ({
      useNavigate: () => vi.fn(),
      Link: ({ children, to }: { children: React.ReactNode; to: string }) => <a href={to}>{children}</a>,
    }))

    const MOCK_SETTINGS = {
      id: 1, native_language: "en", active_target_language: "es",
      target_languages: '["es","fr"]', onboarding_completed: true,
      auto_generate_audio: true, auto_generate_images: false,
      default_practice_mode: "self_assess", cards_per_session: 20,
    }
    const MOCK_DECK = {
      id: 1, name: "Spanish Vocab", target_language: "es",
      card_count: 5, due_card_count: 2,
      created_at: "2026-05-01T00:00:00Z", updated_at: "2026-05-01T00:00:00Z",
    }
    ```
  - [x] T8.2: Test cases:
    - `shows loading skeleton while fetching`
    - `renders empty state with create prompt when no decks`
    - `renders deck list with name, card count, due count, language badge`
    - `filters decks by name input (client-side)`
    - `create new deck form submits POST /decks`
    - `rename inline edit calls PATCH /decks/{id}`
    - `delete shows confirmation dialog then calls DELETE /decks/{id}`
    - `delete cancel does not call DELETE`
    - `language switcher calls PUT /settings with new active_target_language`
    - `deck card has link to /decks/$deckId route`
    - `aria-label on due count badge includes count`

- [x] **T9: Create `frontend/src/features/decks/DeckGrid.tsx`** (AC: 1, 2, 3, 4, 6)
  - [x] T9.1: Define state machine type:
    ```typescript
    type DeckGridState = "loading" | "loaded" | "empty" | "error"
    // DeckGridState is DERIVED from TanStack Query isLoading/isError/data
    // Local state for create form visibility:
    type CreateState = "hidden" | "open"
    ```
  - [x] T9.2: TanStack Query data fetching — settings + decks:
    ```typescript
    // Fetch settings first to get active_target_language
    const { data: settings } = useQuery({
      queryKey: ["settings"],
      queryFn: () => get<SettingsResponse>("/settings"),
    })
    const activeLanguage = settings?.active_target_language ?? "es"

    // Fetch decks for active language
    const { data: decks, isLoading, isError } = useQuery({
      queryKey: ["decks", activeLanguage],
      queryFn: () => get<DeckResponse[]>(`/decks?target_language=${activeLanguage}`),
      enabled: !!settings,  // don't fetch until settings loaded
    })
    ```
  - [x] T9.3: TanStack Query key for decks: `["decks", languageCode]` (per project-context.md conventions)
  - [x] T9.4: Create deck mutation:
    ```typescript
    const createDeck = useMutation({
      mutationFn: (name: string) =>
        post<DeckResponse>("/decks", { name, target_language: activeLanguage }),
      onSuccess: (newDeck) => {
        queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
          old ? [...old, newDeck].sort((a, b) => a.name.localeCompare(b.name)) : [newDeck]
        )
        setCreateState("hidden")
        setNewDeckName("")
      },
      onError: (error: ApiError) => {
        const message = error.status === 409
          ? `A deck named "${newDeckName}" already exists`
          : (error.detail ?? "Failed to create deck")
        useAppStore.getState().addNotification({ type: "error", message })
      },
    })
    ```
  - [x] T9.5: Rename deck mutation — use optimistic update:
    ```typescript
    const renameDeck = useMutation({
      mutationFn: ({ deckId, name }: { deckId: number; name: string }) =>
        patch<DeckResponse>(`/decks/${deckId}`, { name }),
      onSuccess: (updated) => {
        queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
          old
            ? old.map((d) => (d.id === updated.id ? updated : d))
                .sort((a, b) => a.name.localeCompare(b.name))
            : [updated]
        )
      },
      onError: (error: ApiError) => {
        useAppStore.getState().addNotification({
          type: "error",
          message: error.status === 409 ? "Deck name already exists" : (error.detail ?? "Failed to rename"),
        })
      },
    })
    ```
  - [x] T9.6: Delete deck mutation:
    ```typescript
    const deleteDeck = useMutation({
      mutationFn: (deckId: number) => del(`/decks/${deckId}`),
      onSuccess: (_, deckId) => {
        queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
          old ? old.filter((d) => d.id !== deckId) : []
        )
      },
      onError: (error: ApiError) => {
        useAppStore.getState().addNotification({
          type: "error",
          message: error.detail ?? "Failed to delete deck",
        })
      },
    })
    ```
  - [x] T9.7: Language switcher mutation:
    ```typescript
    const switchLanguage = useMutation({
      mutationFn: (langCode: string) =>
        put<SettingsResponse>("/settings", { active_target_language: langCode }),
      onSuccess: (updated) => {
        queryClient.setQueryData(["settings"], updated)
        // Deck list will auto-refetch because activeLanguage changed (query key changes)
      },
      onError: (error: ApiError) => {
        useAppStore.getState().addNotification({
          type: "error",
          message: error.detail ?? "Failed to switch language",
        })
      },
    })
    ```
  - [x] T9.8: Name filter — client-side, local state only:
    ```typescript
    const [filterText, setFilterText] = useState("")
    const filteredDecks = (decks ?? []).filter((d) =>
      d.name.toLowerCase().includes(filterText.toLowerCase())
    )
    ```
  - [x] T9.9: Layout structure:
    ```tsx
    <div className="p-4 md:p-8 flex flex-col gap-6">
      {/* Header: title + language switcher + new deck button */}
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-zinc-50">Decks</h1>
        <div className="flex items-center gap-3">
          {/* Language selector — only shown if target_languages has > 1 entry */}
          {availableLanguages.length > 1 && (
            <select
              aria-label="Active target language"
              value={activeLanguage}
              onChange={(e) => switchLanguage.mutate(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-50"
            >
              {availableLanguages.map((lang) => (
                <option key={lang} value={lang}>{lang.toUpperCase()}</option>
              ))}
            </select>
          )}
          <Button onClick={() => setCreateState("open")}>New deck</Button>
        </div>
      </div>

      {/* Search filter */}
      <Input
        placeholder="Filter decks by name..."
        aria-label="Filter decks by name"
        value={filterText}
        onChange={(e) => setFilterText(e.target.value)}
        className="max-w-sm"
      />

      {/* Create deck inline form */}
      {createState === "open" && (
        <CreateDeckForm
          onSubmit={(name) => createDeck.mutate(name)}
          onCancel={() => setCreateState("hidden")}
          isPending={createDeck.isPending}
        />
      )}

      {/* Deck grid */}
      {isLoading && <DeckGridSkeleton />}
      {isError && <p className="text-red-400">Failed to load decks</p>}
      {!isLoading && !isError && filteredDecks.length === 0 && (
        <EmptyDecksState hasFilter={!!filterText} />
      )}
      {!isLoading && !isError && filteredDecks.length > 0 && (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {filteredDecks.map((deck) => (
            <DeckCard
              key={deck.id}
              deck={deck}
              onRename={(name) => renameDeck.mutate({ deckId: deck.id, name })}
              onDelete={() => deleteDeck.mutate(deck.id)}
            />
          ))}
        </div>
      )}
    </div>
    ```
  - [x] T9.10: `availableLanguages` is derived from `settings.target_languages` (parsed JSON string):
    ```typescript
    const availableLanguages: string[] = settings
      ? JSON.parse(settings.target_languages)
      : [activeLanguage]
    ```

- [x] **T10: Create `frontend/src/features/decks/DeckCard.tsx`** (AC: 1, 2, 3, 4)
  - [x] T10.1: State machine:
    ```typescript
    type DeckCardState = "viewing" | "renaming" | "confirm-delete" | "deleting"
    ```
  - [x] T10.2: Component props:
    ```typescript
    interface DeckCardProps {
      deck: DeckResponse
      onRename: (newName: string) => void
      onDelete: () => void
    }
    ```
  - [x] T10.3: Use shadcn/ui `Card` as the container with a `Link` to `/decks/${deck.id}`:
    ```tsx
    <Card className="hover:border-zinc-700 transition-colors relative group">
      {/* Card body is a link to deck detail */}
      <Link to="/decks/$deckId" params={{ deckId: String(deck.id) }}
        className="block p-4 focus:outline-none focus:ring-1 focus:ring-indigo-500 rounded-lg">
        {/* Deck name — either display or inline edit input */}
        ...
        {/* Badges row */}
        <div className="flex gap-2 mt-2 flex-wrap">
          <Badge variant="secondary">{deck.target_language.toUpperCase()}</Badge>
          <Badge variant="outline">{deck.card_count} cards</Badge>
          {deck.due_card_count > 0 && (
            <Badge
              variant="outline"
              className="text-amber-500 border-amber-500"
              aria-label={`${deck.due_card_count} cards due for review`}
            >
              {deck.due_card_count} due
            </Badge>
          )}
        </div>
      </Link>
      {/* Action buttons — absolute positioned top-right (visible on group-hover) */}
      <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
        <Button variant="ghost" size="icon" aria-label={`Rename ${deck.name}`}
          onClick={() => setState("renaming")}>✏️</Button>
        <Button variant="ghost" size="icon" aria-label={`Delete ${deck.name}`}
          onClick={() => setState("confirm-delete")}>🗑️</Button>
      </div>
    </Card>
    ```
  - [x] T10.4: Inline rename — when `state === "renaming"`, replace the `Link` with:
    - An `<input>` with `autoFocus` pre-filled with `deck.name`
    - On blur or Enter: call `onRename(draft)` + `setState("viewing")`
    - On Escape: `setState("viewing")` without saving
    - Input must stop click propagation (prevent navigation while editing)
  - [x] T10.5: Delete confirmation Dialog (same pattern as CardDetail Story 2.1):
    ```tsx
    <Dialog open={state === "confirm-delete"} onOpenChange={(open) => !open && setState("viewing")}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete deck · This cannot be undone</DialogTitle>
          <DialogDescription className="sr-only">
            Cards in this deck will remain in your collection.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-zinc-400">
          Cards assigned to this deck will remain in your collection without a deck.
        </p>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setState("viewing")}>Cancel</Button>
          <Button
            variant="destructive"
            onClick={() => { setState("deleting"); onDelete() }}
            disabled={state === "deleting"}
          >
            {state === "deleting" ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    ```
  - [x] T10.6: **IMPORTANT**: Use `e.stopPropagation()` and `e.preventDefault()` on rename/delete button clicks to prevent the Card's Link navigation from triggering.

- [x] **T11: Create internal `CreateDeckForm` component (inline in `DeckGrid.tsx`)** (AC: 2)
  - [x] T11.1: Simple form with name input + submit + cancel:
    ```tsx
    function CreateDeckForm({ onSubmit, onCancel, isPending }: CreateDeckFormProps) {
      const [name, setName] = useState("")
      return (
        <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()) }}
          className="flex gap-2 items-center max-w-sm border border-zinc-700 rounded-lg p-3">
          <Input
            autoFocus
            placeholder="Deck name..."
            aria-label="New deck name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
          />
          <Button type="submit" disabled={!name.trim() || isPending} size="sm">
            {isPending ? "Creating..." : "Create"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
        </form>
      )
    }
    ```

- [x] **T12: Create `frontend/src/features/decks/index.ts`** (AC: 1)
  ```typescript
  export { DeckGrid } from "./DeckGrid"
  export type { DeckResponse } from "./DeckGrid"
  ```

- [x] **T13: Create `frontend/src/routes/decks.tsx`** (AC: 1)
  ```typescript
  import { createFileRoute } from "@tanstack/react-router"
  import { DeckGrid } from "../features/decks"

  export const Route = createFileRoute("/decks")({
    component: DecksPage,
  })

  function DecksPage() {
    return <DeckGrid />
  }
  ```

- [x] **T14: Create `frontend/src/routes/decks.$deckId.tsx`** (stub for this story) (AC: 1)
  ```typescript
  import { createFileRoute } from "@tanstack/react-router"
  import { useQuery } from "@tanstack/react-query"
  import { get } from "@/lib/client"

  export const Route = createFileRoute("/decks/$deckId")({
    component: DeckDetailPage,
  })

  function DeckDetailPage() {
    const { deckId } = Route.useParams()
    // Stub: full card-in-deck listing is a future story
    return (
      <div className="p-4 md:p-8">
        <p className="text-zinc-400 text-sm">Deck detail — coming in a future story.</p>
      </div>
    )
  }
  ```

- [x] **T15: Add Decks nav item to `IconSidebar.tsx` and `BottomNav.tsx`** (AC: 1)
  - [x] T15.1: In `frontend/src/components/layout/IconSidebar.tsx`:
    - Import `LibraryBig` (or `FolderOpen`) from `lucide-react`
    - Add to `NAV_ITEMS` after Home, before Practice:
      `{ to: "/decks", icon: LibraryBig, label: "Decks", ariaLabel: "Decks — vocabulary organization" }`
  - [x] T15.2: In `frontend/src/components/layout/BottomNav.tsx`:
    - Add same Decks entry to NAV_ITEMS
    - **Note**: This brings BottomNav to 6 items, exceeding the UX spec's "5 icons max" guideline. The dev should also check if `IconSidebar.test.tsx` and `BottomNav.test.tsx` need updating to account for the new nav item.
  - [x] T15.3: Run `npx @tanstack/router-cli generate` (or it auto-generates via Vite plugin) to update `routeTree.gen.ts` with `/decks` and `/decks/$deckId` routes.

- [x] **T16: Update `CardCreationPanel.tsx` — add deck assignment dropdown + fix discard** (AC: 5, 8)
  - [x] T16.1: Add deck list query (only when in "populated" state to avoid unnecessary requests):
    ```typescript
    // In CardCreationPanel — fetch settings to get activeLanguage
    const { data: settings } = useQuery({
      queryKey: ["settings"],
      queryFn: () => get<SettingsResponse>("/settings"),
    })
    const activeLanguage = settings?.active_target_language ?? "es"

    // Fetch decks for deck assignment dropdown — only in populated state
    const { data: deckOptions } = useQuery({
      queryKey: ["decks", activeLanguage],
      queryFn: () => get<DeckResponse[]>(`/decks?target_language=${activeLanguage}`),
      enabled: state === "populated",  // only fetch when action row is visible
    })
    ```
  - [x] T16.2: Add `selectedDeckId` local state:
    ```typescript
    const [selectedDeckId, setSelectedDeckId] = useState<number | null>(null)
    // Reset on state change to idle
    useEffect(() => {
      if (state === "idle") setSelectedDeckId(null)
    }, [state])
    ```
  - [x] T16.3: Add deck selector to the action row (populated state):
    ```tsx
    {showActionRow && (
      <div className="flex gap-2 items-center justify-end flex-wrap">
        {/* Deck assignment dropdown */}
        {deckOptions && deckOptions.length > 0 && (
          <select
            aria-label="Assign to deck (optional)"
            value={selectedDeckId ?? ""}
            onChange={(e) => setSelectedDeckId(e.target.value ? Number(e.target.value) : null)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-50"
          >
            <option value="">No deck</option>
            {deckOptions.map((deck) => (
              <option key={deck.id} value={deck.id}>{deck.name}</option>
            ))}
          </select>
        )}
        <Button variant="ghost" onClick={handleDiscard}>Discard</Button>
        {completedCardId != null && (
          <Link to="/cards/$cardId" params={{ cardId: String(completedCardId) }}
            className="text-sm text-zinc-400 hover:text-zinc-200 underline">
            View card →
          </Link>
        )}
        <Button onClick={handleSave} disabled={state === "saving"}>Save card</Button>
      </div>
    )}
    ```
  - [x] T16.4: Replace `onClick={saveCard}` with `onClick={handleSave}` — async handler that patches deck assignment:
    ```typescript
    async function handleSave() {
      if (selectedDeckId != null && completedCardId != null) {
        try {
          await patch(`/cards/${completedCardId}`, { deck_id: selectedDeckId })
          queryClient.invalidateQueries({ queryKey: ["decks", activeLanguage] })
        } catch {
          // Non-fatal: card already saved; deck assignment failed — show warning
          useAppStore.getState().addNotification({
            type: "error",
            message: "Card saved, but deck assignment failed. Edit from the card detail page.",
          })
        }
      }
      saveCard()
    }
    ```
  - [x] T16.5: Replace `onClick={discard}` with `onClick={handleDiscard}` — implement the TODO that removes the card:
    ```typescript
    async function handleDiscard() {
      if (completedCardId != null) {
        try {
          await del(`/cards/${completedCardId}`)
          queryClient.invalidateQueries({ queryKey: ["cards"] })
        } catch {
          // Non-fatal: just reset the panel; orphaned card is benign
        }
      }
      discard()
    }
    ```
  - [x] T16.6: Add needed imports: `useQuery`, `useQueryClient` from `@tanstack/react-query`; `patch`, `del` from `@/lib/client`; `useAppStore` from `@/lib/stores/useAppStore`; `DeckResponse` type from `@/features/decks`.
  - [x] T16.7: **IMPORTANT**: The `queryClient` must be obtained via `useQueryClient()` at the top of the component — not from a module-level import. Add `const queryClient = useQueryClient()` to the component.

- [x] **T17: TypeScript + coverage validation** (AC: 9)
  - [x] T17.1: `npx tsc --noEmit` — zero TypeScript errors
  - [x] T17.2: `uv run pytest tests/api/test_decks.py -v` — all deck test classes pass
  - [x] T17.3: `uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90` — stays above 90% gate
  - [x] T17.4: `npm run test -- --coverage` — DeckGrid.test.tsx all pass; CardCreationPanel.test.tsx regressions fixed
  - [x] T17.5: `uv run ruff check src/` — no ruff violations (watch line length ≤100, import sort)

- [x] **T18: Playwright E2E — deck management specs** (AC: 1–6)
  - [x] T18.1: Create `frontend/e2e/features/deck-management.spec.ts`:
    - `test('browse decks screen — empty state')` — navigate to `/decks`, verify "No decks yet" or empty message
    - `test('create deck and see it in grid')` — click "New deck", enter name, submit, verify deck card appears
    - `test('rename deck inline')` — create deck, click rename button, type new name, confirm, verify updated
    - `test('delete deck removes it but cards remain')` — create deck, assign a card, delete deck, verify deck gone, verify card still accessible at `/cards/{id}`
    - `test('deck card shows card count badge')` — create deck with cards, verify count badge renders
    - `test('filter decks by name')` — create 3 decks, type partial name in filter, verify only matching deck shown
    - `test('assign card to deck on creation')` — create deck, create card via panel, select deck in dropdown, save, verify card has deck_id
    - `test('discard removes card from collection')` — stream a card, click Discard, verify card no longer accessible at `/cards/{id}`
    - `test('keyboard navigation through deck grid')` — Tab to New Deck button, Enter to open form, Tab to input, type, Tab to Create, Enter
  - [x] T18.2: Add `createSeedDeck()` helper to `frontend/e2e/fixtures/index.ts`:
    ```typescript
    export async function createSeedDeck(request: APIRequestContext, name: string, lang = "es"): Promise<number> {
      const response = await request.post("/decks", {
        data: { name, target_language: lang },
        headers: { "Content-Type": "application/json", Accept: "application/json" },
      })
      const body = await response.json()
      return body.id as number
    }
    ```

---

## Dev Notes

### §WhatAlreadyExists — DO NOT Recreate

| Existing | Location | What it provides |
|---|---|---|
| `Deck` SQLModel | `src/lingosips/db/models.py:45` | `id`, `name`, `target_language`, `settings_overrides`, `created_at`, `updated_at` — all columns needed |
| `Card.deck_id` FK | `src/lingosips/db/models.py:30` | `deck_id: int \| None = Field(default=None, foreign_key="decks.id", index=True)` — already exists |
| `PATCH /cards/{card_id}` with `deck_id` | `src/lingosips/api/cards.py` + `CardUpdateRequest` | Already handles `deck_id` field — Story 2.1 added this. No changes needed to `api/cards.py` |
| `get_session` Depends | `src/lingosips/db/session.py` | Used by all new endpoints |
| `get_or_create_settings()` | `src/lingosips/core/settings.py:59` | Use for fetching active_target_language in deck router |
| `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`, `DialogDescription` | `frontend/src/components/ui/dialog.tsx` | Already installed — use same delete confirmation pattern as CardDetail |
| `Button` shadcn/ui | `frontend/src/components/ui/button.tsx` | `variant="destructive"` for Delete button |
| `Input` shadcn/ui | `frontend/src/components/ui/input.tsx` | For deck name inputs |
| `Card`, `CardHeader`, `CardContent` shadcn/ui | `frontend/src/components/ui/card.tsx` | Use for DeckCard layout |
| `Badge` shadcn/ui | `frontend/src/components/ui/badge.tsx` | For language badge, card count, due count |
| `Skeleton` shadcn/ui | `frontend/src/components/ui/skeleton.tsx` | For loading state in DeckGrid |
| `useAppStore.addNotification()` | `frontend/src/lib/stores/useAppStore.ts` | Error notification → Zustand → Toast flow |
| `patch()` function | `frontend/src/lib/client.ts:70` | Added in Story 2.1 — use for PATCH /cards + PATCH /decks |
| `del()` function | `frontend/src/lib/client.ts:79` | Fixed in Story 2.1 for 204 — use for DELETE /decks + DELETE /cards |
| `put()` function | `frontend/src/lib/client.ts:61` | Use for `PUT /settings` language switch |
| `post()` function | `frontend/src/lib/client.ts:52` | Use for `POST /decks` |
| `ApiError` class | `frontend/src/lib/client.ts:12` | In `onError` handlers for 409 conflict detection |
| `conftest.py` fixtures | `tests/conftest.py` | `session`, `client`, `test_engine` — use these; never create new session factory |
| `seed_card` fixture pattern | `tests/api/test_cards.py:82` | Pattern for creating seed data — replicate for `seed_deck` |
| `.pop()` NOT `.clear()` for dependency override teardown | `tests/conftest.py:76` | Always use `app.dependency_overrides.pop(dep, None)` |
| `CardCreationPanel.tsx` + `useCardStream.ts` | `frontend/src/features/cards/` | Must add `handleSave` and `handleDiscard` async wrappers without breaking existing 5-state machine |
| TanStack Query key `["decks", langCode]` | architecture | Canonical key format for deck list per language |
| TanStack Query key `["settings"]` | `__root.tsx` + project-context.md | Already fetched globally — use `useQuery(["settings"])` to share cache |
| `Settings.target_languages` | `src/lingosips/db/models.py:61` | JSON string `'["es"]'` — stored as str, parse with `json.loads()` |
| `Settings.active_target_language` | `src/lingosips/db/models.py:63` | The currently active one — used for filtering decks |

### §BackendDesign — Exact API Shapes

**`GET /decks?target_language=es` → 200 `list[DeckResponse]`:**
```json
[
  {
    "id": 1,
    "name": "Spanish Vocab",
    "target_language": "es",
    "card_count": 5,
    "due_card_count": 2,
    "created_at": "2026-05-01T00:00:00Z",
    "updated_at": "2026-05-01T00:00:00Z"
  }
]
```
Empty result: `[]` — never `null`.

**`POST /decks` → 201 `DeckResponse`:**
```json
// Request body:
{ "name": "Travel Phrases", "target_language": "es" }
// Or without target_language — defaults to active_target_language:
{ "name": "Travel Phrases" }

// Response (201 Created):
{ "id": 2, "name": "Travel Phrases", "target_language": "es", "card_count": 0, "due_card_count": 0, ... }
```

**`PATCH /decks/{deck_id}` → 200 `DeckResponse`:**
```json
// Request: { "name": "New Name" }
// Response: full DeckResponse with updated name (card_count + due_card_count = 0 post-rename — OK)
```
> Note: `card_count` and `due_card_count` in PATCH response are `0` because `_deck_to_response()` doesn't compute them. This is acceptable — the frontend updates its cache directly from the mutation response or re-fetches.

**`DELETE /decks/{deck_id}` → 204 No Content**

**`409 Conflict` RFC 7807 body:**
```json
{
  "type": "/errors/deck-name-conflict",
  "title": "Deck name already exists",
  "status": 409,
  "detail": "A deck named 'Spanish Vocab' already exists for language 'es'"
}
```

**`404 Not Found` RFC 7807 body:**
```json
{
  "type": "/errors/deck-not-found",
  "title": "Deck not found",
  "status": 404,
  "detail": "Deck 99999 does not exist"
}
```

### §SQLAlchemyAggregationPattern — Card Count Query

The `list_decks()` function uses a single aggregated SQL query to avoid N+1 queries:

```python
from sqlalchemy import func, case, select
from datetime import UTC, datetime

now = datetime.now(UTC)
stmt = (
    select(
        Deck,
        func.count(Card.id).label("card_count"),
        func.sum(case((Card.due <= now, 1), else_=0)).label("due_card_count"),
    )
    .outerjoin(Card, Card.deck_id == Deck.id)
    .where(Deck.target_language == target_language)
    .group_by(Deck.id)
    .order_by(Deck.name)
)
result = await session.execute(stmt)
# Each row is a tuple: (Deck ORM object, card_count int, due_card_count int|None)
```

**IMPORTANT**: `func.sum()` returns `None` when all cards are not-due (the SUM of an empty set). Always use `int(row[2] or 0)` to convert `None → 0`.

**IMPORTANT**: `outerjoin` (not `join`) — ensures decks with 0 cards are included.

### §DeckDeletionPattern — Cards Survive Deck Deletion

SQLite does not enforce FK constraints by default. Even so, implement explicit nulling to be explicit and portable:

```python
from sqlalchemy import update as sql_update

# Before deleting the deck, null out all cards referencing it
await session.execute(
    sql_update(Card).where(Card.deck_id == deck_id).values(deck_id=None)
)
await session.delete(deck)
await session.commit()
```

Do NOT rely on SQLite's implicit behavior. The explicit null ensures correctness regardless of FK pragma settings.

### §MultiLanguagePattern — target_languages Reconciliation

`Settings.target_languages` is a JSON string list of all languages the user has ever created a deck for. `Settings.active_target_language` is the currently viewed one.

When a deck is created for language "fr" and `target_languages` only contains `["es"]`, `create_deck()` must add "fr" to the list:

```python
import json
settings = ... # fetch settings row
langs: list[str] = json.loads(settings.target_languages)
if target_language not in langs:
    langs.append(target_language)
    settings.target_languages = json.dumps(langs)
    settings.updated_at = datetime.now(UTC)
```

This resolves the deferred item from Story 1.4 code review: "target_languages not synced with active_target_language."

### §CardAssignmentPattern — PATCH /cards/{card_id}

Card-to-deck assignment in `CardCreationPanel` is done via the existing `PATCH /cards/{card_id}` endpoint (Story 2.1). The `CardUpdateRequest` already supports `deck_id`:

```typescript
// In handleSave() — only called if user selected a deck
await patch(`/cards/${completedCardId}`, { deck_id: selectedDeckId })
```

This does NOT modify `api/cards.py`. Only `CardCreationPanel.tsx` is modified.

### §DiscardPattern — Implementing the Story 2.1 TODO

`useCardStream.ts` has a TODO comment on `discard()`:
```typescript
// TODO Story 2.1: call DELETE /cards/${fields.card_id} to actually remove the card
```

Story 2.2 implements this by adding `handleDiscard` in `CardCreationPanel.tsx` (NOT in `useCardStream.ts`). The hook's `discard()` function is called after the DELETE completes. This avoids changing the hook's contract:

```typescript
// In CardCreationPanel — do NOT modify useCardStream.ts
async function handleDiscard() {
  const cardId = fields.card_id  // access from the hook's fields
  if (cardId != null) {
    try {
      await del(`/cards/${cardId}`)
      queryClient.invalidateQueries({ queryKey: ["cards"] })
    } catch { /* non-fatal */ }
  }
  discard()  // useCardStream.ts discard() resets state
}
```

**IMPORTANT**: `fields` is returned from `useCardStream()`. `fields.card_id` is set when the SSE `complete` event fires. In the "populated" state (where Discard is shown), `fields.card_id` will always be set.

### §DeckGridState — No Separate State Machine Needed

Unlike `CardDetail` which manages a complex local state, `DeckGrid`'s states are fully derived from TanStack Query:
- `loading`: `isLoading === true`
- `error`: `isError === true`
- `empty`: `data !== undefined && data.length === 0`
- `loaded`: `data !== undefined && data.length > 0`

Only `createState: "hidden" | "open"` is local UI state.

The `DeckCard` component manages its own state machine (`viewing | renaming | confirm-delete | deleting`) internally.

### §TanStackQueryInvalidation — Cache Update Strategy

**On Create Deck**: Use `setQueryData` to optimistically add to cache, avoiding a refetch:
```typescript
queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
  old ? [...old, newDeck].sort((a, b) => a.name.localeCompare(b.name)) : [newDeck]
)
```

**On Rename Deck**: Use `setQueryData` to optimistically update:
```typescript
queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
  old ? old.map((d) => d.id === updated.id ? updated : d).sort(...) : [updated]
)
```

**On Delete Deck**: Use `setQueryData` to remove from cache:
```typescript
queryClient.setQueryData<DeckResponse[]>(["decks", activeLanguage], (old) =>
  old ? old.filter((d) => d.id !== deckId) : []
)
```

**On Language Switch**: The query key `["decks", activeLanguage]` changes, so TanStack Query automatically fetches the new language's decks. No manual invalidation needed.

### §RouteGeneration — TanStack Router Auto-Discovery

Creating `routes/decks.tsx` and `routes/decks.$deckId.tsx` will cause TanStack Router to auto-update `routeTree.gen.ts` during `npm run dev`. If Vite plugin isn't updating it:
```bash
npx @tanstack/router-cli generate
```

Do NOT manually edit `routeTree.gen.ts`.

### §NavItemLucideIcon — Choosing the Deck Icon

The `lucide-react` package is already installed. Use `LibraryBig` or `BookMarked` for Decks:
```typescript
import { Home, BookOpen, LibraryBig, Upload, BarChart3, Settings } from "lucide-react"
```

Check if the icon is available in the version currently installed: run `grep lucide-react frontend/package.json` to verify version, then check the lucide-react icon list for that version.

### §TestPatterns — Following Established Conventions

**Backend test structure (from `tests/api/test_cards.py`):**
```python
# Autouse fixture to clean tables between tests
@pytest.fixture(autouse=True)
async def truncate(self, test_engine):
    async with test_engine.begin() as conn:
        await conn.execute(text("DELETE FROM cards"))
        await conn.execute(text("DELETE FROM decks"))
        await conn.execute(text("DELETE FROM settings"))

# RFC 7807 shape for 409
async def test_create_deck_duplicate_returns_409(self, client):
    response = await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
    assert response.status_code == 201
    response2 = await client.post("/decks", json={"name": "My Deck", "target_language": "es"})
    assert response2.status_code == 409
    body = response2.json()
    assert body["type"] == "/errors/deck-name-conflict"
    assert body["status"] == 409
```

**Frontend test pattern (from `CardDetail.test.tsx`):**
```typescript
// Always findByText (async) not getByText (sync) for TanStack Query results
await screen.findByText("Spanish Vocab")

// queryClient.clear() in afterEach
afterEach(() => queryClient.clear())

// Mock get using vi.mocked
vi.mocked(get).mockResolvedValue([MOCK_DECK])  // GET /decks returns array

// For 409 conflict:
vi.mocked(post).mockRejectedValue(
  new ApiError(409, "/errors/deck-name-conflict", "Deck name already exists", "...")
)
```

### §PreviousStoryIntelligence — From Story 2.1 Code Review

1. **Ruff E501 (line > 100 chars)**: All Python lines ≤ 100 chars. Watch long `raise HTTPException(...)` calls — spread across multiple lines.

2. **Ruff I001 (import sort)**: `from sqlalchemy import ...` imports must be at the top in isort order. The `from sqlalchemy import func, case, select, update as sql_update` in `core/decks.py` must go at module top, not inside functions.

3. **`model_fields_set` for PATCH**: Only update fields explicitly provided in request body. `DeckUpdateRequest` has only `name` — use `if "name" in request.model_fields_set`.

4. **`autoFocus` on rename inputs**: Use React's `autoFocus` prop, not `useEffect` + ref.

5. **Stop click propagation**: Rename/delete buttons inside a `Link` must call `e.stopPropagation()` to prevent navigation while editing.

6. **`DialogDescription` (sr-only) for Radix accessibility**: Silences the Radix UI accessibility warning in tests. Add `<DialogDescription className="sr-only">...</DialogDescription>` to the delete confirmation Dialog.

7. **TanStack Router `useParams()`**: Route file `decks.$deckId.tsx` uses `$deckId` syntax. `Route.useParams()` returns `{ deckId: string }` — use `Number(deckId)` to convert.

8. **`put()` vs `patch()`**: Settings update uses `put()` (existing `PUT /settings` endpoint). Deck rename uses `patch()` (new `PATCH /decks/{deck_id}` endpoint). Don't confuse them.

9. **`POST /decks` returns 201**: Unlike PATCH which returns 200, create endpoints use status 201. Ensure `status_code=201` in the FastAPI router decorator.

10. **`func.sum()` can return `None`**: Always coerce with `int(row[2] or 0)` when using `func.sum()` in aggregate queries — SQLAlchemy returns `None` not `0` for empty sums.

### §ProjectStructureNotes — New and Modified Files

**New files:**
```
src/lingosips/api/decks.py                   ← NEW: deck CRUD router
src/lingosips/core/decks.py                  ← NEW: deck business logic
tests/api/test_decks.py                      ← NEW: TDD backend tests

frontend/src/features/decks/
├── DeckGrid.tsx                             ← NEW: deck browser + create/rename/delete
├── DeckCard.tsx                             ← NEW: individual deck card component
├── DeckGrid.test.tsx                        ← NEW: RTL tests
└── index.ts                                 ← NEW: public exports

frontend/src/routes/decks.tsx                ← NEW: /decks route
frontend/src/routes/decks.$deckId.tsx        ← NEW: /decks/$deckId stub route
frontend/e2e/features/deck-management.spec.ts ← NEW: Playwright E2E
```

**Modified files:**
```
src/lingosips/api/app.py                     ← MODIFIED: add decks router registration
frontend/src/components/layout/IconSidebar.tsx ← MODIFIED: add Decks nav item
frontend/src/components/layout/BottomNav.tsx ← MODIFIED: add Decks nav item
frontend/src/features/cards/CardCreationPanel.tsx ← MODIFIED: deck dropdown + handleSave/handleDiscard
frontend/src/lib/api.d.ts                    ← REGENERATED
frontend/src/routeTree.gen.ts                ← AUTO-REGENERATED by TanStack Router CLI
```

**DO NOT modify:**
- `src/lingosips/api/cards.py` — PATCH /cards/{card_id} already handles deck_id
- `src/lingosips/db/models.py` — Deck table already defined
- `src/lingosips/core/cards.py` — no changes needed
- `frontend/src/features/cards/useCardStream.ts` — handleDiscard is in CardCreationPanel, not the hook

### §AntiPatterns — DO NOT Do These

| ❌ Wrong | ✅ Correct |
|---|---|
| N+1 queries for card counts (one query per deck) | Single aggregated query with `outerjoin` + `func.count`/`func.sum` |
| `func.sum()` without null guard | `int(row[2] or 0)` — sum returns None on empty sets |
| Hard-deleting cards when deck is deleted | NULL out `Card.deck_id` first, then delete deck |
| Using `join` instead of `outerjoin` in list_decks | `outerjoin` — decks with 0 cards must still appear |
| Storing server data (deck list) in Zustand | TanStack Query owns deck list — key `["decks", langCode]` |
| Calling `queryClient.invalidateQueries` (triggers re-fetch) | Use `setQueryData` for optimistic updates on create/rename/delete |
| Checking duplicate name for `PATCH` when name unchanged | Skip conflict check when `new_name == deck.name` |
| `app.dependency_overrides.clear()` in test teardown | `app.dependency_overrides.pop(dep, None)` — safe pop |
| Manually editing `routeTree.gen.ts` | Auto-generated — run TanStack Router CLI |
| `getByText()` for async TanStack Query data | `await screen.findByText()` |
| Navigation link click when renaming inline | `e.stopPropagation()` on rename button click |
| Adding business logic to `api/decks.py` router | All logic in `core/decks.py` — router validates, delegates, converts errors |
| Manually editing `api.d.ts` | Always regenerated from FastAPI OpenAPI schema |

### References

- Story 2.2 acceptance criteria: [Source: `_bmad-output/planning-artifacts/epics.md#Story 2.2`]
- FR9 (deck CRUD), FR10 (browse/filter), FR16 (multi-language): [Source: `_bmad-output/planning-artifacts/epics.md#Functional Requirements`]
- `Deck` SQLModel table definition: [Source: `src/lingosips/db/models.py:45`]
- `Card.deck_id` FK column: [Source: `src/lingosips/db/models.py:30`]
- `Settings.target_languages` + `active_target_language`: [Source: `src/lingosips/db/models.py:61–63`]
- `PATCH /cards/{card_id}` with deck_id: [Source: `src/lingosips/api/cards.py:212`, `CardUpdateRequest.deck_id`]
- `get_or_create_settings()`: [Source: `src/lingosips/core/settings.py:59`]
- `update_settings()`: [Source: `src/lingosips/core/settings.py:85`]
- `PUT /settings` endpoint: [Source: `src/lingosips/api/settings.py:66`]
- Deferred target_languages reconciliation: [Source: `_bmad-output/implementation-artifacts/deferred-work.md` — deferred from Story 1.4]
- discard() TODO in useCardStream: [Source: `frontend/src/features/cards/useCardStream.ts:113`]
- `saveCard()` in useCardStream: [Source: `frontend/src/features/cards/useCardStream.ts:98`]
- CardCreationPanel save action row (populated state): [Source: `frontend/src/features/cards/CardCreationPanel.tsx:209`]
- `patch()`, `del()`, `put()`, `post()`, `get()` client functions: [Source: `frontend/src/lib/client.ts`]
- `Dialog` delete confirmation pattern: [Source: `_bmad-output/implementation-artifacts/2-1-card-detail-editing-notes.md#T10.9`]
- TanStack Query key conventions: [Source: `_bmad-output/project-context.md#TanStack Query key conventions`]
- Zustand/TanStack Query state boundary: [Source: `_bmad-output/project-context.md#Frontend state boundary`]
- RFC 7807 error format: [Source: `_bmad-output/project-context.md#API Design Rules`]
- Router delegates to core: [Source: `_bmad-output/project-context.md#Layer Architecture & Boundaries`]
- State machine enum-driven pattern: [Source: `_bmad-output/project-context.md#Component state machines`]
- TDD mandatory process: [Source: `_bmad-output/planning-artifacts/architecture.md#TDD Process`]
- Ruff line length E501, import sort I001: [Source: `_bmad-output/implementation-artifacts/2-1-card-detail-editing-notes.md#PreviousStoryIntelligence`]
- `app.dependency_overrides.pop()` pattern: [Source: `tests/conftest.py:76`]
- `conftest.py` session/client/test_engine fixtures: [Source: `tests/conftest.py`]
- shadcn/ui `Card`, `Badge`, `Dialog`, `Button`, `Input`, `Skeleton`: [Source: `frontend/src/components/ui/`]
- Feature isolation — no cross-feature imports: [Source: `_bmad-output/project-context.md#Feature isolation`]
- `useAppStore.addNotification()` error flow: [Source: `_bmad-output/project-context.md#Error flow pattern`]
- Backend architecture `api/` + `core/` separation: [Source: `_bmad-output/planning-artifacts/architecture.md#Structure Patterns`]
- `useQueryClient()` for cache mutations: [Source: `_bmad-output/planning-artifacts/architecture.md#Frontend Architecture`]

---

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5)

### Debug Log References

### Completion Notes List

- T1–T4: 27 TDD backend tests written first (test_decks.py) before any implementation
- T5: core/decks.py with single aggregated SQL (outerjoin + func.count + func.sum(case)) — no N+1; always coerce func.sum() with `int(row or 0)`
- T6: api/decks.py router delegates all logic to core; RFC 7807 error shapes for 409 + 404; POST returns 201
- T7: Decks router registered in app.py; api.d.ts regenerated from live OpenAPI spec (12 deck types added)
- T8: 14 unit tests in DeckGrid.test.tsx written first (TDD), covering all ACs including 409 error notification
- T9–T11: DeckGrid.tsx + DeckCard.tsx + inline CreateDeckForm; all mutations use setQueryData (not invalidateQueries); settingsLoading tracked separately to show skeleton
- T12–T14: decks feature index.ts, /decks route, /decks/$deckId stub route
- T15: Decks nav item added to IconSidebar + BottomNav (6 items total); routeTree.gen.ts regenerated via TanStack Router CLI; nav tests updated for 6 items
- T16: CardCreationPanel updated with async handleSave (PATCH deck_id) + handleDiscard (DELETE card, implements Story 2.1 TODO)
- T17: TypeScript 0 errors, backend 90.40% coverage (309 tests), frontend 150 tests (11 files) all pass, ruff clean
- T18: 9 Playwright E2E tests in deck-management.spec.ts; createSeedDeck() helper added to fixtures/index.ts
- Coverage fix: Created tests/core/test_decks.py (21 direct unit tests) to fix core/decks.py 33% → 100% (ASGI transport does not track async coverage)

### File List

**New files:**
- tests/api/test_decks.py
- tests/core/test_decks.py
- src/lingosips/core/decks.py
- src/lingosips/api/decks.py
- frontend/src/features/decks/DeckGrid.tsx
- frontend/src/features/decks/DeckCard.tsx
- frontend/src/features/decks/DeckGrid.test.tsx
- frontend/src/features/decks/index.ts
- frontend/src/routes/decks.tsx
- frontend/src/routes/decks.$deckId.tsx
- frontend/e2e/features/deck-management.spec.ts

**Modified files:**
- src/lingosips/api/app.py
- frontend/src/components/layout/IconSidebar.tsx
- frontend/src/components/layout/BottomNav.tsx
- frontend/src/components/layout/__tests__/IconSidebar.test.tsx
- frontend/src/components/layout/__tests__/BottomNav.test.tsx
- frontend/src/features/cards/CardCreationPanel.tsx
- frontend/e2e/fixtures/index.ts

**Auto-regenerated:**
- frontend/src/lib/api.d.ts
- frontend/src/routeTree.gen.ts

### Review Findings

- [x] [Review][Patch] DeckCard.tsx — Double `onRename` call on Enter: unmount-triggered blur re-fires after keyboard commit [`frontend/src/features/decks/DeckCard.tsx:56-72`] — **Fixed**: added `renameSettledRef` guard; Enter/Escape set ref before `setState` so blur echo is ignored
- [x] [Review][Patch] DeckCard.tsx — Spurious rename on Escape: blur fires after cancel and saves typed text [`frontend/src/features/decks/DeckCard.tsx:62-72`] — **Fixed**: same `renameSettledRef` guard; new test "pressing Escape after typing a new name discards without saving" added
- [x] [Review][Patch] DeckGrid.tsx — 409 error message double-nested: `error.detail` (full RFC 7807 sentence) wrapped in another template string [`frontend/src/features/decks/DeckGrid.tsx:155-161`] — **Fixed**: `error.detail` now used directly for 409; falls back to `error.title` then generic
- [x] [Review][Patch] DeckGrid.tsx — `JSON.parse(target_languages)` unguarded: `SyntaxError` crashes component on malformed data [`frontend/src/features/decks/DeckGrid.tsx:122-124`] — **Fixed**: wrapped in `parseLanguages()` helper with try/catch + `Array.isArray` validation, fallback to `[activeLanguage]`
- [x] [Review][Patch] tests/api/test_decks.py — Ruff I001 (import sort) + F401 (`lingosips.api.app.app` unused import) [`tests/api/test_decks.py:7-14`] — **Fixed**
- [x] [Review][Patch] tests/core/test_decks.py — Ruff I001 (import sort) + F841 (`original_updated`, `card_id` unused variables) [`tests/core/test_decks.py`] — **Fixed**

## Change Log

- 2026-05-01: Story 2.2 implemented — deck CRUD backend (27 API tests + 21 core unit tests, 90.40% coverage), DeckGrid + DeckCard frontend (14 unit tests), Decks nav item in sidebar + bottom nav, CardCreationPanel deck assignment dropdown + discard card fix, 9 Playwright E2E tests
- 2026-05-01: Code review — 6 patches applied: DeckCard double-rename/Escape-saves bugs fixed with `renameSettledRef`; DeckGrid 409 message corrected and `JSON.parse` guarded; ruff violations fixed; 1 new test added (151 frontend, 309 backend, 90.40% coverage, ruff clean)
