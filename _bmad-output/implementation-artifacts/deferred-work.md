# Deferred Work

## Deferred from: code review of 1-4-first-run-language-onboarding (2026-04-30)

- **Race condition in `get_or_create_settings`** — Two concurrent first-launch requests on an empty DB could both INSERT a Settings row. Very unlikely for a local single-process SQLite app with uvicorn single-worker. Consider adding `INSERT OR IGNORE` or a `SELECT FOR UPDATE` equivalent if moving to multi-process deployment. File: `src/lingosips/core/settings.py:59`

- **`target_languages` not synced with `active_target_language`** — When `active_target_language` changes via `PUT /settings`, the `target_languages` JSON list is not updated. These are distinct concepts (`target_languages` = all languages ever learned; `active_target_language` = current one), so this is by design for now. Future story implementing multi-language deck management (Story 2.2) should reconcile these fields.

- **`api.d.ts` 422 response type is `HTTPValidationError`** — FastAPI's OpenAPI schema declares 422 as `HTTPValidationError` for all endpoints, but `PUT /settings` actually returns a custom RFC 7807 Problem Detail dict for invalid language codes. The generated type is misleading. Fix: add `responses={422: {"model": ProblemDetail}}` to the `@router.put` decorator and create a `ProblemDetail` Pydantic model. Not a runtime bug since the wizard's `onError` handler receives the error as an `Error` object, not the typed response body.

## Deferred from: code review of 1-5-ai-provider-abstraction-local-llm-fallback (2026-05-01)

- **T2.7 `get_download_progress` missing on `ModelManager`** — Spec required an `async get_download_progress(job_id, session)` method on `ModelManager` (T2.7). The implementation inlined equivalent polling logic directly in `api/models.py`. Behavior is equivalent, but the `ModelManager` contract is incomplete. Refactor to extract the method if a second consumer needs it. File: `src/lingosips/services/models/manager.py`

- **AC4 `Depends(get_llm_provider)` not wired to any router** — Story 1.5 AC4 states the provider must always be resolved via `FastAPI Depends(get_llm_provider)` in routers. No router uses it yet — deferred to Story 1.7 (`api/cards.py`).

- **TOCTOU in `_get_llm`: file deleted between `exists()` and `Llama()` construction** — `model_path.exists()` passes, then the file is deleted before `Llama(model_path=…)` executes, raising an opaque native exception instead of `LLMModelNotReadyError`. Wrap the `Llama()` instantiation in a try/except. Extreme edge case; deferred MVP. File: `src/lingosips/services/llm/qwen_local.py:27`

- **`progress_done` reset to 0 on failure wipes real progress** — `_update_job(0, 0, …, "failed")` in the download exception handler loses the bytes-downloaded context. Consider preserving the last-known `done`/`total` values. In `# pragma: no cover` path. File: `src/lingosips/services/models/manager.py:140`

- **`is_ready()` no integrity check** — Only checks file existence and non-zero size. A corrupt or partial GGUF file passes the check. Consider adding size validation against the expected model size. Out of MVP scope.

- **SSE holds long-lived SQLAlchemy session** — `_model_download_sse` holds the `AsyncSession` open for potentially many minutes (entire download duration). Sessions are not designed as long-lived objects; idle timeout can cause disconnects. MVP acceptable; consider periodic session refresh or a separate session per poll for production. File: `src/lingosips/api/models.py`

- **No auth on `/models/status` and `/models/download/progress`** — Any unauthenticated caller can trigger a multi-GB download. No auth system exists in MVP. Add rate-limiting or auth in a future security hardening story.

- **`_qwen_provider` singleton never invalidated if model path changes** — Once set, `_qwen_provider` in `registry.py` is cached forever. If the model filename changes (future settings API), the stale provider is returned. Add invalidation logic when Story 2.3 (Service Configuration) lands. File: `src/lingosips/services/registry.py`

## Deferred from: code review of 1-6-speech-provider-abstraction-local-tts-fallback (2026-05-01)

