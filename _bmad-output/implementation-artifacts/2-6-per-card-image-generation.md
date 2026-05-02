# Story 2.6: Per-Card Image Generation

Status: review

## Story

As a user,
I want to optionally generate an image for any card using a configured image generation endpoint,
so that visual memory hooks can strengthen my vocabulary retention.

## Acceptance Criteria

1. **Given** a card is open in CardDetail and an image endpoint is configured
   **When** I click "Add image"
   **Then** an image generation request is sent to the configured endpoint (OpenAI image generation REST format) with the target word as the prompt

2. **Given** image generation completes
   **When** the image is received
   **Then** `core/safety.py` validates the response: content-type must be `image/*` (detected from magic bytes) and size must not exceed 10 MB
   **And** if validation passes, the image is stored at `~/.lingosips/images/{card_id}.{ext}` and `card.image_url` is set to `/cards/{card_id}/image`
   **And** the image is shown in CardDetail

   _Note: MVP image safety = content-type + size validation only. The keyword/pattern blocklist in `core/safety.py` is text-only and does NOT apply to image binaries._

3. **Given** an image fails the safety check
   **When** the filter rejects it
   **Then** the message "Image filtered — please try again" is shown
   **And** the card is saved without an image (`image_url` remains null)

4. **Given** no image generation endpoint is configured (no `IMAGE_ENDPOINT_URL` in keyring)
   **When** CardDetail renders
   **Then** the "Add image" button is replaced by "Image endpoint not configured · Configure in Settings" text
   **And** no request is made (endpoint configuration is checked client-side via `GET /services/status`)

5. **Given** I click "Skip image" on a card
   **When** I skip
   **Then** `card.image_skipped` is set to `True` and any existing `image_url` is cleared
   **And** the card shows "Image skipped · Undo" with the skip state

6. **Given** image generation fails (API error, timeout, or non-200 response)
   **When** the error occurs
   **Then** a specific error message is shown naming what failed and what to do next
   **And** the card is saved without an image — image failure does NOT block card save or any other card operation

7. **Given** `GET /cards/{card_id}/image` is called
   **When** an image file exists for that card
   **Then** the image file is returned with the correct `image/*` media type
   **And** 404 RFC 7807 is returned if no image file exists

API tests: successful generation + safety pass → 200 CardResponse with image_url; safety rejection → 422 with "Image filtered" message; endpoint not configured → 422 RFC 7807 with type `/errors/image-endpoint-not-configured`; generation timeout → 422 with timeout message; 404 on GET image for card without image.

## Tasks / Subtasks

- [x] T1: Create `services/image.py` — ImageService (AC: 1, 2)
  - [x] T1.1: Write failing tests in `tests/services/test_image_routing.py`:
    - `ImageService.generate()` happy path: valid PNG bytes returned
    - `ImageService.generate()` timeout raises `asyncio.TimeoutError`
    - `ImageService.generate()` non-200 response raises `RuntimeError` with status code
    - `ImageService.generate()` uses Bearer token header when api_key provided
    - `ImageService.generate()` omits Authorization header when api_key is None
  - [x] T1.2: Create `src/lingosips/services/image.py`:
    ```python
    import asyncio, base64, httpx, structlog
    logger = structlog.get_logger(__name__)
    IMAGE_GENERATION_TIMEOUT = 30.0  # seconds

    class ImageService:
        """HTTP client for OpenAI-format image generation REST endpoints."""

        def __init__(self, endpoint_url: str, api_key: str | None):
            self.endpoint_url = endpoint_url.rstrip("/")
            self.api_key = api_key

        async def generate(self, prompt: str, size: str = "512x512") -> bytes:
            """Generate image. Returns raw image bytes. Raises RuntimeError on non-200. Raises asyncio.TimeoutError on timeout."""
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            async with httpx.AsyncClient(timeout=IMAGE_GENERATION_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.endpoint_url}/v1/images/generations",
                    headers=headers,
                    json={"prompt": prompt, "n": 1, "size": size, "response_format": "b64_json"},
                )
            if resp.status_code != 200:
                logger.warning("image.generation_failed", status=resp.status_code)
                raise RuntimeError(f"Image endpoint returned {resp.status_code}")
            data = resp.json()
            b64_data = data["data"][0]["b64_json"]
            return base64.b64decode(b64_data)
    ```
  - [x] T1.3: Confirm tests pass

- [x] T2: Update `services/registry.py` — add `get_image_service()` + `image_endpoint_configured` to `ServiceStatusInfo` (AC: 4)
  - [x] T2.1: Add `image_endpoint_configured: bool = False` field to `ServiceStatusInfo` dataclass
  - [x] T2.2: Update `get_service_status_info()`: add `image_url = get_credential(IMAGE_ENDPOINT_URL)` check, set `image_endpoint_configured = bool(image_url)`
  - [x] T2.3: Add `get_image_service()` function:
    ```python
    def get_image_service():
        """Return ImageService if endpoint configured. Raises HTTP 422 if not configured."""
        from lingosips.services.image import ImageService
        endpoint_url = get_credential(IMAGE_ENDPOINT_URL)
        if not endpoint_url:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "/errors/image-endpoint-not-configured",
                    "title": "Image endpoint not configured",
                    "detail": "Configure an image generation endpoint in Settings to use this feature",
                    "status": 422,
                },
            )
        api_key = get_credential(IMAGE_ENDPOINT_KEY)
        return ImageService(endpoint_url=endpoint_url, api_key=api_key)
    ```
  - [x] T2.4: No tests needed for T2 — covered by existing `get_service_status_info()` tests

