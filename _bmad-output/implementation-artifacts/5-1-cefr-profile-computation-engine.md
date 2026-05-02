# Story 5.1: CEFR Profile Computation Engine

Status: done

## Story

As a user,
I want the app to continuously analyze my vocabulary breadth, grammar forms, practice performance, and recall history to estimate where I sit on the A1–C2 scale,
So that I have an authoritative, data-driven picture of my language proficiency — not a self-reported guess.

## Acceptance Criteria

1. **AC1 — Four-dimension profile aggregation:** When `core/cefr.py` computes the knowledge profile, it aggregates four dimensions from the review log: vocabulary breadth (unique cards with `fsrs_state` in `"Review"` or `"Mature"`), grammar forms coverage (count of distinct form type keys across all saved cards), practice performance (recall rate by `card_type` over last 30 days), and active vs. passive recall (ratio of cards in write/speak sessions vs. self-assess-only sessions). All dimensions are scoped to the requested `target_language`.

2. **AC2 — CEFR level mapping:** `core/cefr.py` maps the four dimensions to a CEFR level using vocabulary thresholds with a grammar coverage modifier: A1 (0–49 active words), A2 (50–149), B1 (150–499), B2 (500–1199), C1 (1200–2499), C2 (2500+). Grammar coverage ≥ 5 distinct form types can advance the level by one step if the vocabulary is near the upper threshold (≥ 80% of next level). The assigned level is cached per `target_language` so subsequent `GET /cefr/profile` calls return within 500ms without recomputing.

3. **AC3 — Null level for sparse data:** When the review log has fewer than 10 cards reviewed (for the specified language), the response returns `{"level": null, "explanation": "Practice more cards to generate your profile"}` and all dimension values are zero or null. No invalid level estimate is shown.

4. **AC4 — Cache invalidation after rating:** After a `POST /practice/cards/{card_id}/rate` completes successfully, the CEFR profile cache entry for that card's `target_language` is invalidated (synchronously, zero-latency dict pop). The rating response is not delayed. The next `GET /cefr/profile` call triggers a fresh computation.

5. **AC5 — Language scoping:** `GET /cefr/profile?target_language={lang}` computes the profile using only cards and reviews linked to the specified language. Missing `target_language` returns `422 Unprocessable Entity` with `{"field": "target_language", "message": "target_language is required"}`.

6. **AC6 — Performance:** `GET /cefr/profile` returns within 500ms when the review log has 1000+ rows (for the specified language). Aggregation uses indexed queries on `reviews.card_id` and `reviews.reviewed_at`.

7. **AC7 — Session mode tracking (prerequisite for active/passive dimension):** `POST /practice/session/start` accepts an optional `mode` query param (`"self_assess"` | `"write"` | `"speak"`). The value is stored in `practice_sessions.mode` (new nullable column, Alembic migration `003`). `usePracticeSession.ts` passes the current mode when calling session start. Existing sessions without mode data are treated as `"self_assess"` for active/passive ratio computation.

## Tasks / Subtasks

- [x] Task 1: Write ALL failing tests first — TDD (AC: 1–7)
  - [x] 1.1 Create `tests/core/test_cefr.py`:
    - `TestComputeVocabularyBreadth`: returns correct count for seeded cards in "Review"/"Mature" state; excludes "New"/"Learning" state; scopes to target_language
    - `TestComputeGrammarCoverage`: returns count of distinct form-type keys across cards; handles null `forms`; handles malformed JSON (skip, no crash)
    - `TestComputeRecallRateByCardType`: correct rate by card_type for last 30 days; ignores reviews older than 30 days; returns `{}` when no reviews
    - `TestComputeActivePassiveRatio`: returns correct ratio; returns `None` when no sessions with mode data; treats null mode as self_assess
    - `TestMapToCefrLevel`: A1 threshold (49 words → A1), B1 threshold (150 words → B1), C1 threshold (1200 words → C1); null when < 10 reviews; grammar boost advances level when vocab ≥ 80% of next threshold
    - `TestGetCefrProfile`: cached result returned on second call; cache invalidated by `invalidate_profile_cache(lang)`; profile scoped to language correctly
  - [x] 1.2 Create `tests/api/test_cefr.py`:
    - `TestGetCefrProfile`:
      - `test_missing_target_language_returns_422` — no query param → 422 RFC 7807
      - `test_empty_profile_fewer_than_10_reviews` — < 10 reviews → `level: null`
      - `test_correct_a1_level_for_seeded_data` — seed 40 Review-state cards, 10+ reviews → `level: "A1"`
      - `test_correct_b1_level_for_seeded_data` — seed 200 Review-state cards, 10+ reviews → `level: "B1"`
      - `test_correct_c1_level_for_seeded_data` — seed 1300 Review-state cards, 10+ reviews → `level: "C1"`
      - `test_language_scoping_excludes_other_languages` — Spanish cards don't affect French profile
      - `test_cache_returns_same_result_without_requery` — call twice; mocked DB only queried once
      - `test_cache_invalidated_after_rating` — GET → rate card → GET returns freshly computed result
      - `test_response_shape_with_valid_profile` — all required fields present in response
  - [x] 1.3 Update `tests/api/test_practice.py`:
    - Add `test_start_session_with_mode_stored` — POST /practice/session/start?mode=write → session row has mode="write"
    - Add `test_start_session_without_mode_defaults_to_null` — no mode param → mode is null in DB