- **Race condition in `_pyttsx3_provider` singleton** — Two concurrent `get_speech_provider()` calls could both observe `None` and create two `Pyttsx3Provider` instances before either assignment completes. Benign because `Pyttsx3Provider` is stateless (no shared engine), and the FastAPI event loop is single-threaded, making the scenario effectively impossible in the async runtime. Matches the pre-existing `_qwen_provider` pattern. File: `src/lingosips/services/registry.py:90`

## Deferred from: code review of 1-8-card-audio-generation-tts (2026-05-01)

- **Business logic in `get_card_audio` router** — Path construction and `audio_path.exists()` check live directly in the router (`api/cards.py:68`), violating the "routers delegate to core" rule. Spec explicitly defines this design and justifies it (consistent with ModelManager pattern, avoids unnecessary DB query). Revisit if a second consumer of audio path logic emerges. File: `src/lingosips/api/cards.py:68`

- **TOCTOU race between `exists()` check and `FileResponse` delivery** — `audio_path.exists()` passes, then the file could theoretically be deleted before Starlette streams it. `FileResponse` lazy-loads during ASGI response, so no `FileNotFoundError` is catchable at construction time. Negligible for a local single-user app. File: `src/lingosips/api/cards.py:69`

- **Autouse fixture ordering fragility in `test_tts_failure_card_created_no_stream_error`** — The test overrides `app.dependency_overrides[get_speech_provider]` and removes it in `finally`, leaving the autouse fixture's teardown `.pop()` as a no-op. Works correctly via safe-pop semantics but the teardown order dependency is fragile. Refactor: configure the failure via the autouse mock rather than setting a second override. File: `tests/api/test_cards.py:316`

## Deferred from: code review of 1-7-card-creation-api-sse-streaming (2026-05-01)

- **No pagination on `GET /practice/queue`** — Endpoint fetches all due cards with no `LIMIT`. For users with hundreds of due cards this allocates the entire result set in one response. Explicitly deferred to Story 3.1 (`GET /practice/queue` FSRS session management). File: `src/lingosips/api/practice.py:47`

- **Empty LLM response persists card with `translation=""`** — `_parse_llm_response("{}")` returns `{"translation": "", ...}`. An empty string passes the safety filter (empty text is always safe) and the card is persisted with `translation=""`. No product decision exists on minimum field quality requirements. Consider adding a post-parse validation step that rejects empty `translation` with an error SSE event. File: `src/lingosips/core/cards.py:128`

- **AC7 latency SLA not enforced or measured** — AC7 requires the first `field_update` within 500ms (OpenRouter) / 2s (local Qwen). There is no timing measurement, first-token assertion, or monitoring counter in the implementation. The 10s `asyncio.wait_for` timeout bounds the total call but not first-token latency. Needs an observability/monitoring approach — not unit-testable in isolation.

## Deferred from: code review of 2-5-deck-export-import-lingosips-format (2026-05-01)

- **Session atomicity: `create_deck()` commits before cards are created** — `import_lingosips_deck()` calls `create_deck()` which commits the deck row, then adds cards in the same session. If `session.flush()` or audio writes fail afterward, the deck is committed with no cards (orphaned empty deck). Fixing requires refactoring `create_deck()` to support caller-controlled commit, which changes the interface used by all deck creation paths. Accepted MVP trade-off; all core functions commit eagerly. File: `src/lingosips/core/imports.py:181`, `src/lingosips/core/decks.py:100`

- **409 routing via error message string match** — `start_lingosips_import` routes to 409 by checking `"conflict" in msg.lower()`. Couples HTTP status to internal `ValueError` message content. A more robust approach: create a `DeckConflictError(ValueError)` custom exception in `core/decks.py` and catch it specifically in the router. Not a current correctness issue since no other code path raises `ValueError("conflict")` in this flow. File: `src/lingosips/api/imports.py:241`

## Deferred from: code review of 3-1-fsrs-scheduling-engine-practice-queue (2026-05-01)

- **No rollback on exception in `rate_card`** — If `session.commit()` raises (e.g., DB timeout, FK violation), there is no `try/except/rollback` in `core/fsrs.py`. In practice the SQLAlchemy async session context manager handles rollback at the router level; acceptable for MVP single-process SQLite. File: `src/lingosips/core/fsrs.py`

