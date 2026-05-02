"""Tests for services/image.py — ImageService unit tests.

TDD: these tests are written BEFORE implementation (Story 2.6 T1.1).
AC: 1, 2
"""

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Minimal valid 1×1 PNG bytes (smallest possible valid PNG)
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x11\x00\x01n\xfe\xc5S\x00\x00\x00\x00IEND\xaeB`\x82"
)

_B64_PNG = base64.b64encode(_PNG_1X1).decode()

_ENDPOINT = "https://image-api.example.com"


def _make_mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    """Create a mock httpx Response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json = MagicMock(return_value=json_data)
    return mock_resp


def _make_mock_client(response: MagicMock) -> MagicMock:
    """Create a mock httpx.AsyncClient context manager."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx, mock_client


@pytest.mark.anyio
class TestImageServiceGenerate:
    """Tests for ImageService.generate() — AC: 1, 2."""

    async def test_happy_path_returns_png_bytes(self) -> None:
        """generate() returns decoded PNG bytes on 200 with b64_json data."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"data": [{"b64_json": _B64_PNG}]},
        )
        mock_ctx, mock_client = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            result = await service.generate(prompt="melancólico")

        assert result == _PNG_1X1

    async def test_timeout_raises_timeout_error(self) -> None:
        """generate() propagates TimeoutError/httpx.TimeoutException on network timeout."""
        from lingosips.services.image import ImageService

        mock_ctx = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            with pytest.raises((asyncio.TimeoutError, httpx.TimeoutException)):
                await service.generate(prompt="melancólico")

    async def test_non_200_raises_runtime_error_with_status(self) -> None:
        """generate() raises RuntimeError containing the status code on non-200."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(status_code=429)
        mock_ctx, _ = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            with pytest.raises(RuntimeError, match="429"):
                await service.generate(prompt="melancólico")

    async def test_bearer_token_sent_when_api_key_provided(self) -> None:
        """generate() includes Authorization: Bearer {api_key} header when api_key given."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"data": [{"b64_json": _B64_PNG}]},
        )
        mock_ctx, mock_client = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key="test-secret-key")
            await service.generate(prompt="melancólico")

        call_kwargs = mock_client.post.call_args
        # Headers are always passed as a keyword argument in generate()
        sent_headers = call_kwargs.kwargs.get("headers", {})
        assert sent_headers.get("Authorization") == "Bearer test-secret-key"

    async def test_no_auth_header_when_api_key_is_none(self) -> None:
        """generate() omits Authorization header when api_key is None."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"data": [{"b64_json": _B64_PNG}]},
        )
        mock_ctx, mock_client = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            await service.generate(prompt="melancólico")

        call_kwargs = mock_client.post.call_args
        sent_headers = call_kwargs.kwargs.get("headers", {})
        assert "Authorization" not in sent_headers

    async def test_network_error_raises_runtime_error(self) -> None:
        """generate() wraps httpx.NetworkError in RuntimeError."""
        from lingosips.services.image import ImageService

        mock_ctx = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.NetworkError("connection refused"))
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            with pytest.raises(RuntimeError, match="unreachable"):
                await service.generate(prompt="melancólico")

    async def test_malformed_response_missing_data_key_raises_runtime_error(self) -> None:
        """generate() raises RuntimeError when response JSON lacks 'data' key."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(status_code=200, json_data={"error": "quota exceeded"})
        mock_ctx, _ = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            with pytest.raises(RuntimeError, match="malformed response"):
                await service.generate(prompt="melancólico")

    async def test_malformed_response_empty_data_list_raises_runtime_error(self) -> None:
        """generate() raises RuntimeError when 'data' list is empty."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(status_code=200, json_data={"data": []})
        mock_ctx, _ = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            with pytest.raises(RuntimeError, match="malformed response"):
                await service.generate(prompt="melancólico")

    async def test_invalid_base64_raises_runtime_error(self) -> None:
        """generate() raises RuntimeError when b64_json contains invalid base64."""
        from lingosips.services.image import ImageService

        mock_resp = _make_mock_response(
            status_code=200,
            json_data={"data": [{"b64_json": "!!!not-valid-base64!!!"}]},
        )
        mock_ctx, _ = _make_mock_client(mock_resp)

        with patch("lingosips.services.image.httpx.AsyncClient", return_value=mock_ctx):
            service = ImageService(endpoint_url=_ENDPOINT, api_key=None)
            with pytest.raises(RuntimeError, match="invalid base64"):
                await service.generate(prompt="melancólico")