- [x] T3: Update `api/services.py` — extend `ServiceStatusResponse` with `image` field (AC: 4)
  - [x] T3.1: Write failing test in `tests/api/test_services.py` (or add to existing): `GET /services/status` returns `image.configured` field
  - [x] T3.2: Add `ImageServiceStatus(BaseModel)` with `configured: bool` field
  - [x] T3.3: Add `image: ImageServiceStatus` to `ServiceStatusResponse`
  - [x] T3.4: Update `get_service_status()` handler: `image=ImageServiceStatus(configured=info.image_endpoint_configured)`
  - [x] T3.5: Confirm tests pass

- [x] T4: Update `core/safety.py` — add `check_image()` (AC: 2, 3)
  - [x] T4.1: Write failing tests in `tests/core/test_safety.py`:
    - `check_image("image/png", 1024)` → `(True, None)`
    - `check_image("image/jpeg", 1024)` → `(True, None)`
    - `check_image("application/json", 1024)` → `(False, "content-type must be image/*")`
    - `check_image("image/png", 11_000_000)` → `(False, "image exceeds 10 MB")`
    - `check_image("image/png", 10_485_760)` → `(True, None)` — boundary: exactly 10 MB is OK
    - `check_image("image/png", 10_485_761)` → `(False, ...)` — one byte over fails
    - `_detect_image_content_type(png_magic_bytes)` → `"image/png"`
    - `_detect_image_content_type(jpeg_magic_bytes)` → `"image/jpeg"`
    - `_detect_image_content_type(unknown_bytes)` → `None`
  - [x] T4.2: Add to `core/safety.py`:
    ```python
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    _IMAGE_MAGIC: list[tuple[bytes, bytes | None, int | None, str]] = [
        # (prefix, secondary_check_at_offset, secondary_bytes, content_type)
        (b"\x89PNG\r\n\x1a\n", None, None, "image/png"),
        (b"\xff\xd8", None, None, "image/jpeg"),
        (b"GIF87a", None, None, "image/gif"),
        (b"GIF89a", None, None, "image/gif"),
        (b"RIFF", b"WEBP", 8, "image/webp"),
    ]

    def _detect_image_content_type(data: bytes) -> str | None:
        """Detect image content-type from magic bytes. Returns None if unrecognized."""
        for entry in _IMAGE_MAGIC:
            prefix = entry[0]
            if data[:len(prefix)] == prefix:
                if len(entry) == 4 and entry[1]:  # secondary check
                    sec_bytes, sec_offset = entry[1], entry[2]
                    if data[sec_offset:sec_offset + len(sec_bytes)] == sec_bytes:
                        return entry[3]
                    continue
                return entry[3]
        return None

    def check_image(content_type: str, size_bytes: int) -> tuple[bool, str | None]:
        """Check whether image data is safe to display.

        Returns:
            (True, None) if image passes all safety checks
            (False, reason) if image fails any check
        """
        if not content_type.startswith("image/"):
            logger.warning("safety.image_invalid_content_type", content_type=content_type)
            return False, "content-type must be image/*"
        if size_bytes > MAX_IMAGE_SIZE_BYTES:
            logger.warning("safety.image_too_large", size_bytes=size_bytes)
            return False, f"image exceeds 10 MB ({size_bytes} bytes)"
        return True, None
    ```
  - [x] T4.3: Confirm tests pass. Existing `check_text()` tests must still pass.

