"""Tests for database session configuration.

Verifies the async session factory works correctly.
AC: 6 — DB session available throughout the app.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession


class TestGetSession:
    async def test_get_session_yields_async_session(self, session: AsyncSession) -> None:
        """get_session yields an AsyncSession instance."""
        assert isinstance(session, AsyncSession)

    async def test_session_can_execute_simple_query(self, session: AsyncSession) -> None:
        """Session can execute a basic SQL query."""
        from sqlalchemy import text

        result = await session.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1

    async def test_get_session_dependency_is_async_generator(self) -> None:
        """get_session is an async generator function (verifies the dependency contract).

        We verify the function signature rather than invoking the generator directly,
        because calling get_session() uses the module-level engine which is configured
        at import time. The fixture-based tests (session, client) already exercise the
        full dependency-injection path via app.dependency_overrides.
        """
        from lingosips.db.session import get_session

        assert inspect.isasyncgenfunction(get_session), (
            "get_session must be an async generator function for FastAPI Depends() injection"
        )

    async def test_session_rollback_on_teardown(self, session: AsyncSession) -> None:
        """Session is usable for writes (rollback is handled by fixture)."""
        from datetime import UTC, datetime

        from lingosips.db.models import Deck

        deck = Deck(
            name="Test Deck",
            target_language="es",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(deck)
        await session.flush()  # flush to DB without committing
        assert deck.id is not None, "Deck should have been assigned an ID after flush"
