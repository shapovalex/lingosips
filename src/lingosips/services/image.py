"""HTTP client for OpenAI-format image generation REST endpoints.

Follows the architecture rule: services/ contains external provider abstractions only.
No FastAPI imports, no business logic — pure HTTP client.
"""

import base64

import httpx
import structlog

logger = structlog.get_logger(__name__)

IMAGE_GENERATION_TIMEOUT = 30.0  # seconds


class ImageService:
    """HTTP client for OpenAI-format image generation REST endpoints."""

    def __init__(self, endpoint_url: str, api_key: str | None):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.api_key = api_key

    async def generate(self, prompt: str, size: str = "512x512") -> bytes:
        """Generate image. Returns raw image bytes.

        Raises:
            RuntimeError: on non-200 response, malformed response, or network error
            httpx.TimeoutException: on network timeout (propagated as-is so callers
                can distinguish timeouts from other failures)
        """
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=IMAGE_GENERATION_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.endpoint_url}/v1/images/generations",
                    headers=headers,
                    json={"prompt": prompt, "n": 1, "size": size, "response_format": "b64_json"},
                )
                if resp.status_code != 200:
                    logger.warning("image.generation_failed", status=resp.status_code)
                    raise RuntimeError(f"Image endpoint returned {resp.status_code}")
                try:
                    data = resp.json()
                    b64_data = data["data"][0]["b64_json"]
                except (KeyError, IndexError, ValueError) as exc:
                    logger.warning("image.malformed_response", error=str(exc))
                    raise RuntimeError("Image endpoint returned malformed response") from exc
                try:
                    return base64.b64decode(b64_data)
                except Exception as exc:
                    logger.warning("image.invalid_base64", error=str(exc))
                    raise RuntimeError("Image endpoint returned invalid base64 data") from exc
        except httpx.TimeoutException:
            raise  # propagate as-is — generate_card_image renders a user-friendly message
        except httpx.NetworkError as exc:
            logger.warning("image.network_error", error=str(exc))
            raise RuntimeError(f"Image endpoint unreachable: {exc}") from exc