- [x] T5: Update `core/cards.py` — add `generate_card_image()` + extend `update_card()` (AC: 2, 5, 6)
  - [x] T5.1: Write failing tests in `tests/core/test_cards.py`:
    - `test_generate_card_image_success`: mock ImageService returns PNG bytes → card.image_url set, file written to IMAGE_DIR
    - `test_generate_card_image_safety_rejected`: mock ImageService returns non-image bytes → raises ValueError("Image filtered")
    - `test_generate_card_image_size_exceeds_limit`: mock ImageService returns >10MB bytes → raises ValueError("Image filtered")
    - `test_generate_card_image_timeout`: mock ImageService raises asyncio.TimeoutError → raises ValueError with timeout message
    - `test_generate_card_image_api_error`: mock ImageService raises RuntimeError → raises ValueError with error message
    - `test_update_card_image_skipped_clears_image_url`: update with image_skipped=True clears image_url
    - `test_update_card_image_skipped_false_leaves_image_url_unchanged`: image_skipped=False doesn't clear image_url
  - [x] T5.2: Add to `core/cards.py`:
    ```python
    from lingosips.services.image import ImageService  # TYPE_HINT ONLY — import inside function

    IMAGE_DIR = Path.home() / ".lingosips" / "images"

    _CONTENT_TYPE_EXT: dict[str, str] = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
    }

    async def generate_card_image(
        card_id: int,
        image_service: "ImageService",
        session: AsyncSession,
    ) -> Card:
        """Generate and store image for a card.

        Raises ValueError on safety rejection, timeout, or API error.
        Never modifies card if generation fails — card stays intact.
        """
        from lingosips.services.image import ImageService as _ImageService  # avoid circular at module level

        card = await get_card(card_id, session)  # raises ValueError if not found

        try:
            image_bytes = await asyncio.wait_for(
                image_service.generate(card.target_word),
                timeout=_ImageService.IMAGE_GENERATION_TIMEOUT if hasattr(_ImageService, "IMAGE_GENERATION_TIMEOUT") else 30.0,
            )
        except TimeoutError:
            logger.warning("cards.image_generation_timeout", card_id=card_id)
            raise ValueError("Image generation timed out — please try again")
        except RuntimeError as exc:
            logger.warning("cards.image_generation_error", card_id=card_id, exc=str(exc))
            raise ValueError(f"Image generation failed: {exc}")

        # Safety check — detect content type from magic bytes
        content_type = safety._detect_image_content_type(image_bytes) or "application/octet-stream"
        is_safe, reason = safety.check_image(content_type, len(image_bytes))
        if not is_safe:
            logger.warning("cards.image_safety_rejected", card_id=card_id, reason=reason)
            raise ValueError("Image filtered — please try again")

        # Store image
        ext = _CONTENT_TYPE_EXT.get(content_type, "png")
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        image_path = IMAGE_DIR / f"{card_id}.{ext}"
        await asyncio.to_thread(image_path.write_bytes, image_bytes)

        card.image_url = f"/cards/{card_id}/image"
        card.image_skipped = False  # generation success clears any prior skip
        card.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(card)
        logger.info("cards.image_generated", card_id=card_id, size=len(image_bytes), ext=ext)
        return card
    ```
  - [x] T5.3: Extend `update_card()` in `core/cards.py` — add after existing `if "example_sentences"` block:
    ```python
    if "image_skipped" in update_data:
        card.image_skipped = update_data["image_skipped"]
        if update_data["image_skipped"]:
            card.image_url = None  # clear image when skipped
    if "image_url" in update_data:
        card.image_url = update_data["image_url"]
    ```
  - [x] T5.4: Confirm all core card tests pass (existing 463 backend tests must still pass)

- [x] T6: Update `api/cards.py` — add image endpoints + extend PATCH (AC: 1, 2, 3, 6, 7)
  - [x] T6.1: Write failing tests in `tests/api/test_cards.py`:

    **`TestGenerateCardImage`:**
    - `test_generate_card_image_success`: mock configured ImageService + PNG bytes → 200, `image_url` in response
    - `test_generate_card_image_endpoint_not_configured`: no IMAGE_ENDPOINT_URL credential → 422 with type `/errors/image-endpoint-not-configured`
    - `test_generate_card_image_safety_rejected`: ImageService returns non-image bytes → 422 with "Image filtered" message
    - `test_generate_card_image_timeout`: ImageService raises TimeoutError → 422 with timeout detail
    - `test_generate_card_image_card_not_found`: card_id=9999 → 404 RFC 7807
    - `test_generate_card_image_api_error`: ImageService raises RuntimeError → 422 with error detail

    **`TestGetCardImage`:**
    - `test_get_card_image_success`: image file at IMAGE_DIR/{card_id}.png exists → 200 with image/png content-type
    - `test_get_card_image_not_found`: no image file → 404 RFC 7807

    **`TestPatchCardImageSkipped`:**
    - `test_patch_card_image_skipped_true`: PATCH with `{image_skipped: true}` → 200, `image_skipped=true`, `image_url=null`
    - `test_patch_card_image_skipped_false_undo`: PATCH with `{image_skipped: false}` → 200, `image_skipped=false`

  - [x] T6.2: Add to `CardUpdateRequest` in `api/cards.py`:
    ```python
    image_skipped: bool | None = None
    ```
  - [x] T6.3: Add to `patch_card()` handler in `api/cards.py`:
    ```python
    if "image_skipped" in request.model_fields_set:
        update_data["image_skipped"] = request.image_skipped
    ```
  - [x] T6.4: Add new endpoints to `api/cards.py`:
    ```python
    from lingosips.services.image import ImageService
    from lingosips.services.registry import get_image_service

    @router.post("/{card_id}/generate-image", response_model=CardResponse)
    async def generate_card_image_endpoint(
        card_id: int,
        session: AsyncSession = Depends(get_session),
        image_service: ImageService = Depends(get_image_service),
    ) -> CardResponse:
        """Trigger image generation for a card.
        422 if endpoint not configured (Depends raises); 422 on safety/timeout/error; 404 if card missing.
        """
        try:
            card = await core_cards.generate_card_image(card_id, image_service, session)
        except ValueError as exc:
            msg = str(exc)
            if "does not exist" in msg:
                raise HTTPException(
                    status_code=404,
                    detail={"type": "/errors/card-not-found", "title": "Card not found",
                            "detail": msg, "status": 404},
                )
            raise HTTPException(
                status_code=422,
                detail={"type": "/errors/image-generation-failed", "title": "Image generation failed",
                        "detail": msg, "status": 422},
            )
        return _card_to_response(card)

    @router.get("/{card_id}/image")
    async def get_card_image(card_id: int) -> FileResponse:
        """Serve stored image for a card. 404 RFC 7807 if no image file exists."""
        for ext in ("png", "jpg", "jpeg", "gif", "webp"):
            path = IMAGE_DIR_IMAGES / f"{card_id}.{ext}"
            if path.exists():
                media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
                return FileResponse(path, media_type=media_type)
        raise HTTPException(
            status_code=404,
            detail={"type": "/errors/image-not-found", "title": "Image not found",
                    "detail": f"No image file for card {card_id}", "status": 404},
        )
    ```
    **Note on `IMAGE_DIR_IMAGES`:** Import `IMAGE_DIR` from `core/cards.py` (same as `AUDIO_DIR`) or define locally. Recommend importing from core: `from lingosips.core.cards import IMAGE_DIR as IMAGE_DIR_IMAGES`. Check if `AUDIO_DIR` is already imported — it is (`from lingosips.core.cards import AUDIO_DIR, CardCreateRequest`). Just add `IMAGE_DIR` to that import.
  - [x] T6.5: Confirm all API card tests pass

