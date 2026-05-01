"""Tests for FastAPI app configuration.

Verifies: RFC 7807 error responses, server binding, static file setup.
AC: 3, 5 — server configuration correct.
"""

import asyncio

from httpx import AsyncClient
from starlette.exceptions import HTTPException as StarletteHTTPException


class TestRFC7807ErrorResponses:
    async def test_404_returns_problem_json_content_type(self, client: AsyncClient) -> None:
        """404 errors return Content-Type: application/problem+json (not text/html)."""
        response = await client.get("/nonexistent-route-that-does-not-exist")
        assert response.status_code == 404
        content_type = response.headers.get("content-type", "")
        assert "application/problem+json" in content_type, (
            f"Expected application/problem+json, got: {content_type}"
        )

    async def test_404_returns_json_body_not_html(self, client: AsyncClient) -> None:
        """404 errors return a JSON body, not an HTML page."""
        response = await client.get("/nonexistent-route-xyz")
        assert response.status_code == 404
        # Must be parseable as JSON
        data = response.json()
        assert isinstance(data, dict), "404 body must be a JSON object"

    async def test_404_body_has_required_problem_fields(self, client: AsyncClient) -> None:
        """404 body contains type, title, status fields per RFC 7807."""
        response = await client.get("/route-that-does-not-exist")
        assert response.status_code == 404
        data = response.json()
        # RFC 7807 requires at minimum a 'type' or 'title' field
        assert "title" in data or "type" in data, f"RFC 7807 body missing type/title: {data}"


class TestRFC7807DictDetail:
    async def test_dict_detail_passed_through_unchanged(self) -> None:
        """When HTTPException.detail is a dict, it's passed through as-is (RFC 7807 custom body)."""
        from unittest.mock import MagicMock

        from lingosips.api.app import app

        # Simulate how the exception handler processes a dict detail
        mock_request = MagicMock()

        # Find the exception handler registered on the app
        exception_handlers = app.exception_handlers
        http_exc_handler = None
        for exc_type, handler in exception_handlers.items():
            if exc_type is StarletteHTTPException:
                http_exc_handler = handler
                break

        # Direct handler invocation — bypasses routing
        exc = StarletteHTTPException(
            status_code=422,
            detail={"type": "/errors/custom", "title": "Custom Error", "field": "name"},
        )
        response = await http_exc_handler(mock_request, exc)
        assert response.status_code == 422
        import json

        body = json.loads(response.body)
        assert body["type"] == "/errors/custom"
        assert body["title"] == "Custom Error"
        assert body["field"] == "name"


class TestBrowserOpen:
    async def test_schedule_browser_open_with_active_loop(self) -> None:
        """_schedule_browser_open runs without error inside an event loop."""
        import unittest.mock as mock

        from lingosips.api.app import _schedule_browser_open

        # Mock webbrowser.open to prevent actual browser launch
        with mock.patch("webbrowser.open"):
            # Should not raise — either creates a task or catches RuntimeError
            _schedule_browser_open()
            # Give the event loop a tick to process (or not — no assertion needed on actual open)
            await asyncio.sleep(0)

    def test_schedule_browser_open_no_event_loop(self) -> None:
        """_schedule_browser_open handles RuntimeError gracefully when no running loop exists.

        get_running_loop() raises RuntimeError when called outside an async context.
        The function must swallow this and not propagate it to the caller.
        """
        import unittest.mock as mock

        from lingosips.api.app import _schedule_browser_open

        # Patch get_running_loop (used since Python 3.10+ deprecation of get_event_loop)
        with mock.patch("asyncio.get_running_loop", side_effect=RuntimeError("no running loop")):
            with mock.patch("webbrowser.open"):
                # Should NOT raise — RuntimeError is caught by the except clause
                _schedule_browser_open()


class TestScrubDetail:
    """Unit tests for the _scrub_detail helper (edge cases patched in review)."""

    def test_none_detail_returns_empty_string(self) -> None:
        """_scrub_detail(None) returns '' so the handler builds the RFC 7807 envelope.

        Previously returned {} which would make the response body an empty dict
        with no 'type', 'title', or 'status' fields — an invalid RFC 7807 response.
        """
        from lingosips.api.app import _scrub_detail

        result = _scrub_detail(None)
        assert result == "", f"Expected empty string for None detail, got {result!r}"

    def test_nested_dict_values_are_scrubbed(self) -> None:
        """_scrub_detail recursively scrubs credentials inside nested dict values."""
        from lingosips.api.app import _scrub_detail

        detail = {
            "message": "api_key=sk-outerleak is invalid",
            "context": {"token": "sk-innerleak"},
        }
        result = _scrub_detail(detail)
        assert isinstance(result, dict)
        assert "sk-outerleak" not in str(result), "Outer credential must be scrubbed"
        assert "sk-innerleak" not in str(result), "Nested credential must be scrubbed"
        assert "[REDACTED]" in str(result)

    def test_non_string_dict_values_preserved(self) -> None:
        """_scrub_detail preserves non-string, non-dict values (int, bool, list) unchanged."""
        from lingosips.api.app import _scrub_detail

        detail = {"status": 422, "active": True, "items": [1, 2, 3]}
        result = _scrub_detail(detail)
        assert result["status"] == 422
        assert result["active"] is True
        assert result["items"] == [1, 2, 3]