- [x] Task 2: Alembic migration — add `mode` to `practice_sessions` (AC: 7)
  - [x] 2.1 Add `mode: str | None = Field(default=None)` to `PracticeSession` in `db/models.py`
  - [x] 2.2 Create `src/lingosips/db/migrations/versions/003_practice_session_mode.py` with revision ID `c3d4e5f6a1b2`, down_revision `a1b2c3d4e5f6`
  - [x] 2.3 Migration `upgrade()`: `op.add_column("practice_sessions", sa.Column("mode", sa.String(), nullable=True))`
  - [x] 2.4 Migration `downgrade()`: `op.drop_column("practice_sessions", "mode")`

- [x] Task 3: Update `api/practice.py` session start + rate card (AC: 4, 7)
  - [x] 3.1 Import `Optional` / `Query` from fastapi; add `mode: str | None = Query(default=None)` to `start_session` signature
  - [x] 3.2 Store `mode` on the created `PracticeSession` row before commit in `start_session`
  - [x] 3.3 Import `cefr as core_cefr` from `lingosips.core`
  - [x] 3.4 After `core_fsrs.rate_card(...)` succeeds in `rate_card` endpoint, call `core_cefr.invalidate_profile_cache(updated_card.target_language)` — synchronous, one-liner

- [x] Task 4: Implement `core/cefr.py` (AC: 1–6)
  - [x] 4.1 Define module-level cache: `_profile_cache: dict[str, "CefrProfile | None"] = {}`
  - [x] 4.2 Define `CefrProfile` dataclass with fields: `level: str | None`, `vocabulary_breadth: int`, `grammar_coverage: int`, `recall_rate_by_card_type: dict[str, float]`, `active_passive_ratio: float | None`, `explanation: str`
  - [x] 4.3 Implement `compute_vocabulary_breadth(db, target_language) → int` — count distinct card IDs where `fsrs_state` in `("Review", "Mature")` and `target_language = lang`
  - [x] 4.4 Implement `compute_grammar_coverage(db, target_language) → int` — fetch non-null `forms` for cards of target_language; parse each JSON string; collect top-level keys; return `len(distinct_keys)`. Skip cards with invalid JSON (don't crash).
  - [x] 4.5 Implement `compute_recall_rate_by_card_type(db, target_language) → dict[str, float]` — join `reviews` with `cards` on `card_id`; filter `reviewed_at >= now - 30 days` and `target_language = lang`; group by `card_type`; return `{card_type: correct_count/total_count}`
  - [x] 4.6 Implement `compute_active_passive_ratio(db, target_language) → float | None` — query `practice_sessions` joined to `reviews` joined to `cards` where `target_language = lang`; count sessions with `mode` in `("write", "speak")` (active) vs total sessions with mode data. Return `None` if zero sessions with mode data. Treat null mode as `"self_assess"` (passive).
  - [x] 4.7 Implement `map_to_cefr_level(vocab_breadth, grammar_coverage, review_count) → str | None` — apply thresholds (A1–C2). Return `None` when `review_count < 10`. Grammar boost: if `grammar_coverage >= 5` and `vocab_breadth >= 0.8 * next_level_threshold`, advance one step.
  - [x] 4.8 Implement `get_profile(target_language, db) → CefrProfile` — check cache first; if miss, compute all dimensions via 4.3–4.6, map level via 4.7, build `CefrProfile`, cache under `target_language`, return. Cache hit must not call `db`.
  - [x] 4.9 Implement `invalidate_profile_cache(target_language: str) → None` — `_profile_cache.pop(target_language, None)`. Pure sync, no async needed.
  - [x] 4.10 Count total reviews for the language (for null-check threshold) in `get_profile` using an indexed query on `reviews` joined to `cards.target_language`.

- [x] Task 5: Implement `api/cefr.py` (AC: 1–6)
  - [x] 5.1 Create router with `router = APIRouter()`
  - [x] 5.2 Define `CefrProfileResponse` Pydantic model: `level: str | None`, `vocabulary_breadth: int`, `grammar_coverage: int`, `recall_rate_by_card_type: dict[str, float]`, `active_passive_ratio: float | None`, `explanation: str`
  - [x] 5.3 Implement `GET /profile` endpoint with `target_language: str = Query(...)` (required) and `session: AsyncSession = Depends(get_session)`
  - [x] 5.4 Validate `target_language` present — FastAPI handles `...` as required; `Query(...)` returns 422 automatically
  - [x] 5.5 Call `await core_cefr.get_profile(target_language, db)` and map to `CefrProfileResponse`

- [x] Task 6: Register CEFR router in `api/app.py` (AC: 5)
  - [x] 6.1 Import `from lingosips.api.cefr import router as cefr_router`
  - [x] 6.2 Register: `application.include_router(cefr_router, prefix="/cefr", tags=["cefr"])` — add after `progress_router` registration

- [x] Task 7: Update `usePracticeSession.ts` — pass mode to session start (AC: 7)
  - [x] 7.1 Update `mutationFn` in `startSessionMutation`: `post<SessionStartApiResponse>("/practice/session/start", undefined, { mode: _mode ?? "self_assess" })` — or use query params: `post<SessionStartApiResponse>(`/practice/session/start?mode=${_mode ?? "self_assess"}`, undefined)`
  - [x] 7.2 Prefer query param approach since `start_session` uses `mode: str | None = Query(default=None)`: change to `get<SessionStartApiResponse>(`/practice/session/start?mode=${_mode ?? "self_assess"}`)` and switch from POST body to query param — but wait, the endpoint is a POST with no body, so query param is correct.

  Actually use: in `startSessionMutation.mutationFn`, call `post<SessionStartApiResponse>("/practice/session/start", undefined)` → change path to include mode: `post<SessionStartApiResponse>(\`/practice/session/start?mode=${_mode ?? "self_assess"}\`, undefined)`

- [x] Task 8: Playwright E2E — `frontend/e2e/features/progress-and-cefr.spec.ts` (AC: 1–6)
  - [x] 8.1 This file is named in the architecture spec (`frontend/e2e/features/progress-and-cefr.spec.ts`) and covers FR41–FR47. Story 3.5 added partial coverage; Story 5.1 adds CEFR backend tests.
  - [x] 8.2 Add `describe("CEFR profile endpoint")` block:
    - Test: `GET /cefr/profile` without target_language param returns 422
    - Test: `GET /cefr/profile?target_language=es` with seeded review data returns a valid profile shape (level field present, may be null if seed is minimal)
    - Test: `GET /cefr/profile?target_language=es` returns within 500ms (measure response time)

## Dev Notes

### Overview

Story 5.1 delivers the entire backend computation pipeline for CEFR profiling. It is purely backend — no new frontend components. The frontend display (`CefrProfile` component, knowledge breakdown rows) is Story 5.2.

What this story touches:
- **New**: `src/lingosips/core/cefr.py` — CEFR computation + cache
- **New**: `src/lingosips/api/cefr.py` — FastAPI router for `GET /cefr/profile`
- **New**: `src/lingosips/db/migrations/versions/003_practice_session_mode.py`
- **New**: `tests/core/test_cefr.py` + `tests/api/test_cefr.py`
- **Modify**: `src/lingosips/db/models.py` — add `mode` to `PracticeSession`
- **Modify**: `src/lingosips/api/practice.py` — accept mode in session start, invalidate CEFR cache after rating
- **Modify**: `src/lingosips/api/app.py` — register cefr router
- **Modify**: `frontend/src/features/practice/usePracticeSession.ts` — pass mode to session start
- **Modify**: `frontend/e2e/features/progress-and-cefr.spec.ts` — add CEFR endpoint tests

No new frontend components. Story 5.2 builds the `CefrProfile` React component that consumes `GET /cefr/profile`.

---

### CRITICAL: `fsrs_state` Column Name

The FSRS state column on `Card` is `fsrs_state` (not `state`). This is defined in `db/models.py` line 40:
```python
fsrs_state: str = Field(default="New")
```
The valid values are `"New"`, `"Learning"`, `"Review"`, `"Relearning"`, `"Mature"`.

In `compute_vocabulary_breadth`, filter on `Card.fsrs_state.in_(["Review", "Mature"])` — NOT `Card.state`.

---

### CRITICAL: `core/cefr.py` Must Not Import FastAPI

Following the strict layer architecture — `core/` never imports `fastapi`, `SQLModel`, or response types:

```python
# CORRECT
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import structlog
from sqlalchemy import distinct as sa_distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.db.models import Card, PracticeSession, Review

# WRONG
from fastapi import HTTPException  # ❌ never in core/
from pydantic import BaseModel     # ❌ use @dataclass in core/
```

---

### CRITICAL: Caching Design — Module-Level Dict

The cache is a simple module-level dict in `core/cefr.py`. In Python asyncio (single-threaded), dict operations are safe without a lock. The cache key is `target_language` string:

```python
# core/cefr.py
_profile_cache: dict[str, "CefrProfile | None"] = {}

def invalidate_profile_cache(target_language: str) -> None:
    """Remove cached profile for the given language. Safe to call synchronously."""
    _profile_cache.pop(target_language, None)

async def get_profile(target_language: str, db: AsyncSession) -> CefrProfile:
    if target_language in _profile_cache:
        cached = _profile_cache[target_language]
        return cached  # type: ignore[return-value] — None is valid (< 10 reviews case)
    profile = await _compute_profile(target_language, db)
    _profile_cache[target_language] = profile
    return profile
```

**Important for tests**: The cache persists across test calls within the same session. In `tests/api/test_cefr.py`, clear the cache in `teardown` or between tests:
```python
@pytest.fixture(autouse=True)
async def clear_cefr_cache(self) -> None:
    from lingosips.core import cefr as core_cefr
    core_cefr._profile_cache.clear()
    yield
    core_cefr._profile_cache.clear()
```

The existing `conftest.py` rolls back the DB session after each test, but that doesn't clear the in-memory cache. The autouse fixture above is required.

---

### CRITICAL: CEFR Level Thresholds

Exact thresholds used in `map_to_cefr_level`:

| Level | Min active words | Max (exclusive) |
|-------|-----------------|-----------------|
| A1    | 0               | 50              |
| A2    | 50              | 150             |
| B1    | 150             | 500             |
| B2    | 500             | 1200            |
| C1    | 1200            | 2500            |
| C2    | 2500            | ∞               |

Grammar coverage boost rule:
- If `grammar_coverage >= 5` AND `vocab_breadth >= 0.8 * current_upper_threshold` → advance one level
- Cap at C2 (no level above C2)
- Do not apply boost to `null` level (< 10 reviews case)

Example implementation:
```python
THRESHOLDS = [(50, "A1"), (150, "A2"), (500, "B1"), (1200, "B2"), (2500, "C1")]
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

def map_to_cefr_level(
    vocab_breadth: int, grammar_coverage: int, review_count: int
) -> str | None:
    if review_count < 10:
        return None
    base_level = "C2"
    upper = None
    for threshold, level in THRESHOLDS:
        if vocab_breadth < threshold:
            base_level = level
            upper = threshold
            break
    # Grammar boost: advance one step if coverage ≥ 5 and vocab ≥ 80% of next level threshold
    if grammar_coverage >= 5 and upper is not None:
        if vocab_breadth >= 0.8 * upper:
            idx = LEVELS.index(base_level)
            if idx + 1 < len(LEVELS):
                base_level = LEVELS[idx + 1]
    return base_level
```

---

### CRITICAL: Grammar Forms JSON Parsing

`Card.forms` is a JSON string like `'{"gender": "masculine", "article": "el", "plural": "colores", "conjugations": {...}}'`. To count grammar form types:

```python
async def compute_grammar_coverage(db: AsyncSession, target_language: str) -> int:
    result = await db.execute(
        select(Card.forms)
        .where(Card.target_language == target_language, Card.forms.isnot(None))
    )
    rows = result.scalars().all()
    
    form_types: set[str] = set()
    for forms_json in rows:
        try:
            forms_dict = json.loads(forms_json)
            if isinstance(forms_dict, dict):
                form_types.update(forms_dict.keys())
        except (json.JSONDecodeError, TypeError):
            continue  # skip malformed JSON — do not crash
    
    return len(form_types)
```

This fetches only `forms` column (no full card rows), reducing data transfer. For 1000 cards this is fast.

---

### CRITICAL: Active/Passive Ratio Query

The active/passive ratio requires joining `reviews` → `practice_sessions` via `session_id`. Sessions without a `mode` (null) are treated as `"self_assess"`:

```python
async def compute_active_passive_ratio(
    db: AsyncSession, target_language: str
) -> float | None:
    # Find all practice sessions that had at least one review for this language
    # A session is "active" if mode in ("write", "speak")
    result = await db.execute(
        select(
            PracticeSession.mode,
            func.count(sa_distinct(Review.session_id)).label("session_count"),
        )
        .join(Review, Review.session_id == PracticeSession.id)
        .join(Card, Card.id == Review.card_id)
        .where(Card.target_language == target_language)
        .where(Review.session_id.isnot(None))
        .group_by(PracticeSession.mode)
    )
    rows = result.all()
    
    if not rows:
        return None
    
    total = sum(r.session_count for r in rows)
    active = sum(
        r.session_count for r in rows
        if r.mode in ("write", "speak")
    )
    return active / total if total > 0 else None
```

Note: `sa_distinct` is `from sqlalchemy import distinct as sa_distinct` — same pattern as `core/progress.py`. Do NOT write `sa.distinct(...)` — the project imports specific symbols only.

---

### CRITICAL: `api/practice.py` Changes

Two changes to `rate_card` and `start_session`. Keep them minimal to avoid regressions:

**1. `start_session` — add mode param:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request  # add Query

@router.post("/session/start", response_model=SessionStartResponse)
async def start_session(
    session: AsyncSession = Depends(get_session),
    mode: str | None = Query(default=None),  # ADD THIS
) -> SessionStartResponse:
    ...
    # When creating PracticeSession, add mode:
    practice_session = PracticeSession(mode=mode)  # was: PracticeSession()
    ...
```

**2. `rate_card` — invalidate CEFR cache after rating:**
```python
from lingosips.core import cefr as core_cefr  # ADD THIS IMPORT

@router.post("/cards/{card_id}/rate", response_model=RatedCardResponse)
async def rate_card(
    card_id: int,
    request: RateCardRequest,
    session: AsyncSession = Depends(get_session),
) -> RatedCardResponse:
    ...
    updated_card = await core_fsrs.rate_card(card, request.rating, session, request.session_id)
    # Invalidate CEFR profile cache — synchronous, zero-latency dict pop (AC4)
    core_cefr.invalidate_profile_cache(updated_card.target_language)
    return RatedCardResponse.model_validate(updated_card)
```

Do NOT change any other logic in `rate_card` or `start_session`.

---

### CRITICAL: `api/app.py` Registration

Add CEFR router registration after progress router:

```python
# In create_app(), after:
application.include_router(progress_router, prefix="/progress", tags=["progress"])
# ADD:
from lingosips.api.cefr import router as cefr_router
application.include_router(cefr_router, prefix="/cefr", tags=["cefr"])
```

Also add `"/cefr"` is NOT a browser-navigable SPA route (no HTML fallback needed), so no change to `_spa_routes_exact`.

---

### CRITICAL: `usePracticeSession.ts` Mode Pass-Through

The `_mode` parameter is already accepted by `usePracticeSession` but not sent to the backend. Change the `startSessionMutation.mutationFn` to include mode:

```typescript
// CURRENT (line ~114):
mutationFn: () => post<SessionStartApiResponse>("/practice/session/start", undefined),

// CHANGE TO:
mutationFn: () => post<SessionStartApiResponse>(
  `/practice/session/start?mode=${_mode ?? "self_assess"}`,
  undefined
),
```

This is the ONLY change to `usePracticeSession.ts`. Do not touch any other logic.

---

### CRITICAL: `api/cefr.py` Response Shape

The `CefrProfileResponse` must have `nullable` fields where needed. `null` level is valid:

```python
from pydantic import BaseModel

class CefrProfileResponse(BaseModel):
    level: str | None             # null when < 10 reviews
    vocabulary_breadth: int
    grammar_coverage: int
    recall_rate_by_card_type: dict[str, float]  # empty dict when no reviews
    active_passive_ratio: float | None           # null when no session mode data
    explanation: str              # always present — describes level or instructs to practice more
```

The `explanation` field content:
- When `level` is null: `"Practice more cards to generate your profile"` (verbatim from AC)
- When `level` is set: `"You have demonstrated {level} vocabulary and grammar coverage."` — Story 5.2 renders full explanatory text; the backend just provides the raw data and a minimal explanation string.

---

### CRITICAL: `GET /cefr/profile` Endpoint Signature

`target_language` is a **required** query param. Use FastAPI's `Query(...)` (ellipsis = required) — FastAPI auto-returns 422 when missing:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import cefr as core_cefr
from lingosips.db.session import get_session

router = APIRouter()

@router.get("/profile", response_model=CefrProfileResponse)
async def get_cefr_profile(
    target_language: str = Query(...),  # required — missing → 422 auto from FastAPI
    session: AsyncSession = Depends(get_session),
) -> CefrProfileResponse:
    profile = await core_cefr.get_profile(target_language, session)
    return CefrProfileResponse(
        level=profile.level,
        vocabulary_breadth=profile.vocabulary_breadth,
        grammar_coverage=profile.grammar_coverage,
        recall_rate_by_card_type=profile.recall_rate_by_card_type,
        active_passive_ratio=profile.active_passive_ratio,
        explanation=profile.explanation,
    )
```

Note: FastAPI's auto-generated 422 for missing `Query(...)` parameters does NOT use our RFC 7807 format by default, BUT we have a `validation_exception_handler` in `app.py` that converts all `RequestValidationError` to RFC 7807. So the 422 body will be:
```json
{"type": "/errors/validation", "title": "Validation error", "status": 422, "errors": [{"field": "query.target_language", "message": "Field required", "type": "missing"}]}
```
The AC says `{"field": "target_language", "message": "target_language is required"}` — the actual output via the validation handler will have `"field": "query.target_language"` (FastAPI validation loc includes param location). Test for the field name containing `"target_language"` rather than exact match.

---

### CRITICAL: Alembic Migration 003 Pattern

Follow exact pattern from migration 002:

```python
"""003_practice_session_mode

Revision ID: c3d4e5f6a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "c3d4e5f6a1b2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add mode column to practice_sessions for active/passive recall tracking."""
    op.add_column(
        "practice_sessions",
        sa.Column("mode", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove mode column from practice_sessions."""
    op.drop_column("practice_sessions", "mode")
```

The migration file name must follow the pattern: `003_practice_session_mode.py` (no revision prefix in filename, unlike `e328b921ead2_001_initial_schema.py`). The filename convention from 002 uses just the number prefix.

---

### CRITICAL: Test Seeding for CEFR Level Tests

The test fixtures need to create cards with specific FSRS states AND enough reviews. Here's the seed pattern for A1 level test:

```python
async def test_correct_a1_level_for_seeded_data(self, client, session):
    """40 Review-state cards + 15 reviews → level: A1"""
    from lingosips.db.models import Card, Review
    
    # Seed 40 active cards (Review state)
    cards = []
    for i in range(40):
        c = Card(target_word=f"word{i}", target_language="es", fsrs_state="Review")
        session.add(c)
    await session.commit()
    # Refresh to get IDs
    for c in cards:
        await session.refresh(c)
    
    # Add 15 reviews (> 10 threshold) — need to seed via models directly
    # Use the actual card IDs
    result = await session.execute(select(Card).where(Card.target_language == "es"))
    db_cards = result.scalars().all()
    
    for i, c in enumerate(db_cards[:15]):
        session.add(Review(
            card_id=c.id,
            rating=3,
            stability_after=1.0,
            difficulty_after=5.0,
            fsrs_state_after="Review",
            reps_after=1,
            lapses_after=0,
        ))
    await session.commit()
    
    response = await client.get("/cefr/profile?target_language=es")
    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "A1"
    assert data["vocabulary_breadth"] == 40
```

For B1 (need 150–499 active words): seed 200 Review-state cards + 10 reviews.
For C1 (need 1200–2499 active words): seed 1300 Review-state cards + 10 reviews.

Performance test (AC6 — 500ms SLA): seed 1000+ reviews and measure response time:
```python
import time

async def test_large_review_log_returns_within_500ms(self, client, session):
    # Seed 1000+ reviews for "es" language
    ...
    start = time.monotonic()
    response = await client.get("/cefr/profile?target_language=es")
    elapsed_ms = (time.monotonic() - start) * 1000
    assert response.status_code == 200
    assert elapsed_ms < 500, f"Response took {elapsed_ms:.0f}ms, expected < 500ms"
```

---

### CRITICAL: Recall Rate by Card Type — Join Strategy

The `recall_rate_by_card_type` query joins `reviews` with `cards`. Use SQLAlchemy join, not Python-side filtering (expensive). Use explicit imports matching the project pattern (no `import sqlalchemy as sa` — the project uses `from sqlalchemy import ...`):

```python
from datetime import UTC, datetime, timedelta
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

async def compute_recall_rate_by_card_type(
    db: AsyncSession, target_language: str
) -> dict[str, float]:
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    result = await db.execute(
        select(
            Card.card_type,
            func.count(Review.id).label("total"),
            func.sum(
                case((Review.rating >= 3, 1), else_=0)
            ).label("correct"),
        )
        .join(Card, Card.id == Review.card_id)
        .where(Card.target_language == target_language)
        .where(Review.reviewed_at >= thirty_days_ago)
        .group_by(Card.card_type)
    )
    rows = result.all()
    return {
        row.card_type: (row.correct or 0) / row.total
        for row in rows
        if row.total > 0
    }
```

**Import pattern for `core/cefr.py` — use explicit imports matching `core/progress.py`:**
```python
from sqlalchemy import case, distinct as sa_distinct, func, select
```
Do NOT use `import sqlalchemy as sa` — that is not the project pattern. Use `case` directly from sqlalchemy.

---

### CRITICAL: Review Count for Null-Check

The null check (< 10 reviews) must use a count query scoped to `target_language`. Don't reuse `vocab_breadth` for this:

```python
async def _count_reviews_for_language(db: AsyncSession, target_language: str) -> int:
    result = await db.execute(
        select(func.count(Review.id))
        .join(Card, Card.id == Review.card_id)
        .where(Card.target_language == target_language)
    )
    return result.scalar_one() or 0
```

Call this FIRST in `_compute_profile`. If count < 10, return early with `CefrProfile(level=None, ...)` without running the expensive dimension queries.

---

### CRITICAL: Alembic vs `SQLModel.metadata.create_all()`

The `conftest.py` test setup uses `SQLModel.metadata.create_all` for creating the in-memory test DB — this is correct for tests only. DO NOT call `create_all` in production code. The migration must be an Alembic `.py` file. The conftest will pick up the new `mode` column automatically since it reads from the updated `PracticeSession` SQLModel definition.

---

### CRITICAL: `api/app.py` Import Pattern

Imports are currently done inside the `create_app()` function body (not at module top level). Follow the same pattern:

```python
def create_app() -> FastAPI:
    from lingosips.api.cards import router as cards_router
    # ... existing imports ...
    from lingosips.api.cefr import router as cefr_router  # ADD HERE
    
    # ... existing router registrations ...
    application.include_router(cefr_router, prefix="/cefr", tags=["cefr"])  # ADD AFTER progress_router
```

---

### Performance: Vocabulary Breadth Query Uses Indexed Column

`Card.fsrs_state` is NOT indexed, but the filter `target_language` IS covered by the general table scan. For performance with large datasets:
- The vocabulary breadth query is: `SELECT COUNT(DISTINCT id) FROM cards WHERE target_language = ? AND fsrs_state IN ('Review', 'Mature')`
- SQLite will use the `target_language` index if one exists, or scan. At single-user scale (< 5000 cards), this is fast.
- Do NOT add a new index — the story doesn't require schema index changes beyond migration 003.

---

### Files to Create

| File | Action | Description |
|------|--------|-------------|
| `src/lingosips/core/cefr.py` | CREATE NEW | CEFR computation engine: vocab breadth, grammar coverage, recall rate by type, active/passive ratio, level mapping, cache |
| `src/lingosips/api/cefr.py` | CREATE NEW | FastAPI router: `GET /cefr/profile` with `target_language` query param |
| `src/lingosips/db/migrations/versions/003_practice_session_mode.py` | CREATE NEW | Alembic migration: add `mode` nullable column to `practice_sessions` |
| `tests/core/test_cefr.py` | CREATE NEW | Unit tests for all `core/cefr.py` functions |
| `tests/api/test_cefr.py` | CREATE NEW | API tests for `GET /cefr/profile` endpoint |

### Files to Modify

| File | Action | What Changes |
|------|--------|--------------|
| `src/lingosips/db/models.py` | MODIFY | Add `mode: str | None = Field(default=None)` to `PracticeSession` |
| `src/lingosips/api/practice.py` | MODIFY | (1) Add `mode: str | None = Query(default=None)` to `start_session`; (2) Store `mode` on `PracticeSession`; (3) Import `core_cefr`; (4) Call `core_cefr.invalidate_profile_cache(updated_card.target_language)` in `rate_card` |
| `src/lingosips/api/app.py` | MODIFY | Import and register `cefr_router` after `progress_router` |
| `frontend/src/features/practice/usePracticeSession.ts` | MODIFY | Pass `mode` as query param to `POST /practice/session/start` |
| `frontend/e2e/features/progress-and-cefr.spec.ts` | MODIFY (or CREATE if missing) | Add CEFR endpoint tests |
| `tests/api/test_practice.py` | MODIFY | Add 2 tests for mode param in session start |

### Files NOT to Modify

| File | Reason |
|------|--------|
| `src/lingosips/core/fsrs.py` | FSRS logic unchanged — rate_card in practice.py already calls it |
| `src/lingosips/core/progress.py` | Progress aggregation unchanged |
| `src/lingosips/api/progress.py` | Progress router unchanged |
| `frontend/src/lib/api.d.ts` | Auto-generated — regenerate after backend changes; NEVER edit manually |
| `frontend/src/routes/progress.tsx` | Story 5.2 adds CefrProfile component here |
| `frontend/src/features/progress/ProgressDashboard.tsx` | Unchanged — Story 5.2 adds alongside it |
| `tests/conftest.py` | `SQLModel.metadata.create_all` picks up new PracticeSession.mode column automatically |

---

### Previous Story Intelligence (from Story 4.3)

- `fake_timers + waitFor` conflict in Vitest tests: TanStack Query's `waitFor` uses `setInterval` — avoid shared `vi.useFakeTimers()` in `beforeEach`
- `speakAttempts` as `useRef` vs `useState`: mutable state in async callbacks → use `useRef` to avoid lint warnings and closure issues
- Pattern for clearing module-level refs/caches in tests: use `autouse` fixtures rather than relying on beforeEach (more reliable cleanup)
- `api.d.ts` auto-generated — after any backend schema change, `openapi-typescript` must regenerate it; CI enforces freshness

---

### Git Context

Most recent commits (relevant to this story):
```
f977f6e Add speak mode practice session with full UI and E2E tests (Story 4.3)
dc8711a Add SyllableFeedback component with tests (Story 4.2)
0473b5a Add speech evaluation API with Whisper and Azure Speech backends (Story 4.1)
8b6b3be Add progress dashboard and session stats (Story 3.5)
```

Key existing files this story builds on:
- `src/lingosips/core/progress.py` — exact pattern for aggregation queries (dataclasses, async functions, UTC helpers, `sa_distinct`, `func.count`)
- `src/lingosips/api/progress.py` — exact pattern for router-delegates-to-core
- `src/lingosips/db/models.py` — `PracticeSession`, `Review`, `Card` table definitions
- `src/lingosips/db/migrations/versions/002_practice_sessions.py` — migration pattern to follow
- `tests/api/test_progress.py` — test fixture pattern (truncate tables in autouse, seed via `session.add()`, check response shape)
- `tests/conftest.py` — shared fixtures: `client`, `session`, `test_engine`, `anyio_backend`

---

### Architecture & Pattern Compliance Checklist

| Constraint | How Satisfied |
|------------|--------------|
| `core/` has no FastAPI imports | `core/cefr.py` uses only `AsyncSession`, `dataclasses`, `json`, `sqlalchemy`, `structlog` |
| `api/` delegates to `core/` | `api/cefr.py` calls `core_cefr.get_profile()`; no aggregation logic in router |
| RFC 7807 error responses | `Query(...)` triggers `validation_exception_handler` for missing `target_language` |
| All JSON fields snake_case | `CefrProfileResponse` uses snake_case throughout |
| No `SQLModel.metadata.create_all()` in production | New `mode` column is added via Alembic migration only |
| TDD — failing tests before implementation | Task 1 creates all tests; Tasks 2–8 implement |
| 90% coverage CI gate | New `core/cefr.py` and `api/cefr.py` must be covered by Tasks 1.1/1.2 |
| No server data in Zustand | No new frontend state; `GET /cefr/profile` will be a TanStack Query call in Story 5.2 |

---

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.1 full AC and description]
- [Source: _bmad-output/planning-artifacts/architecture.md — `core/cefr.py` in implementation sequence (step 6); CEFR Profile Aggregation Engine cross-cutting concern; test file locations `tests/core/test_cefr.py`, `tests/api/test_cefr.py`; performance: indexed queries on `reviews.card_id` and `reviews.reviewed_at`]
- [Source: _bmad-output/project-context.md — Layer architecture (core/ no FastAPI), DB rules (Alembic only), testing rules (TDD, 90% coverage), naming conventions (snake_case JSON), anti-patterns table]
- [Source: src/lingosips/db/models.py — `Card.fsrs_state` column name, `PracticeSession` model, `Review` model with all columns]
- [Source: src/lingosips/core/progress.py — exact aggregation pattern: dataclasses, `sa_distinct`, `func.count`, UTC helpers, `_utc_isoformat`]
- [Source: src/lingosips/api/practice.py — `start_session` function signature (lines 93–125), `rate_card` function (lines 147–173), existing imports]
- [Source: src/lingosips/api/app.py — router registration pattern inside `create_app()`, import pattern, `_spa_routes_exact` set]
- [Source: src/lingosips/db/migrations/versions/002_practice_sessions.py — Alembic migration revision/down_revision pattern]
- [Source: tests/conftest.py — `anyio_backend`, `test_engine`, `session`, `client` fixture definitions]
- [Source: tests/api/test_progress.py — autouse truncate fixture, seed-via-session pattern, response shape assertions]
- [Source: frontend/src/features/practice/usePracticeSession.ts — `startSessionMutation` mutationFn (line ~114), `_mode` param accepted at line 92]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5 (2026-05-02)