- [x] T7: Frontend — Update CardDetail (AC: 1–6)
  - [x] T7.1: Write failing tests `CardDetail.test.tsx`:
    - `image-generating` state: "Add image" button disabled / shows "Generating..." during mutation
    - `image-generated` state: `img` element rendered with `src={card.image_url}` when `card.image_url` is set
    - `image-skipped` state: "Image skipped · Undo" text when `card.image_skipped=true`
    - `image-not-configured`: "Image endpoint not configured · Configure in Settings" text shown when `serviceStatus.image.configured=false`
    - `add-image-click`: calls `POST /cards/{cardId}/generate-image` when "Add image" clicked
    - `skip-image-click`: calls `PATCH /cards/{cardId}` with `{image_skipped: true}` when "Skip image" clicked
    - `undo-skip-click`: calls `PATCH /cards/{cardId}` with `{image_skipped: false}` when "Undo" clicked
    - `generation-error`: shows toast notification with error message detail on mutation failure
    - Keyboard: "Add image" button receives focus (tab order); "Skip image" receives focus
  - [x] T7.2: Update `CardDetailState` type in `CardDetail.tsx`:
    ```typescript
    type CardDetailState = "viewing" | "confirm-delete" | "deleting" | "image-generating"
    ```
  - [x] T7.3: Add service status query to `CardDetail.tsx`:
    ```typescript
    interface ServiceStatusResponse {
      llm: { provider: string; model: string | null }
      speech: { provider: string }
      image: { configured: boolean }  // NEW field
    }
    const { data: serviceStatus } = useQuery<ServiceStatusResponse>({
      queryKey: ["services", "status"],
      queryFn: () => get<ServiceStatusResponse>("/services/status"),
    })
    const imageConfigured = serviceStatus?.image?.configured ?? false
    ```
  - [x] T7.4: Add image generation mutation:
    ```typescript
    const generateImage = useMutation({
      mutationFn: () => post<CardResponse>(`/cards/${cardId}/generate-image`, {}),
      onMutate: () => setState("image-generating"),
      onSuccess: (updated) => {
        setState("viewing")
        queryClient.setQueryData(["cards", cardId], updated)
      },
      onError: (err: unknown) => {
        setState("viewing")
        const message = err instanceof ApiError
          ? (err.detail ?? "Image generation failed")
          : "Image generation failed"
        useAppStore.getState().addNotification({ type: "error", message })
      },
    })
    ```
  - [x] T7.5: Add skip image mutation:
    ```typescript
    const skipImage = useMutation({
      mutationFn: (skipped: boolean) =>
        patch<CardResponse>(`/cards/${cardId}`, { image_skipped: skipped }),
      onSuccess: (updated) => {
        queryClient.setQueryData(["cards", cardId], updated)
      },
      onError: (err: unknown) => {
        const message = err instanceof ApiError ? (err.detail ?? "Failed to update image") : "Failed to update image"
        useAppStore.getState().addNotification({ type: "error", message })
      },
    })
    ```
  - [x] T7.6: Add image section JSX to the card body (between Audio and Personal Note sections):
    ```tsx
    {/* Image section */}
    <div className="border-b border-zinc-800 pb-4 mb-4">
      <h2 className="text-sm font-medium text-zinc-300 uppercase tracking-wide mb-2">Image</h2>

      {/* Show existing image */}
      {card.image_url && (
        <img
          src={card.image_url}
          alt={`Visual for ${card.target_word}`}
          className="rounded-md mb-2 max-h-48 object-contain"
        />
      )}

      {/* Skipped state */}
      {card.image_skipped && !card.image_url && (
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <span>Image skipped</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => skipImage.mutate(false)}
            aria-label="Undo skip image"
          >
            Undo
          </Button>
        </div>
      )}

      {/* Not configured */}
      {!imageConfigured && !card.image_url && !card.image_skipped && (
        <p className="text-sm text-zinc-500">
          Image endpoint not configured ·{" "}
          <Link to="/settings" className="text-indigo-400 hover:text-indigo-300 underline">
            Configure in Settings
          </Link>
        </p>
      )}

      {/* Action buttons — only if configured and no image yet (or has image for regen) */}
      {imageConfigured && !card.image_skipped && (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => generateImage.mutate()}
            disabled={state === "image-generating"}
            aria-label={card.image_url ? "Regenerate image" : "Add image"}
          >
            {state === "image-generating"
              ? "Generating..."
              : card.image_url ? "Regenerate" : "Add image"}
          </Button>
          {!card.image_url && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => skipImage.mutate(true)}
              aria-label="Skip image generation for this card"
            >
              Skip image
            </Button>
          )}
        </div>
      )}
    </div>
    ```
  - [x] T7.7: Confirm all CardDetail tests pass. Existing CardDetail tests must still pass.

