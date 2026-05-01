# Deferred Work

## Deferred from: code review of 1-4-first-run-language-onboarding (2026-04-30)

- **Race condition in `get_or_create_settings`** — Two concurrent first-launch requests on an empty DB could both INSERT a Settings row. Very unlikely for a local single-process SQLite app with uvicorn single-worker. Consider adding `INSERT OR IGNORE` or a `SELECT FOR UPDATE` equivalent if moving to multi-process deployment. File: `src/lingosips/core/settings.py:59`

- **`target_languages` not synced with `active_target_language`** — When `active_target_language` changes via `PUT /settings`, the `target_languages` JSON list is not updated. These are distinct concepts (`target_languages` = all languages ever learned; `active_target_language` = current one), so this is by design for now. Future story implementing multi-language deck management (Story 2.2) should reconcile these fields.

- **`api.d.ts` 422 response type is `HTTPValidationError`** — FastAPI's OpenAPI schema declares 422 as `HTTPValidationError` for all endpoints, but `PUT /settings` actually returns a custom RFC 7807 Problem Detail dict for invalid language codes. The generated type is misleading. Fix: add `responses={422: {"model": ProblemDetail}}` to the `@router.put` decorator and create a `ProblemDetail` Pydantic model. Not a runtime bug since the wizard's `onError` handler receives the error as an `Error` object, not the typed response body.
