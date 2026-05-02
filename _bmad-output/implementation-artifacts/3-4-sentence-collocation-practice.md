# Story 3.4: Sentence & Collocation Practice

Status: done

## Story

As a user,
I want to practice full sentence and collocation translation in all practice modes — not just isolated words — so that I develop the ability to use vocabulary in real linguistic context.

## Acceptance Criteria

1. **AI phrase detection**: When a user types a phrase or collocation into the card creation input, the LLM pipeline detects the input type and sets `card_type = "sentence"` or `card_type = "collocation"` (or `"word"` for single words) on the card. The LLM generates an idiomatic meaning explanation, register context (stored in `forms.register_context`), and a contextual example sentence.

2. **Practice queue exposes card metadata**: `GET /practice/session/start` and related queue endpoints include `card_type`, `forms`, `example_sentences` in each `QueueCard` response so the frontend can render type-appropriate UI.

3. **Self-assess display**: A sentence/collocation card shows the full phrase at a scaled, readable size (`text-2xl` for non-word cards) on the front. The revealed state shows: idiomatic translation, register context (when present, from `forms.register_context`), and the first example sentence.

4. **Write mode — paraphrase acceptance**: For sentence/collocation cards in write mode, `POST /practice/cards/{card_id}/evaluate` uses LLM-based semantic evaluation (not strict char diff). Minor paraphrase variations are accepted as correct (`is_correct: true`), structural errors are reported with an explanation. `highlighted_chars` is always `[]` for sentence/collocation cards (char-level diff is not meaningful for paraphrases). The user's raw typed answer is shown with strikethrough styling when `is_correct: false` and `highlighted_chars` is empty.

5. **FSRS scheduling unchanged**: The same FSRS `Again / Hard / Good / Easy` rating row is used regardless of `card_type`. No scheduling logic changes.

6. **Backwards-compatible API**: Existing word cards (no `register_context` in forms, `card_type = "word"`) continue to work identically. The LLM prompt addition is additive.

7. **E2E coverage**: `frontend/e2e/features/practice-sentence-collocation.spec.ts` covers sentence card creation (card_type verified), self-assess reveal of register context, write mode with paraphrase accepted, and write mode with wrong answer showing explanation.

## Tasks / Subtasks

- [x] T1: Update LLM prompt and card creation pipeline (AC: 1)
  - [x] T1.1: Write `tests/core/test_cards.py::TestParseCardResponse` additions FIRST (TDD) — add tests for `card_type` in parsed output (see §TestCoverage)
  - [x] T1.2: Write `tests/core/test_cards.py::TestCreateCardStream` additions FIRST (TDD) — sentence/collocation `card_type` is set on persisted card (see §TestCoverage)
  - [x] T1.3: Update `CARD_SYSTEM_PROMPT` in `core/cards.py` — add `card_type` and `register_context` instruction (see §CardSystemPromptUpdate)
  - [x] T1.4: Update `_parse_llm_response()` to extract and return `card_type` and `register_context` from the parsed JSON
  - [x] T1.5: Update `create_card_stream()` to pass `card_type` from parsed LLM response to `Card()` creation; emit `field_update` event for `card_type`
  - [x] T1.6: Run tests; confirm all pass

- [x] T2: Add `card_type`, `forms`, `example_sentences` to practice API response (AC: 2)
  - [x] T2.1: Write `tests/api/test_practice.py::TestSentenceCardQueue` class FIRST (TDD) — see §TestCoverage
  - [x] T2.2: Add `card_type: str`, `forms: str | None`, `example_sentences: str | None` to `QueueCard` Pydantic model in `api/practice.py` — `model_config = {"from_attributes": True}` already set; these fields exist in `Card` DB model
  - [x] T2.3: Run tests; confirm all pass

- [x] T3: Extend `core/practice.py` for sentence/collocation paraphrase evaluation (AC: 4)
  - [x] T3.1: Write `tests/core/test_practice.py::TestSentenceEvaluation` class FIRST (TDD) — see §TestCoverage
  - [x] T3.2: Add `SENTENCE_EVAL_SYSTEM_PROMPT` constant and `_evaluate_sentence_answer()` async function (see §SentenceEvalFunction)
  - [x] T3.3: Update `evaluate_answer()` to branch on `card.card_type`: word cards use existing exact-match + char-diff; sentence/collocation use `_evaluate_sentence_answer()`
  - [x] T3.4: For sentence evaluation: `highlighted_chars` always `[]`, `is_correct` from LLM JSON response, `suggested_rating` = 3 if correct else 1; LLM timeout/error → `is_correct: false`, `explanation: null`
  - [x] T3.5: Run tests; confirm all pass

- [x] T4: Update frontend `QueueCard` type (AC: 2, 3, 4)
  - [x] T4.1: Add `card_type: string`, `forms: string | null`, `example_sentences: string | null` to `QueueCard` TypeScript interface in `frontend/src/features/practice/usePracticeSession.ts`
  - [x] T4.2: No hook logic changes required — type extension only
  - [x] T4.3: Run `npm run test` to confirm existing tests still pass with widened type

- [x] T5: Update `routes/practice.tsx` to derive display fields (AC: 3)
  - [x] T5.1: Write `practice.test.tsx` additions FIRST (TDD) — see §TestCoverage
  - [x] T5.2: Add `deriveGrammaticalForms(card: QueueCard): string | undefined` and `deriveFirstExampleSentence(card: QueueCard): string | undefined` as module-level helper functions (see §RouteHelpers)
  - [x] T5.3: In the `practicing` phase render block, spread derived fields onto `currentCard` before passing to `PracticeCard`: `card={{ ...currentCard, grammatical_forms: deriveGrammaticalForms(currentCard), example_sentence: deriveFirstExampleSentence(currentCard) }}`
  - [x] T5.4: No changes to `initialState` logic — sentence cards in write mode still start at `"write-active"`