- [x] T8: E2E tests (AC: 1–6)
  - [x] T8.1: Add to `frontend/e2e/features/card-management.spec.ts`:
    - `image-not-configured`: navigate to card detail → image section shows "not configured" text when no endpoint set
    - `image-generate-success` (skip or mark as skipped in CI environment since real endpoint not available)
    - `image-skip`: click "Skip image" → image_skipped state shown
    - `image-skip-undo`: undo skip → action buttons return
  - [x] T8.2: Regenerate `frontend/src/lib/api.d.ts` from updated OpenAPI schema

## Dev Notes

### §FileChangeSummary — Files to Create/Modify

| File | Change | Why |
|---|---|---|
| `src/lingosips/services/image.py` | **NEW** | OpenAI-format image generation HTTP client |
| `src/lingosips/services/registry.py` | **UPDATE** | Add `get_image_service()` + `image_endpoint_configured` to `ServiceStatusInfo` |
| `src/lingosips/core/safety.py` | **UPDATE** | Add `check_image()` + `_detect_image_content_type()` helper |
| `src/lingosips/core/cards.py` | **UPDATE** | Add `IMAGE_DIR` constant, `generate_card_image()`, extend `update_card()` for `image_skipped`/`image_url` |
| `src/lingosips/api/cards.py` | **UPDATE** | Add `POST /cards/{card_id}/generate-image`, `GET /cards/{card_id}/image`; extend `CardUpdateRequest` + `patch_card()` with `image_skipped` |
| `src/lingosips/api/services.py` | **UPDATE** | Add `ImageServiceStatus` model + `image` field to `ServiceStatusResponse`; update `get_service_status()` handler |
| `tests/services/test_image_routing.py` | **NEW** | ImageService unit tests |
| `tests/api/test_cards.py` | **UPDATE** | Add `TestGenerateCardImage`, `TestGetCardImage`, `TestPatchCardImageSkipped` |
| `tests/core/test_cards.py` | **UPDATE** | Add `TestGenerateCardImageCore` |
| `tests/core/test_safety.py` | **UPDATE** | Add `TestCheckImage`, `TestDetectImageContentType` |
| `tests/api/test_services.py` | **UPDATE** | Add test for `image` field in status response |
| `frontend/src/features/cards/CardDetail.tsx` | **UPDATE** | Add image section, `image-generating` state, service status query |
| `frontend/src/features/cards/CardDetail.test.tsx` | **UPDATE** | Add image state machine tests |
| `frontend/e2e/features/card-management.spec.ts` | **UPDATE** | Add image E2E tests |
| `frontend/src/lib/api.d.ts` | **REGENERATED** | After new endpoints |

**DO NOT modify:**
- `src/lingosips/db/models.py` — `image_url` and `image_skipped` already on `Card` model (confirmed)
- `src/lingosips/services/credentials.py` — `IMAGE_ENDPOINT_URL` and `IMAGE_ENDPOINT_KEY` already defined (confirmed)
- `src/lingosips/api/app.py` — all routers already registered
- Any migration file — no schema changes needed

### §ExistingCardModelConfirmed — No Migration Required

`db/models.py` already has both required fields on `Card`:
```python
image_url: str | None = None
image_skipped: bool = Field(default=False)
```
**No Alembic migration.** This was pre-planned in the initial schema (Story 1.1).

### §ExistingCredentialsConfirmed — Image Keys Already Defined

`services/credentials.py` already has:
```python
IMAGE_ENDPOINT_URL = "image_endpoint_url"
IMAGE_ENDPOINT_KEY = "image_endpoint_key"
```
And `api/services.py` already handles `POST /services/credentials` with `image_endpoint_url`/`image_endpoint_key` fields. The image credential SAVE and TEST flows already exist — Story 2.6 only adds the actual image GENERATION using those credentials.

### §ExistingServiceStatusEndpoint — Must Extend, Not Replace