### Debug Log References

- Fixed `test_cache_invalidated_after_rating`: FSRS scheduler asserts `card.stability is not None` when processing a Review-state card with stability=0.0 (falsy). Used a separate New-state card for the rating step; Review-state cards are used only for vocabulary seeding.

### Completion Notes List

- ✅ Task 1: All 41 new tests written first (TDD red phase confirmed) — `tests/core/test_cefr.py` (20 tests), `tests/api/test_cefr.py` (10 tests), 2 new tests in `tests/api/test_practice.py`
- ✅ Task 2: `PracticeSession.mode` added to `db/models.py`; Alembic migration `003_practice_session_mode.py` created with revision `c3d4e5f6a1b2` → down_revision `a1b2c3d4e5f6`
- ✅ Task 3: `api/practice.py` updated — `start_session` accepts `mode` query param and stores it; `rate_card` calls `core_cefr.invalidate_profile_cache()` after successful rating
- ✅ Task 4: `core/cefr.py` implemented — `CefrProfile` dataclass, module-level cache dict, `compute_vocabulary_breadth`, `compute_grammar_coverage`, `compute_recall_rate_by_card_type`, `compute_active_passive_ratio`, `map_to_cefr_level` with grammar boost, `get_profile` with cache, `invalidate_profile_cache`
- ✅ Task 5: `api/cefr.py` implemented — `CefrProfileResponse` Pydantic model, `GET /profile` endpoint with required `target_language` query param
- ✅ Task 6: CEFR router registered in `api/app.py` after `progress_router`
- ✅ Task 7: `usePracticeSession.ts` updated — mode passed as query param to `POST /practice/session/start`
- ✅ Task 8: `progress-and-cefr.spec.ts` updated — 3 new CEFR endpoint tests added
- ✅ Full test suite: 715 passed, 0 failed; 94.80% coverage (gate: 90%); all ruff lints clean

