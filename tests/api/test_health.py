"""Tests for the GET /health endpoint.

AC: 1, 5 — server starts and health check passes.
"""

from httpx import AsyncClient


class TestHealth:
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """GET /health returns HTTP 200."""
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_returns_ok_status(self, client: AsyncClient) -> None:
        """GET /health returns {"status": "ok"}."""
        response = await client.get("/health")
        data = response.json()
        assert data == {"status": "ok"}

    async def test_health_content_type_is_json(self, client: AsyncClient) -> None:
        """GET /health returns JSON content type."""
        response = await client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")