`GET /services/status` is at `api/services.py` line 61. Currently returns `ServiceStatusResponse` with only `llm` and `speech` fields. Add `image: ImageServiceStatus` as a new required field. **Do NOT make it optional** — it should always be present so frontend can rely on it.

`ServiceStatusInfo` in `registry.py` currently has:
```python
llm_provider: str
llm_model: str | None
speech_provider: str
last_llm_latency_ms: float | None = None
last_llm_success_at: str | None = None
last_speech_latency_ms: float | None = None
last_speech_success_at: str | None = None
```
Add: `image_endpoint_configured: bool = False`

**Existing test for service status** (in `tests/api/test_services.py`) must be updated to expect the new `image` field in the response — or it will fail if tests check exact response shapes. Review existing tests before adding new ones.

### §ImageGenerationAPIFormat — OpenAI-Format Request Body

The endpoint follows OpenAI image generation API format (NFR22):
```
POST {endpoint_url}/v1/images/generations
Authorization: Bearer {api_key}   (omit header if no api_key)
Content-Type: application/json

{
  "prompt": "melancólico",
  "n": 1,
  "size": "512x512",
  "response_format": "b64_json"
}
```
Response (200):
```json
{
  "data": [{"b64_json": "<base64-encoded-image-bytes>"}]
}
```
**Always use `response_format: "b64_json"`** — avoids dealing with expiring URLs from hosted endpoints. The base64 data is decoded in `ImageService.generate()` before returning.

### §ImageSafetyCheckApproach — Magic Bytes, Not HTTP Content-Type

The OpenAI image API response is `application/json` (containing b64_json), not `image/*`. The safety check validates the **decoded image bytes** using magic byte detection — NOT the HTTP Content-Type header from the image API response.

`_detect_image_content_type(data: bytes)` inspects the first few bytes:
- PNG: `\x89PNG\r\n\x1a\n` (8 bytes)
- JPEG: `\xff\xd8` (2 bytes)
- GIF: `GIF87a` or `GIF89a` (6 bytes)
- WebP: `RIFF` (0–3) + `WEBP` (8–11)

If magic bytes match a known image type → content_type = `"image/png"` etc. → `check_image()` passes.
If bytes are unrecognized → content_type = `"application/octet-stream"` → `check_image()` rejects (not `image/*`).

### §ImageStoragePath — Analogous to AUDIO_DIR

Audio: `AUDIO_DIR = Path.home() / ".lingosips" / "audio"` (in `core/cards.py` line 25)  
Image: `IMAGE_DIR = Path.home() / ".lingosips" / "images"` (add to `core/cards.py`)

Images stored as `{card_id}.{ext}` where ext is determined from detected content type.

The `GET /cards/{card_id}/image` endpoint probes for files with known extensions. Import `IMAGE_DIR` into `api/cards.py` alongside the existing `AUDIO_DIR` import.

**Current import in api/cards.py:** `from lingosips.core.cards import AUDIO_DIR, CardCreateRequest`  
**Updated import:** `from lingosips.core.cards import AUDIO_DIR, IMAGE_DIR, CardCreateRequest`

### §GetImageServiceAsDependency — Depends() Pattern

`get_image_service()` in `registry.py` follows the same HTTPException-raising pattern as `get_llm_provider()` (which raises 503 when model not ready). `get_image_service()` raises 422 when not configured. Used as `Depends(get_image_service)` in the router — FastAPI will return the 422 immediately before the handler runs.

```python
# In api/cards.py
from lingosips.services.registry import get_llm_provider, get_speech_provider, get_image_service
from lingosips.services.image import ImageService

@router.post("/{card_id}/generate-image", response_model=CardResponse)
async def generate_card_image_endpoint(
    card_id: int,
    session: AsyncSession = Depends(get_session),
    image_service: ImageService = Depends(get_image_service),
) -> CardResponse:
```

### §UpdateCardExtension — Preserve Existing Behavior

Current `update_card()` in `core/cards.py` handles: `translation`, `personal_note`, `deck_id`, `forms`, `example_sentences`.

Adding `image_skipped` and `image_url` must NOT change behavior for existing fields. The new block goes AFTER the `example_sentences` block, BEFORE `card.updated_at = datetime.now(UTC)`.

Critical rule: when `image_skipped=True`, clear `image_url=None`. This prevents a card from showing both a skip badge and an image.

### §FrontendServiceStatusQuery — New Query in CardDetail

CardDetail currently uses `useQuery(["cards", cardId])`. Adding service status check:
```typescript
useQuery({
  queryKey: ["services", "status"],
  queryFn: () => get<ServiceStatusResponse>("/services/status"),
  staleTime: 30_000,  // 30s — endpoint configured status doesn't change often
})
```
TanStack Query key `["services", "status"]` matches the API path `/services/status`. This is the first consumer of this query in `features/cards/` — other components (`ServiceStatusIndicator`) may already use a similar query. Check `ServiceStatusIndicator.tsx` to see if it uses the same key — if so, the result will be shared from cache.

### §FrontendPostHelper — `post()` in client.ts