### File List

- `src/lingosips/core/cefr.py` — CREATED: CEFR computation engine (vocab breadth, grammar coverage, recall rate, active/passive ratio, level mapping, cache)
- `src/lingosips/api/cefr.py` — CREATED: FastAPI router for `GET /cefr/profile`
- `src/lingosips/db/migrations/versions/003_practice_session_mode.py` — CREATED: Alembic migration adding `mode` column to `practice_sessions`
- `tests/core/test_cefr.py` — CREATED: Unit tests for all `core/cefr.py` functions (20 tests)
- `tests/api/test_cefr.py` — CREATED: API tests for `GET /cefr/profile` (10 tests)
- `src/lingosips/db/models.py` — MODIFIED: Added `mode: str | None = Field(default=None)` to `PracticeSession`
- `src/lingosips/api/practice.py` — MODIFIED: Added `Query` import; `mode` param to `start_session`; `core_cefr.invalidate_profile_cache()` in `rate_card`
- `src/lingosips/api/app.py` — MODIFIED: Added `cefr_router` import and registration
- `frontend/src/features/practice/usePracticeSession.ts` — MODIFIED: `startSessionMutation` passes mode as query param
- `frontend/e2e/features/progress-and-cefr.spec.ts` — MODIFIED: Added `describe("CEFR profile endpoint")` block with 3 E2E tests
- `tests/api/test_practice.py` — MODIFIED: Added `TestSessionMode` class with 2 new tests