- [x] T6: Update `PracticeCard.tsx` for sentence/collocation display (AC: 3, 4)
  - [x] T6.1: Write `PracticeCard.test.tsx` additions FIRST (TDD) — see §TestCoverage
  - [x] T6.2: Add `userAnswer: string | null` state (init to `null`); set it in the textarea `onKeyDown` Enter handler and in the Submit `onClick` handler before calling `onEvaluate?.()`
  - [x] T6.3: Use card-type-aware text sizing for `target_word`: derive `const targetWordSize = (!card.card_type || card.card_type === "word") ? "text-4xl" : "text-2xl"` and apply to all states that render `target_word` (front, revealed, write-active, write-result)
  - [x] T6.4: In write-result: when `highlighted_chars.length === 0 && !result.is_correct && userAnswer`, render `<span className="text-xl font-mono text-zinc-400 line-through">{userAnswer}</span>` in place of the char-highlight row
  - [x] T6.5: In the revealed state, show grammatical forms label appropriately: for sentence/collocation cards, the `grammatical_forms` prop already contains the `"Register: …"` prefix (set by route helper); render it with the same `text-sm text-zinc-400` style as word grammatical forms — no change needed to the component template

- [x] T7: Regenerate `api.d.ts` (AC: 2)
  - [x] T7.1: Start backend, run `npx openapi-typescript http://localhost:7842/openapi.json -o src/lib/api.d.ts`
  - [x] T7.2: Verify `card_type`, `forms`, `example_sentences` appear on the queue card type in `api.d.ts`

- [x] T8: Validate all tests pass
  - [x] T8.1: `uv run pytest tests/ --cov=src/lingosips --cov-fail-under=90` — 578 passed, 95.31% coverage
  - [x] T8.2: `cd frontend && npm run test -- --coverage` — 327 passed
  - [x] T8.3: Write Playwright E2E: `frontend/e2e/features/practice-sentence-collocation.spec.ts`

---

## Dev Notes

### §WhatAlreadyExists — READ BEFORE TOUCHING ANYTHING

**Do NOT recreate or modify these — they are complete and tested:**

| File | Status | Notes |
|---|---|---|
| `src/lingosips/db/models.py` | ✅ complete | `card_type: str = Field(default="word")` already exists — NO migration needed |
| `src/lingosips/core/fsrs.py` | ✅ complete | Do NOT touch — FSRS logic is card_type-agnostic by design |
| `src/lingosips/api/practice.py` | ✅ partial | ADD 3 fields to `QueueCard` only; do NOT modify existing endpoints |
| `src/lingosips/core/practice.py` | ✅ partial | ADD `_evaluate_sentence_answer()` and branch in `evaluate_answer()` — preserve word card logic exactly |
| `src/lingosips/core/cards.py` | ✅ partial | UPDATE prompt + parser + stream; do NOT change function signatures |
| `frontend/.../PracticeCard.tsx` | ✅ partial | ADD `userAnswer` state + card_type font sizing only — do NOT break existing states |
| `frontend/.../usePracticeSession.ts` | ✅ partial | ADD 3 fields to `QueueCard` type only — do NOT modify hook logic |
| `frontend/.../routes/practice.tsx` | ✅ partial | ADD 2 helper functions + update `card` spread — keep all existing logic unchanged |
| `frontend/src/lib/stores/usePracticeStore.ts` | ✅ complete | Do NOT modify |
| `src/lingosips/services/registry.py` | ✅ complete | `get_llm_provider()` is ready |

**`card_type` column already exists in production schema** — confirmed in `db/models.py:29`:
```python
card_type: str = Field(default="word")  # "word" | "sentence" | "collocation"
```
No Alembic migration required.

**Current `QueueCard` in `api/practice.py`** — ADD only these 3 fields:
```python
class QueueCard(BaseModel):
    id: int
    target_word: str
    translation: str | None
    target_language: str
    due: datetime
    fsrs_state: str
    stability: float
    difficulty: float
    reps: int
    lapses: int
    # ADD THESE THREE:
    card_type: str        # "word" | "sentence" | "collocation"
    forms: str | None     # JSON string — contains register_context for sentence/collocation cards
    example_sentences: str | None  # JSON string — list of example sentences

    model_config = {"from_attributes": True}
```

**Current `QueueCard` TypeScript type in `usePracticeSession.ts`** — ADD only these 3 fields:
```typescript
export type QueueCard = {
  id: number
  target_word: string
  translation: string | null
  target_language: string
  due: string
  fsrs_state: string
  stability: number
  difficulty: number
  reps: number
  lapses: number
  // ADD THESE THREE:
  card_type: string         // "word" | "sentence" | "collocation"
  forms: string | null      // JSON string — contains register_context for sentence/collocation
  example_sentences: string | null  // JSON string
}
```

---

### §CardSystemPromptUpdate — `CARD_SYSTEM_PROMPT` replacement

Replace the entire `CARD_SYSTEM_PROMPT` constant in `core/cards.py` with the following. The key additions:
- `card_type` field the LLM must classify
- `register_context` inside `forms` for phrase/sentence cards
- Detection rules that distinguish word vs. collocation vs. sentence

```python
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
```

**`_parse_llm_response` update** — extract `card_type` and ensure `register_context` is preserved in `forms`:

```python
def _parse_llm_response(raw: str) -> dict:
    # ... existing code to strip fences and parse JSON (DO NOT CHANGE) ...
    
    # Apply defaults for missing fields (UPDATED — add card_type)
    forms = parsed.get(
        "forms",
        {"gender": None, "article": None, "plural": None, "conjugations": {}, "register_context": None},
    )
    # Ensure register_context key always exists in forms
    if "register_context" not in forms:
        forms["register_context"] = None
    
    return {
        "card_type": parsed.get("card_type", "word"),   # ADD
        "translation": parsed.get("translation", ""),
        "forms": forms,
        "example_sentences": parsed.get("example_sentences", []),
    }
```

**`create_card_stream` update** — set `card_type` on Card and emit `field_update`:

```python
# In fields_to_emit, emit card_type first (before translation):
fields_to_emit: list[tuple[str, str | dict | list]] = [
    ("card_type", card_data["card_type"]),      # ADD — emitted first
    ("translation", card_data["translation"]),
    ("forms", card_data["forms"]),
    ("example_sentences", card_data["example_sentences"]),
]

# Card constructor — ADD card_type:
card = Card(
    target_word=request.target_word,
    translation=card_data["translation"],
    forms=json.dumps(card_data["forms"]),
    example_sentences=json.dumps(card_data["example_sentences"]),
    card_type=card_data["card_type"],    # ADD
    target_language=target_language,
    # FSRS columns: all defaults from db/models.py
)
```

---

### §SentenceEvalFunction — `core/practice.py` additions

Add these to `core/practice.py` BELOW the existing `SYSTEM_PROMPT` constant and `_char_diff` function. Do NOT modify existing `SYSTEM_PROMPT`, `CharHighlight`, `EvaluationResult`, `_char_diff`, or the word-card path in `evaluate_answer`.

```python
SENTENCE_EVAL_SYSTEM_PROMPT = (
    "You are a language tutor evaluating sentence translations. "
    "Given a sentence card (target language), the student's English translation, "
    "and the reference translation, decide if the student's answer captures the meaning. "
    "Accept: same meaning in different words, minor grammatical variations, "
    "stylistic paraphrases. "
    "Reject: wrong meaning, missing key information, completely different tone. "
    "Return ONLY a JSON object: "
    '{\"is_correct\": true|false, \"explanation\": \"one sentence or null\"}. '
    "No markdown, no extra text."
)


async def _evaluate_sentence_answer(
    card: Card,
    user_answer: str,
    llm: AbstractLLMProvider,
) -> EvaluationResult:
    """LLM-based semantic evaluation for sentence/collocation cards.

    Does NOT produce char-level diff — highlighted_chars is always [].
    The LLM decides if the user's answer captures the meaning (paraphrase accepted).
    """
    correct_value = (card.translation or "").strip()
    normalized_user = user_answer.strip()

    # Exact match short-circuit (case-insensitive) — no LLM call
    if normalized_user.lower() == correct_value.lower():
        return EvaluationResult(
            is_correct=True,
            highlighted_chars=[],
            correct_value=correct_value,
            explanation=None,
            suggested_rating=3,
        )

    explanation: str | None = None
    is_correct = False

    try:
        messages: list[LLMMessage] = [
            {"role": "system", "content": SENTENCE_EVAL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Sentence (target language): {card.target_word}\n"
                    f"Reference translation: {correct_value}\n"
                    f"Student answered: {normalized_user}"
                ),
            },
        ]
        raw = await asyncio.wait_for(
            llm.complete(messages, max_tokens=128),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        # Parse LLM JSON response
        import json as _json
        raw_stripped = raw.strip()
        if raw_stripped.startswith("```"):
            lines = raw_stripped.splitlines()
            end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "```"), len(lines))
            raw_stripped = "\n".join(lines[1:end]).strip()
        start = raw_stripped.find("{")
        if start != -1:
            import json as _json
            decoded = _json.JSONDecoder().raw_decode(raw_stripped, start)[0]
            is_correct = bool(decoded.get("is_correct", False))
            expl = decoded.get("explanation")
            explanation = str(expl).strip() if expl else None
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("llm_sentence_eval_failed", card_id=card.id, error=str(exc))
        is_correct = False
        explanation = None

    return EvaluationResult(
        is_correct=is_correct,
        highlighted_chars=[],   # never char-diff for sentence/collocation
        correct_value=correct_value,
        explanation=explanation,
        suggested_rating=3 if is_correct else 1,
    )
```

**Updated `evaluate_answer` branch logic** (replace only the routing logic, not the word-card implementation):

```python
async def evaluate_answer(
    card: Card,
    user_answer: str,
    llm: AbstractLLMProvider,
) -> EvaluationResult:
    """Compare user's written answer to the card's translation and get AI feedback.

    For word cards: exact match check → char diff + LLM explanation on wrong answers.
    For sentence/collocation cards: LLM semantic evaluation (paraphrase accepted).
    """
    if card.card_type in ("sentence", "collocation"):
        return await _evaluate_sentence_answer(card, user_answer, llm)

    # Word card — existing exact-match + char-diff logic (unchanged below this line)
    correct_value = (card.translation or "").strip()
    normalized_user = user_answer.strip()
    is_correct = normalized_user.lower() == correct_value.lower()
    # ... rest of existing implementation unchanged ...