`CardDetail.tsx` currently uses `get()`, `patch()`, `del()` from `@/lib/client`. The image generation mutation needs `post<CardResponse>()`. Check that `post()` is exported from `@/lib/client` — it should be (used by other features for import). Import it: `import { get, patch, del, post, ApiError } from "@/lib/client"`.

### §ImageSectionUXPatterns — Button Hierarchy

Per UX spec (Button Hierarchy):
- "Add image" is a **secondary action** — use `variant="outline"` (ghost/zinc-bordered)
- "Skip image" is a **secondary action** — use `variant="ghost"`
- "Regenerate" is **secondary** — use `variant="outline"`
- "Undo" is **secondary** — use `variant="ghost"`
- Disabled state: button at 40% opacity, no hover effect (shadcn handles this with `disabled` prop)

Per UX spec (Error Pattern): error messages must name (1) what failed, (2) why if known, (3) what to do next. Examples:
- Timeout: "Image generation timed out — please try again"
- Safety reject: "Image filtered — please try again"
- API error: "Image generation failed: [endpoint returned 429] — check your image endpoint"
- Not configured: "Image endpoint not configured · Configure in Settings" (with Link)

### §PreviousStoryLearnings — From Story 2.5

1. **`asyncio.to_thread()` for file writes** — already used in `core/cards.py` line 240 for audio writes. Use same pattern for image writes: `await asyncio.to_thread(image_path.write_bytes, image_bytes)`.

2. **`app.dependency_overrides.pop()` in test fixtures** — use safe-pop, not `.clear()`. For mocking `get_image_service`, use the same override pattern as mock_llm_provider in existing tests.

3. **`concurrency = ["greenlet", "thread"]` in pyproject.toml** — already fixed; verify still present so async DB calls show as covered.

4. **No synchronous disk I/O in async handlers** — the review found and fixed blocking disk I/O in Story 2.5. Apply `asyncio.to_thread()` from the start for `image_path.write_bytes()` and `image_path.exists()` (if needed).

5. **TanStack Query `await screen.findByText()`** not `screen.getByText()` for async content.

6. **`vi.stubGlobal()` pattern** — not needed here (no `URL.createObjectURL`). Standard `vi.fn()` mocks suffice.

7. **Ruff linter** — run `ruff check --fix` before committing. Common issues: E501 (line length), F401 (unused imports), I001 (import order). Keep imports in: stdlib → third-party → local order.

8. **`URL.createObjectURL` not available in jsdom** — not applicable here (we use `<img src="...">`, not blob URLs). `src={card.image_url}` renders as a regular URL — no special test setup needed.

### §TestingPattern — Mocking ImageService in API Tests

Follow the same pattern used for `mock_llm_provider` in `tests/conftest.py`:
```python
@pytest.fixture
def mock_image_service():
    """Mock ImageService that returns valid 1x1 PNG bytes."""
    _PNG_1X1 = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x11\x00\x01n\xfe\xc5S\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    service = AsyncMock()
    service.generate = AsyncMock(return_value=_PNG_1X1)
    return service

# In test:
async def test_generate_card_image_success(self, client, seed_card, mock_image_service, app):
    app.dependency_overrides[get_image_service] = lambda: mock_image_service
    try:
        resp = await client.post(f"/cards/{seed_card.id}/generate-image")
        assert resp.status_code == 200
        data = resp.json()
        assert data["image_url"] == f"/cards/{seed_card.id}/image"
    finally:
        app.dependency_overrides.pop(get_image_service, None)
```

For "endpoint not configured" test: override `get_image_service` to raise the 422 HTTPException, or do NOT override it and ensure no IMAGE_ENDPOINT_URL credential is set in the test environment (the default).

### §ImageFileCleanup — No File Deletion in MVP

When a card is deleted (`DELETE /cards/{card_id}`), the image file at `IMAGE_DIR/{card_id}.*` is NOT cleaned up in this story. This is acceptable MVP behavior — same as audio files (no audio cleanup on card delete in `delete_card()`). Document as known limitation.

When `image_skipped=True` is set, `card.image_url` is cleared in DB but the image file (if one exists) is NOT deleted from disk. The `GET /cards/{card_id}/image` endpoint would still serve it if someone calls it directly, but the card's `image_url` would be null. This is acceptable MVP behavior.

### §ServiceStatusIndicatorImpact — Check for Breaking Change

`ServiceStatusIndicator.tsx` in `frontend/src/components/` uses the service status API. After extending `ServiceStatusResponse` with an `image` field, verify that `ServiceStatusIndicator` still works correctly — it should, since the existing `llm` and `speech` fields are unchanged. The new `image` field is additive. Check `ServiceStatusIndicator.test.tsx` and update mocked response shapes if tests use exact response matching.

### Project Structure Notes