### Change Log

- 2026-05-02: Implemented Story 5.1 — CEFR Profile Computation Engine. Created `core/cefr.py` with four-dimension aggregation (vocab breadth, grammar coverage, recall rate by type, active/passive ratio), A1–C2 level mapping with grammar boost, and module-level cache with invalidation. Added `GET /cefr/profile` endpoint. Added Alembic migration 003 for `practice_sessions.mode`. Updated practice session start to persist mode and rate_card to invalidate cache. 715 tests passing, 94.80% coverage.

## Review Findings

### Review Summary — 2026-05-02

**Reviewer:** bmad-code-review (3-layer parallel: Blind Hunter · Edge Case Hunter · Acceptance Auditor)
**Outcome:** 6 patches applied, 2 deferred, 18+ dismissed. All tests pass (718 total, 94.80% coverage).

#### Patches Applied ✅

- [x] [Review][Patch] Ruff formatting: 4 files reformatted to project standard [src/lingosips/api/cefr.py, src/lingosips/core/cefr.py, tests/api/test_cefr.py, tests/core/test_cefr.py]
- [x] [Review][Patch] `_profile_cache` type over-permissive: `dict[str, "CefrProfile | None"]` → `dict[str, "CefrProfile"]`; removed unnecessary `# type: ignore[return-value]` [core/cefr.py:37,74]
- [x] [Review][Patch] `mode` param accepts arbitrary strings — added `Literal["self_assess", "write", "speak"]` validation; FastAPI auto-returns 422 for invalid values [api/practice.py:97]
- [x] [Review][Patch] `compute_recall_rate_by_card_type` could produce `None`-keyed dict entry if `card_type` is null — added `row.card_type is not None` guard [core/cefr.py:142]
- [x] [Review][Patch] Grammar boost exact-boundary (vocab=40, 80% of 50) and zero-vocab (vocab=0) cases untested — added 3 boundary tests [tests/core/test_cefr.py]
- [x] [Review][Patch] Performance test comment misleading: "100 cards" omitted "with 1000 reviews" — corrected to match AC6 intent [tests/api/test_cefr.py:304]

#### Deferred 🔁

- [x] [Review][Defer] Concurrent cache miss: two coroutines can both miss the cache, compute independently, and overwrite each other [core/cefr.py:73] — deferred, pre-existing design decision; asyncio single-threaded, single-user desktop app, impact negligible
- [x] [Review][Defer] `compute_grammar_coverage` loads all `forms` blobs into Python memory [core/cefr.py:101] — deferred, pre-existing; acceptable at single-user scale (<5000 cards per spec notes)