- **No authorization check on `card_id` ownership in `POST /practice/cards/{card_id}/rate`** — Any caller can rate any card by PK with no ownership or deck membership check. MVP is a single-user local app so this is not a security risk now; add access control if multi-user mode is introduced. File: `src/lingosips/api/practice.py`

- **Queue count in "in-session" status bar can go stale** — `QueueWidget` in-session mode shows `{queue.length} remaining` but the `["practice","queue"]` query is not refetched during a session. The displayed count does not decrement as cards are rated. Epic 3.2 (self-assess session management) owns session-level query invalidation. File: `frontend/src/features/practice/QueueWidget.tsx`

- **`fsrs_card.last_review` timezone coercion not verified** — `db_card.last_review` is set from `fsrs_card.last_review` which the fsrs library assigns internally. No assertion that the returned datetime is timezone-aware. Works with fsrs v6.3.1 in current tests; verify if upgrading the library. File: `src/lingosips/core/fsrs.py`

## Deferred from: code review of 4-1-speech-evaluation-api-whisper-azure-speech (2026-05-02)

- **`WhisperModel` instantiated per request** — Expensive (model weights loaded fresh each call) but intentional for MVP simplicity. The spec explicitly acknowledges the per-call approach and instructs to "add caching if tests show SLA violation". File: `src/lingosips/services/speech/whisper_local.py:84`

- **`asyncio.wait_for` cannot cancel executor thread** — When `wait_for` times out, the coroutine is cancelled but the background thread running `_evaluate_sync` (model load + inference) keeps running. Leaks threads under load. Known Python limitation; acceptable for single-user MVP. File: `src/lingosips/services/speech/whisper_local.py:55`

- **`_build_syllable_result` substring match causes false-positive `overall_correct`** — `target_clean in trans_clean` means short words (e.g., `"a"`, `"el"`) match inside any transcription. Intentional MVP heuristic; the spec notes the algorithm is "not linguistically precise". File: `src/lingosips/services/speech/whisper_local.py:137`

- **Naive CV syllabification — language-agnostic and phonetically imprecise** — `_syllabify()` and `_syllabify_from_azure()` split on Latin vowels only. Correct per spec: "adequate for per-syllable UX; not linguistically precise". Files: `whisper_local.py:101`, `azure.py:205`

- **No request body size cap on audio upload** — `await request.body()` reads entire body with no size guard. A crafted request can exhaust server memory. Out of scope for Story 4.1; address in a security hardening story. File: `src/lingosips/api/practice.py:299`

- **`is_ready()` does not validate model file integrity** — Returns `True` for any non-empty directory; a partially-downloaded or corrupted model passes. MVP trade-off; `WhisperModel` will raise an error at inference time. File: `src/lingosips/services/models/whisper_manager.py:37`

- **`_downloading` flag stuck `True` if OS kills the download thread** — `finally` block handles Python exceptions but not OOM-kills or segfaults. No TTL or watchdog mechanism. Restart required to recover. MVP acceptable. File: `src/lingosips/services/models/whisper_manager.py:119`

- **`asyncio.to_thread()` wraps a coroutine in `api/services.py`** — Pre-existing bug from a prior story: `AzureSpeechProvider.synthesize()` is `async def` but passed to `asyncio.to_thread()` (for sync callables), so the Azure Speech connection-test path is broken. Out of scope for Story 4.1. File: `src/lingosips/api/services.py:208`

- **"Speech model downloading…" UI string absent** — AC6 requires the frontend to show this string. Frontend integration belongs to Story 4.3 (speak-mode-practice-session), which is backlog. File: frontend/src/features/practice/ (not yet created)

- **2-second SLA not enforced at timeout level** — All timeouts are 10s by design. The 2s target is a goal, not a hard enforcement boundary. Spec comment: `# hard limit; 2s SLA is the goal`. If real-world performance is insufficient, cache the `WhisperModel` instance or move to lazy-init (see whisper_local.py §PerformanceSLA). File: `src/lingosips/services/speech/whisper_local.py:21`