```

---

### §RouteHelpers — `routes/practice.tsx` additions

Add these two module-level helper functions **above** the `Route` declaration (not inside the component). They must be pure functions with no imports beyond `QueueCard` type.

```tsx
/** Parse `forms` JSON and produce a display string for the grammatical forms / register context. */
function deriveGrammaticalForms(card: QueueCard): string | undefined {
  if (!card.forms) return undefined
  try {
    const forms = JSON.parse(card.forms) as Record<string, unknown>
    if (card.card_type === "sentence" || card.card_type === "collocation") {
      const registerContext = forms.register_context as string | null | undefined
      return registerContext ? `Register: ${registerContext}` : undefined
    }
    // Word cards: build "Masculine · pl. melancólicos" style string
    const parts: string[] = []
    if (forms.gender && typeof forms.gender === "string") parts.push(forms.gender)
    if (forms.plural && typeof forms.plural === "string") parts.push(`pl. ${forms.plural}`)
    return parts.length > 0 ? parts.join(" · ") : undefined
  } catch {
    return undefined
  }
}

/** Return the first example sentence from the `example_sentences` JSON array. */
function deriveFirstExampleSentence(card: QueueCard): string | undefined {
  if (!card.example_sentences) return undefined
  try {
    const sentences = JSON.parse(card.example_sentences) as string[]
    return sentences[0] ?? undefined
  } catch {
    return undefined
  }
}
```

**Update `practicing` render block** — spread derived fields:

```tsx
// Replace the existing PracticeCard call:
<PracticeCard
  key={currentCard.id}
  card={{
    ...currentCard,
    grammatical_forms: deriveGrammaticalForms(currentCard),
    example_sentence: deriveFirstExampleSentence(currentCard),
  }}
  onRate={(rating) => rateCard(currentCard.id, rating)}
  onEvaluate={(answer) => evaluateAnswer(currentCard.id, answer)}
  evaluationResult={evaluationResult}
  sessionCount={sessionCount}
  initialState={initialState}
/>
```

Note: `grammatical_forms` and `example_sentence` are already in the `PracticeCardProps.card` type as optional extended fields — no prop type change needed.

---

### §PracticeCardUpdates — `PracticeCard.tsx` changes

**Only two changes needed — do NOT touch any other logic:**

**Change 1 — Add `userAnswer` state and capture on submit:**

```tsx
// Add after existing useState declarations (after textareaRef):
const [userAnswer, setUserAnswer] = useState<string | null>(null)

// In textarea onKeyDown (ADD setUserAnswer call):
if (e.key === "Enter") {
  e.preventDefault()
  const val = e.currentTarget.value.trim()
  if (!isEvaluating && val) {
    setUserAnswer(val)    // ADD THIS
    onEvaluate?.(val)
  }
}

// In Submit button onClick (ADD setUserAnswer call):
onClick={() => {
  const val = textareaRef.current?.value.trim()
  if (val) {
    setUserAnswer(val)    // ADD THIS
    onEvaluate?.(val)
  }
}}
```

**Change 2 — Card-type-aware font sizing + userAnswer in write-result:**

```tsx
// Derive target word size once at component level (before any state renders):
const targetWordSize =
  !card.card_type || card.card_type === "word" ? "text-4xl" : "text-2xl"

// Replace all hardcoded "text-4xl" for target_word with {targetWordSize}:
// Line in front state:      <span className={`${targetWordSize} font-semibold text-zinc-50`}>
// Line in write-active:     <span className={`${targetWordSize} font-semibold text-zinc-50`}>
// Line in write-result:     <span className={`${targetWordSize} font-semibold text-zinc-50`}>
// Line in revealed state:   <span className={`${targetWordSize} font-semibold text-zinc-50`}>
```

**Change 3 — Write-result: show userAnswer for sentence cards (no char-highlight):**

```tsx
// Replace the existing highlighted_chars map block with:
{result.highlighted_chars.length > 0 ? (
  <div className="flex flex-wrap gap-0 text-xl font-mono">
    {result.highlighted_chars.map((hc, i) => (
      <span
        key={i}
        className={
          hc.correct
            ? "text-zinc-200"
            : "text-red-400 underline decoration-red-400"
        }
      >
        {hc.char}
      </span>
    ))}
  </div>
) : !result.is_correct && userAnswer ? (
  <span className="text-xl font-mono text-zinc-400 line-through">{userAnswer}</span>
) : null}
```

---

### §TestCoverage — Required New Tests

**`tests/core/test_cards.py`** — ADD to `TestParseCardResponse`:

```python
# ADD these tests (do NOT modify existing tests):
def test_sentence_card_type_extracted():
    """LLM returns card_type=sentence → extracted and returned."""
    raw = json.dumps({
        "card_type": "sentence",
        "translation": "don't play dumb",
        "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}, "register_context": "informal, River Plate Spanish"},
        "example_sentences": ["No te hagas el tonto, te vi.", "Siempre se hace el tonto."],
    })
    result = _parse_llm_response(raw)
    assert result["card_type"] == "sentence"
    assert result["forms"]["register_context"] == "informal, River Plate Spanish"

def test_collocation_card_type_extracted():
    """LLM returns card_type=collocation → extracted."""
    raw = json.dumps({
        "card_type": "collocation",
        "translation": "to bite the dust",
        "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}, "register_context": "informal"},
        "example_sentences": ["El proyecto mordió el polvo.", "Muchos proyectos muerden el polvo."],
    })
    result = _parse_llm_response(raw)
    assert result["card_type"] == "collocation"

def test_missing_card_type_defaults_to_word():
    """Old-format LLM response without card_type → defaults to 'word'."""
    raw = json.dumps({
        "translation": "sad",
        "forms": {"gender": None, "article": None, "plural": None, "conjugations": {}},
        "example_sentences": ["A.", "B."],
    })
    result = _parse_llm_response(raw)
    assert result["card_type"] == "word"