- `services/image.py` is at `src/lingosips/services/image.py` (not inside a subdirectory). Architecture spec and directory listing both confirm this is a single flat module, unlike `services/llm/` and `services/speech/` which are packages. Do NOT create `services/image/` directory.
- New test file `tests/services/test_image_routing.py` — note the `tests/services/` directory exists (contains `test_llm_routing.py`, `test_speech_routing.py`, `test_model_manager.py` per architecture).
- `CardDetail.tsx` extends existing state machine with `"image-generating"`. The current 3-state machine (`"viewing" | "confirm-delete" | "deleting"`) grows to 4 states. All existing state transitions remain unchanged.
- Frontend image section renders between Audio and Personal Note sections in CardDetail.

### References

- Card model fields `image_url`, `image_skipped`: `src/lingosips/db/models.py` (confirmed, no migration needed)
- Image credentials: `src/lingosips/services/credentials.py` lines 29–30 — `IMAGE_ENDPOINT_URL`, `IMAGE_ENDPOINT_KEY`
- Existing service status endpoint: `src/lingosips/api/services.py` lines 56–81 — `ServiceStatusResponse`, `GET /services/status`
- `get_llm_provider()` pattern (HTTPException in registry): `src/lingosips/services/registry.py`
- `AUDIO_DIR` pattern: `src/lingosips/core/cards.py` line 25; `asyncio.to_thread` file write: line 240
- `update_card()` current implementation: `src/lingosips/core/cards.py` lines 278–305
- Audio endpoint pattern: `api/cards.py` lines 190–209 — `GET /{card_id}/audio` using `FileResponse`
- `CardDetail.tsx` current state machine: `CardDetailState = "viewing" | "confirm-delete" | "deleting"`
- Architecture spec (services/image.py): `_bmad-output/planning-artifacts/architecture.md` §Complete Directory Structure
- Image generation API format (NFR22): `_bmad-output/planning-artifacts/epics.md` NFR22
- Image safety check spec: Story 2.6 AC, `_bmad-output/planning-artifacts/epics.md` lines 786–788
- Button hierarchy (secondary = ghost/zinc-bordered): `_bmad-output/planning-artifacts/ux-design-specification.md` §Button Hierarchy
- Project rules: `_bmad-output/project-context.md` — all naming, layer architecture, testing rules

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-7 (2026-05-01)

### Debug Log References

- T1: `respx` not installed — switched to `unittest.mock` patch of `httpx.AsyncClient` for service-layer tests (consistent with existing test patterns)
- T5: Removed bare `import monkeypatch` inside test body — used `tmp_path` pytest fixture instead
- T8: `api.d.ts` regenerated from live backend on port 7843 (temp server)
- Ruff E501: line too long in `_detect_image_content_type` — extracted `sec_end` variable

### Completion Notes List

- ✅ T1: Created `src/lingosips/services/image.py` — `ImageService` with OpenAI-format b64_json image generation. 5 tests pass.
- ✅ T2: Updated `services/registry.py` — `ServiceStatusInfo.image_endpoint_configured` field + `get_image_service()` Depends helper. Covered by existing status tests.
- ✅ T3: Updated `api/services.py` — `ImageServiceStatus` model + `image` field in `ServiceStatusResponse`. 23 tests pass (+2 new image tests).
- ✅ T4: Updated `core/safety.py` — `_detect_image_content_type()` magic byte detection + `check_image()` validation. 17 tests pass (+10 new).
- ✅ T5: Updated `core/cards.py` — `IMAGE_DIR` constant, `generate_card_image()` async function, extended `update_card()` for `image_skipped`/`image_url`. 35 tests pass (+7 new).
- ✅ T6: Updated `api/cards.py` — `POST /{card_id}/generate-image`, `GET /{card_id}/image` endpoints; extended `CardUpdateRequest` + `patch_card()`. 43 tests pass (+10 new).
- ✅ T7: Updated `CardDetail.tsx` — `image-generating` state, service status query, `generateImage`/`skipImage` mutations, image section JSX. 22 tests pass (+9 new).
- ✅ T8: Added E2E tests to `card-management.spec.ts`; regenerated `api.d.ts` from live schema.
- **Total tests: 497 backend + 220 frontend = 717 passing, 0 failures, 0 regressions**
- Known limitation: image/audio files not cleaned up on card delete (acceptable MVP behavior per §ImageFileCleanup).

### File List

**Backend (new):**
- `src/lingosips/services/image.py`
- `tests/services/test_image_routing.py`

**Backend (modified):**
- `src/lingosips/services/registry.py`
- `src/lingosips/core/safety.py`
- `src/lingosips/core/cards.py`
- `src/lingosips/api/cards.py`
- `src/lingosips/api/services.py`
- `tests/api/test_services_api.py`
- `tests/api/test_cards.py`
- `tests/core/test_safety.py`
- `tests/core/test_cards.py`

**Frontend (modified):**
- `frontend/src/features/cards/CardDetail.tsx`
- `frontend/src/features/cards/CardDetail.test.tsx`
- `frontend/e2e/features/card-management.spec.ts`
- `frontend/src/lib/api.d.ts`

## Change Log

- 2026-05-01: Story 2.6 implemented — per-card image generation with OpenAI-format endpoint, magic byte safety validation, image storage at `~/.lingosips/images/`, skip/undo flow, and full CardDetail image section UI.