class TestExceptionHandlerCredentialScrubbing:
    async def test_http_exception_with_credential_in_detail_is_scrubbed(self) -> None:
        """T5.1 / AC3: Credential in exc.detail must not appear in HTTP response.

        Tests the HTTP exception handler directly (same pattern as TestRFC7807DictDetail)
        to avoid dynamic route injection fragility.
        """
        import json
        from unittest.mock import MagicMock

        from starlette.exceptions import HTTPException as StarletteHTTPException

        from lingosips.api.app import app

        mock_request = MagicMock()

        # Find the StarletteHTTPException handler
        http_exc_handler = None
        for exc_type, handler in app.exception_handlers.items():
            if exc_type is StarletteHTTPException:
                http_exc_handler = handler
                break

        assert http_exc_handler is not None, "StarletteHTTPException handler not registered"

        exc = StarletteHTTPException(
            status_code=400,
            detail="Error: api_key=sk-leakedsecret123 is invalid",
        )
        response = await http_exc_handler(mock_request, exc)

        assert response.status_code == 400
        body_text = response.body.decode()
        assert "sk-leakedsecret123" not in body_text, (
            "Credential value must not appear in HTTP error response"
        )
        body = json.loads(body_text)
        assert "[REDACTED]" in body.get("title", "") or "Error" in body.get("title", "")

    async def test_unhandled_exception_returns_generic_500(self) -> None:
        """T5.2 / AC3: Unhandled exceptions never expose traceback or exception message.

        Tests the generic Exception handler directly to verify safe 500 responses.
        """
        import json
        from unittest.mock import MagicMock

        from lingosips.api.app import app

        mock_request = MagicMock()

        # Find the generic Exception handler
        generic_exc_handler = None
        for exc_type, handler in app.exception_handlers.items():
            if exc_type is Exception:
                generic_exc_handler = handler
                break

        assert generic_exc_handler is not None, "Generic Exception handler not registered"

        exc = RuntimeError("api_key=sk-verysecretvalue123 caused a crash")
        response = await generic_exc_handler(mock_request, exc)

        assert response.status_code == 500
        body_text = response.body.decode()
        assert "sk-verysecretvalue123" not in body_text, (
            "Credential value must not appear in 500 error response"
        )
        assert "RuntimeError" not in body_text, (
            "Exception class name must not appear in 500 error response"
        )
        body = json.loads(body_text)
        assert body["type"] == "/errors/internal"
        assert body["status"] == 500


class TestSPAFallback:
    """SPA routing: 404s for browser navigation return index.html; API 404s stay JSON."""

    async def test_browser_404_serves_index_html(self, client: AsyncClient) -> None:
        """GET /settings with Accept: text/html returns 200 index.html for React routing."""
        response = await client.get(
            "/settings", headers={"accept": "text/html,application/xhtml+xml,*/*"}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", ""), (
            f"Expected text/html content-type, got: {response.headers.get('content-type')}"
        )

    async def test_api_client_404_returns_problem_json(self, client: AsyncClient) -> None:
        """GET unknown route without Accept: text/html returns RFC 7807 JSON 404."""
        response = await client.get(
            "/nonexistent-api-route", headers={"accept": "application/json"}
        )
        assert response.status_code == 404
        assert "application/problem+json" in response.headers.get("content-type", "")
        body = response.json()
        assert "type" in body and "status" in body

    async def test_practice_route_serves_spa(self, client: AsyncClient) -> None:
        """GET /practice with browser Accept header returns SPA index.html."""
        response = await client.get(
            "/practice", headers={"accept": "text/html,application/xhtml+xml,*/*"}
        )
        assert response.status_code == 200

    async def test_progress_route_serves_spa(self, client: AsyncClient) -> None:
        """GET /progress with browser Accept header returns SPA index.html."""
        response = await client.get(
            "/progress", headers={"accept": "text/html,application/xhtml+xml,*/*"}
        )
        assert response.status_code == 200


class TestServerBinding:
    async def test_health_endpoint_accessible(self, client: AsyncClient) -> None:
        """Server is accessible (binding check via test client)."""
        # The test client tests the ASGI app directly;
        # the actual 127.0.0.1 binding is enforced in __main__.py and Makefile.
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_app_has_correct_title(self, client: AsyncClient) -> None:
        """FastAPI OpenAPI schema has the correct app title."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "lingosips"