def test_register_context_key_always_present():
    """forms always has register_context key (None for word cards)."""
    raw = json.dumps({
        "card_type": "word",
        "translation": "happy",
        "forms": {"gender": "masculine", "article": "el", "plural": "felices", "conjugations": {}},
        "example_sentences": ["A.", "B."],
    })
    result = _parse_llm_response(raw)
    assert "register_context" in result["forms"]
    assert result["forms"]["register_context"] is None
```

**`tests/core/test_cards.py`** — ADD to `TestCreateCardStream`:

```python
async def test_sentence_card_type_persisted(mock_session, mock_llm_sentence, mock_speech):
    """Sentence card: card_type='sentence' saved to DB and emitted as field_update."""
    # mock_llm_sentence returns JSON with card_type="sentence"
    events = [e async for e in create_card_stream(request, mock_llm_sentence, mock_session, "es", mock_speech)]
    field_updates = [parse_sse(e) for e in events if '"field_update"' in e]
    card_type_event = next((f for f in field_updates if f["data"]["field"] == "card_type"), None)
    assert card_type_event is not None
    assert card_type_event["data"]["value"] == "sentence"
    # Verify DB card has card_type="sentence"
    assert mock_session.added_card.card_type == "sentence"
```

**`tests/api/test_practice.py`** — ADD `TestSentenceCardQueue` class (do NOT modify existing tests):

```python
class TestSentenceCardQueue:
    # Setup: sentence card in DB, check it appears in session with card_type + forms + example_sentences

    async def test_session_includes_card_type_in_response(client, sentence_card_fixture):
        """GET /practice/session/start includes card_type field."""
        response = await client.post("/practice/session/start")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "card_type" in data[0]
        assert data[0]["card_type"] == "sentence"

    async def test_session_includes_forms_and_example_sentences(client, sentence_card_fixture):
        """Queue response includes forms (JSON string) and example_sentences."""
        response = await client.post("/practice/session/start")
        data = response.json()
        assert "forms" in data[0]
        assert "example_sentences" in data[0]

    async def test_word_card_type_defaults_in_response(client, word_card_fixture):
        """Existing word cards show card_type='word' in queue response."""
        response = await client.post("/practice/session/start")
        data = response.json()
        assert data[0]["card_type"] == "word"
```

**`tests/core/test_practice.py`** — ADD `TestSentenceEvaluation` class:

```python
class TestSentenceEvaluation:
    async def test_exact_match_sentence_no_llm_call(card_sentence, mock_llm):
        """Sentence exact match → is_correct=True, LLM not called, highlighted_chars=[]."""
    async def test_paraphrase_accepted_by_llm(card_sentence, mock_llm_accepts_paraphrase):
        """LLM returns is_correct=true for paraphrase → is_correct=True, highlighted_chars=[]."""
    async def test_wrong_sentence_rejected_by_llm(card_sentence, mock_llm_rejects):
        """LLM returns is_correct=false → is_correct=False, explanation populated."""
    async def test_sentence_eval_always_returns_empty_highlighted_chars(card_sentence, mock_llm):
        """highlighted_chars is always [] for sentence cards regardless of result."""
    async def test_sentence_eval_llm_timeout_returns_incorrect_no_explanation(card_sentence, mock_llm_timeout):
        """LLM timeout → is_correct=False, explanation=None."""
    async def test_sentence_eval_llm_json_parse_error_returns_incorrect(card_sentence, mock_llm_bad_json):
        """Malformed LLM JSON → is_correct=False, explanation=None."""
    async def test_collocation_card_uses_sentence_eval_path(card_collocation, mock_llm):
        """card_type='collocation' also goes through _evaluate_sentence_answer()."""
    async def test_word_card_still_uses_char_diff_path(card_word, mock_llm):
        """card_type='word' still uses existing char-diff + exact-match logic."""
```

**`frontend/src/features/practice/PracticeCard.test.tsx`** — ADD to existing describe block:

```typescript
describe("card_type-aware font sizing", () => {
  it("renders target_word at text-4xl for word cards (default)")
  it("renders target_word at text-2xl for sentence cards")
  it("renders target_word at text-2xl for collocation cards")
  it("defaults to text-4xl when card_type is undefined")
})

describe("write-result — sentence card (empty highlighted_chars)", () => {
  it("shows userAnswer with line-through when highlighted_chars=[] and is_correct=false")
  it("does NOT show char-highlight div when highlighted_chars is empty")
  it("still shows correct_value in emerald when is_correct=false")
  it("still shows explanation when present")
})

describe("write-active — userAnswer capture", () => {
  it("captures userAnswer on Enter key submit")
  it("captures userAnswer on Submit button click")
  it("userAnswer state is available for write-result display")
})
```

**`frontend/src/routes/practice.test.tsx`** — ADD:

```typescript
describe("deriveGrammaticalForms", () => {
  it("returns undefined when forms is null")
  it("returns 'Register: informal' for sentence card with register_context")
  it("returns 'Register: …' for collocation card with register_context")
  it("returns 'Masculine · pl. melancólicos' for word card with gender+plural")
  it("returns undefined when register_context is null for sentence card")
})

describe("deriveFirstExampleSentence", () => {
  it("returns first sentence from JSON array")
  it("returns undefined when example_sentences is null")
  it("returns undefined on JSON parse error")
})
```

**`frontend/e2e/features/practice-sentence-collocation.spec.ts`** (Playwright, real backend):

```typescript
test("sentence card created with card_type=sentence and register_context", async ({ page }) => {
  // Type a full sentence into card creation input
  // Verify SSE stream emits card_type=sentence field_update
  // Verify card saved with card_type=sentence (check card detail)
})

