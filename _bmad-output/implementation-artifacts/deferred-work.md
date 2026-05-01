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

## Deferred from: code review of 1-7-card-creation-api-sse-streaming (2026-05-01)

- **No pagination on `GET /practice/queue`** — Endpoint fetches all due cards with no `LIMIT`. For users with hundreds of due cards this allocates the entire result set in one response. Explicitly deferred to Story 3.1 (`GET /practice/queue` FSRS session management). File: `src/lingosips/api/practice.py:47`

- **Empty LLM response persists card with `translation=""`** — `_parse_llm_response("{}")` returns `{"translation": "", ...}`. An empty string passes the safety filter (empty text is always safe) and the card is persisted with `translation=""`. No product decision exists on minimum field quality requirements. Consider adding a post-parse validation step that rejects empty `translation` with an error SSE event. File: `src/lingosips/core/cards.py:128`

- **AC7 latency SLA not enforced or measured** — AC7 requires the first `field_update` within 500ms (OpenRouter) / 2s (local Qwen). There is no timing measurement, first-token assertion, or monitoring counter in the implementation. The 10s `asyncio.wait_for` timeout bounds the total call but not first-token latency. Needs an observability/monitoring approach — not unit-testable in isolation.