test("sentence card in self-assess — revealed shows register context", async ({ page }) => {
  // Seed sentence card with register_context in forms
  // Navigate to /practice
  // Verify phrase shown at smaller size than text-4xl
  // Press Space to reveal
  // Verify register context visible: "Register: informal..."
  // Verify example sentence visible
})

test("sentence card write mode — paraphrase accepted", async ({ page }) => {
  // Seed sentence card; navigate to /practice?mode=write
  // Type a valid paraphrase of the translation
  // Submit — verify write-result shows ✓ Correct
  // Verify FSRS row shows Good pre-selected
})

test("sentence card write mode — wrong answer shows explanation and correct value", async ({ page }) => {
  // Type completely wrong translation
  // Verify: no char-highlight row; userAnswer shown with line-through
  // Verify: correct value shown in emerald
  // Verify: explanation text (or "Evaluation unavailable — rate manually")
})

test("mixed session — word and sentence cards use same FSRS rating row", async ({ page }) => {
  // Seed both a word card and a sentence card
  // Rate the word card — verify normal flow
  // Rate the sentence card — verify same Again/Hard/Good/Easy row
})
```

---

### §AntiPatterns — Do NOT Do These

| Anti-Pattern | Correct Approach |
|---|---|
| Add Alembic migration for `card_type` | Column already exists in schema — NO migration needed |
| Modify `core/fsrs.py` for card_type | FSRS scheduling is card_type-agnostic — do NOT touch |
| Use char diff for sentence/collocation evaluation | `highlighted_chars = []` always for sentence/collocation; use `_evaluate_sentence_answer()` |
| Modify existing word-card path in `evaluate_answer` | Only ADD the `if card.card_type in ("sentence", "collocation"): return` branch at the top |
| Parse `forms` JSON inside `PracticeCard.tsx` | Parse in `routes/practice.tsx` helpers; pass as string props to PracticeCard |
| Add `card_type` to `PracticeCardProps` directly | `card_type` is already on `QueueCard` type — access via `card.card_type` |
| Reinvent LLM JSON parsing for sentence evaluation | Re-use `json.JSONDecoder().raw_decode()` pattern (already established in `core/cards.py`) |
| Modify `QueueCard` in conftest for practice tests | Add new fixtures; do NOT break 31 existing `TestEvaluateAnswer` tests |
| Remove `CARD_SYSTEM_PROMPT` `card_type` from old LLM responses | `_parse_llm_response` defaults `card_type` to `"word"` — old response format is backward-compatible |
| Show char highlights for sentence cards | `highlighted_chars: []` is the correct response from the API — frontend handles empty array gracefully |
| Wrap `_evaluate_sentence_answer` in a separate module | Add directly to `core/practice.py` — it's the same domain (practice evaluation) |
| Import `json` again inside `_evaluate_sentence_answer` | Add `import json as _json` locally within the function OR import `json` at module level if not already there (it currently is NOT imported in `core/practice.py` — it uses `difflib` and `asyncio` only; add `import json` at module level) |

---

### §GitContext — Patterns from Recent Commits

From Story 3.3 implementation (commit: `9841389`):
- `core/practice.py` uses `asyncio.wait_for` with `LLM_TIMEOUT_SECONDS = 10.0` — follow same pattern for `_evaluate_sentence_answer`
- LLM error handling: `except (asyncio.TimeoutError, Exception) as exc:` → log warning, return safe fallback
- `structlog.get_logger(__name__)` is the logger — use it in `_evaluate_sentence_answer`
- `field_validator` pattern with `return stripped` (not `v`) is established in `api/practice.py` — don't reintroduce
- Tests use `AsyncMock(spec=AbstractLLMProvider)` fixture pattern — follow for `mock_llm_accepts_paraphrase` etc.
- Git commit style: lowercase, imperative, story reference in parens — e.g. "Add sentence/collocation practice support (Story 3.4)"

---

### §BreakingTestFix — MUST UPDATE EXISTING TESTS (or they will FAIL)

**Adding `card_type` as the first `field_update` event breaks these existing tests by shifting all indices. You MUST update them as part of T1:**

**`tests/core/test_cards.py`** (currently `line 243–247`):
```python
# BEFORE (will fail):
assert len(field_updates) == 4  # translation, forms, example_sentences, audio
assert field_updates[2]["data"]["field"] == "example_sentences"
assert field_updates[3]["data"]["field"] == "audio"

# AFTER (update to):
assert len(field_updates) == 5  # card_type, translation, forms, example_sentences, audio
assert field_updates[3]["data"]["field"] == "example_sentences"
assert field_updates[4]["data"]["field"] == "audio"
```

**`tests/api/test_cards.py`** (currently `lines 145–149`):
```python
# BEFORE (will fail):
assert len(field_updates) == 4  # translation, forms, example_sentences, audio
assert field_updates[0]["data"]["field"] == "translation"
assert field_updates[1]["data"]["field"] == "forms"
assert field_updates[2]["data"]["field"] == "example_sentences"
assert field_updates[3]["data"]["field"] == "audio"

# AFTER (update to):
assert len(field_updates) == 5  # card_type, translation, forms, example_sentences, audio
assert field_updates[0]["data"]["field"] == "card_type"
assert field_updates[1]["data"]["field"] == "translation"
assert field_updates[2]["data"]["field"] == "forms"
assert field_updates[3]["data"]["field"] == "example_sentences"
assert field_updates[4]["data"]["field"] == "audio"
```

These files are in the **UPDATE** list. Failing to make these changes will cause `test_card_creation_stream_emits_all_fields` (and related) to fail immediately.

---

### §FieldUpdateSequence — New SSE field_update order

After adding `card_type` to `fields_to_emit`, the stream now emits in this order:
```
event: field_update    data: {"field": "card_type", "value": "sentence"}
event: field_update    data: {"field": "translation", "value": "don't play dumb"}
event: field_update    data: {"field": "forms", "value": {..., "register_context": "informal"}}
event: field_update    data: {"field": "example_sentences", "value": [...]}
[optional] event: field_update    data: {"field": "audio", "value": "/cards/42/audio"}
event: complete        data: {"card_id": 42}
```

The `CardCreationPanel.tsx` frontend parses these events already. The `card_type` field is new — if `CardCreationPanel` collects field updates (not just the final complete event), it may receive this new event. Check `CardCreationPanel.tsx` for how it handles unknown fields: it should silently ignore `card_type` field updates since it only uses `card_id` from the `complete` event for navigation.

> **VERIFY**: Before emitting `card_type` in the stream, open `frontend/src/features/cardCreation/CardCreationPanel.tsx` and confirm it handles unknown `field_update` field names gracefully (doesn't crash).

---

### References

- Story 3.4 AC: [Source: `_bmad-output/planning-artifacts/epics.md` lines 923–949]
- PRD phrase/collocation enrichment story: [Source: `_bmad-output/planning-artifacts/prd.md` — "Rising Action" paragraph for collocation card scenario]
- `card_type` DB column: [Source: `src/lingosips/db/models.py:29`]
- `CARD_SYSTEM_PROMPT`: [Source: `src/lingosips/core/cards.py:78`]
- `_parse_llm_response`: [Source: `src/lingosips/core/cards.py:117`]
- `create_card_stream` fields_to_emit: [Source: `src/lingosips/core/cards.py:212`]
- `QueueCard` model: [Source: `src/lingosips/api/practice.py:26`]
- `evaluate_answer`: [Source: `src/lingosips/core/practice.py:310`]
- `_char_diff`: [Source: `src/lingosips/core/practice.py:291`]
- `LLM_TIMEOUT_SECONDS`: [Source: `src/lingosips/core/practice.py:264`]
- `PracticeCard` state machine: [Source: `frontend/src/features/practice/PracticeCard.tsx:22`]
- `QueueCard` TS type: [Source: `frontend/src/features/practice/usePracticeSession.ts:21`]
- `routes/practice.tsx` practicing phase: [Source: `frontend/src/routes/practice.tsx:113`]
- `grammatical_forms` prop in PracticeCard: [Source: `frontend/src/features/practice/PracticeCard.tsx:49`]
- Existing `mock_llm` fixture pattern: [Source: `tests/api/test_practice.py:578`]
- SSE envelope spec: [Source: `_bmad-output/project-context.md §API Design Rules`]
- Layer architecture rule: [Source: `_bmad-output/project-context.md §Layer Architecture`]
- TDD requirement: [Source: `_bmad-output/project-context.md §Testing Rules`]
- No cross-feature imports: [Source: `_bmad-output/project-context.md §Feature isolation`]
- E2E spec file pattern: [Source: `_bmad-output/project-context.md §E2E Playwright`]
- FR23 coverage requirement: [Source: `_bmad-output/project-context.md §E2E` — `practice-sentence-collocation` maps to FR23]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (claude-sonnet-4-6)

### Debug Log References

None — implementation proceeded smoothly following story spec.

### Completion Notes List

- **T1**: Updated `CARD_SYSTEM_PROMPT` with `card_type`/`register_context` instructions. Updated `_parse_llm_response()` to extract `card_type` (defaults to `"word"`) and ensure `register_context` key always present in `forms`. Updated `create_card_stream()` to emit `card_type` as first `field_update` and pass it to `Card()`. Fixed breaking tests in `test_cards.py` and `test_api/test_cards.py` to expect 5 field_updates (not 4).
- **T2**: Added `card_type: str`, `forms: str | None`, `example_sentences: str | None` to `QueueCard` Pydantic model — `from_attributes=True` handles auto-mapping from DB model. Added `TestSentenceCardQueue` covering all 4 scenarios.
- **T3**: Added `import json` at module level, `SENTENCE_EVAL_SYSTEM_PROMPT`, `_evaluate_sentence_answer()` with exact-match short-circuit, LLM JSON parsing, timeout/error handling. Updated `evaluate_answer()` to route `sentence`/`collocation` card types to the new path. 8 new unit tests in `TestSentenceEvaluation`.
- **T4**: Extended `QueueCard` TypeScript type with `card_type`, `forms`, `example_sentences` — type-only change, no hook logic modified. All 307 existing tests still pass.
- **T5**: Created `deriveGrammaticalForms()` and `deriveFirstExampleSentence()` as exported module-level helpers in `routes/practice.tsx`. Updated `practicing` render block to spread derived fields onto `card` prop. 11 new helper unit tests added to `practice.test.tsx`.
- **T6**: Added `userAnswer` state and `targetWordSize` derived constant to `PracticeCard`. Updated all 4 `target_word` render sites to use `targetWordSize`. Updated write-result to show `userAnswer` with line-through when `highlighted_chars=[]` and `!result.is_correct`. Verified `useCardStream.ts` handles unknown `field_update` field names gracefully. Added 12 new tests in 3 new describe blocks.
- **T7**: Restarted backend with updated code; regenerated `api.d.ts` via `openapi-typescript`. Verified `card_type`, `forms`, `example_sentences` appear in `QueueCard` schema.
- **T8**: 578 backend tests pass (95.31% coverage, threshold 90%). 327 frontend tests pass. E2E spec `practice-sentence-collocation.spec.ts` written with 8 tests covering AC 2, 4, 5, 6.

### File List

**CREATE (new files):**
- `frontend/e2e/features/practice-sentence-collocation.spec.ts`

**UPDATE (existing files):**
- `src/lingosips/core/cards.py` — update CARD_SYSTEM_PROMPT, _parse_llm_response, create_card_stream
- `src/lingosips/core/practice.py` — add SENTENCE_EVAL_SYSTEM_PROMPT, _evaluate_sentence_answer(), update evaluate_answer() routing; add `import json` at module level
- `src/lingosips/api/practice.py` — add card_type, forms, example_sentences to QueueCard model
- `tests/core/test_cards.py` — ⚠️ UPDATE existing `assert len(field_updates) == 4` to `== 5` and fix index offsets (see §BreakingTestFix); ADD new card_type tests
- `tests/api/test_cards.py` — ⚠️ UPDATE existing field_updates index assertions (see §BreakingTestFix)
- `tests/api/test_practice.py` — add TestSentenceCardQueue class
- `tests/core/test_practice.py` — add TestSentenceEvaluation class
- `frontend/src/features/practice/usePracticeSession.ts` — add card_type, forms, example_sentences to QueueCard type
- `frontend/src/routes/practice.tsx` — add deriveGrammaticalForms/deriveFirstExampleSentence helpers; update practicing phase card spread
- `frontend/src/routes/practice.test.tsx` — add helper function tests
- `frontend/src/features/practice/PracticeCard.tsx` — add userAnswer state, card_type font sizing, empty highlighted_chars write-result handling
- `frontend/src/features/practice/PracticeCard.test.tsx` — add card_type and sentence write-result tests
- `frontend/src/lib/api.d.ts` — regenerated via openapi-typescript

**DO NOT TOUCH:**
- `src/lingosips/db/models.py` (card_type already there, no migration)
- `src/lingosips/core/fsrs.py` (scheduling is card_type-agnostic)
- `frontend/src/lib/stores/usePracticeStore.ts`
- `frontend/src/features/practice/usePracticeSession.ts` hook logic (type only)
- All existing tests in `tests/api/test_practice.py` (31 tests — add only)
- All existing tests in `tests/core/test_practice.py` (add only)
- `src/lingosips/db/migrations/` (no schema change needed)

### Review Findings

- [x] [Review][Patch] E501: `api/practice.py:38` comment too long — shortened inline comments [`src/lingosips/api/practice.py:37-39`]
- [x] [Review][Patch] E501: `core/cards.py:166` default forms dict too long — broke across lines [`src/lingosips/core/cards.py:165-172`]
- [x] [Review][Patch] UP041: `asyncio.TimeoutError` redundant in `except` clause — replaced with `except Exception` [`src/lingosips/core/practice.py:142`]
- [x] [Review][Patch] E402: `import json as _json` at non-top position — moved to module top [`tests/core/test_practice.py:7`]
- [x] [Review][Patch] UP041: `asyncio.TimeoutError()` in test helper — replaced with builtin `TimeoutError()` [`tests/core/test_practice.py`]
- [x] [Review][Patch] Dead code: `formsPayload` computed but never sent in PATCH request [`frontend/e2e/features/practice-sentence-collocation.spec.ts`]
- [x] [Review][Patch] Dead code: `createSentenceCardDirectly()` defined but never called — removed [`frontend/e2e/features/practice-sentence-collocation.spec.ts`]
- [x] [Review][Patch] `QueueCard.card_type: string` should be narrowed to literal union — changed to `"word" | "sentence" | "collocation"` [`frontend/src/features/practice/usePracticeSession.ts`]
- [x] [Review][Patch] `str(expl).strip() if expl else None` passes `"null"` string as explanation — added null-sentinel filter [`src/lingosips/core/practice.py:141`]
- [x] [Review][Patch] `card_type` from LLM not normalized — added validation to default unknown values to `"word"` [`src/lingosips/core/cards.py:178-181`]
- [x] [Review][Patch] Stale comment "Stories 3.4+" for speak stubs — updated to "Stories 3.5+" [`frontend/src/features/practice/PracticeCard.tsx:167`]
- [x] [Review][Patch] `!card.card_type` dead guard removed after narrowing type — simplified to `card.card_type === "word"` [`frontend/src/features/practice/PracticeCard.tsx:124`]

## Change Log

| Date | Description |
|---|---|
| 2026-05-02 | Story created — ready for dev |
| 2026-05-02 | Story implemented — sentence/collocation practice support added (Story 3.4). Updated CARD_SYSTEM_PROMPT, _parse_llm_response, create_card_stream (T1); added card_type/forms/example_sentences to QueueCard API (T2); added _evaluate_sentence_answer() with LLM-based paraphrase evaluation (T3); extended TypeScript QueueCard type (T4); added deriveGrammaticalForms/deriveFirstExampleSentence helpers (T5); updated PracticeCard with card_type-aware font sizing and userAnswer state (T6); regenerated api.d.ts (T7); all tests pass 578 backend / 327 frontend (T8). |
| 2026-05-02 | Code review complete — 12 patch findings fixed. Linter clean (ruff). 578 backend / 327 frontend tests all pass. Story status set to done. |
