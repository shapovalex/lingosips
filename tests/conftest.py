"""Pytest configuration and shared fixtures for lingosips tests.

Uses in-memory SQLite for fast, isolated test runs.
The app's get_session dependency is overridden for every test.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Mark tests as running in test mode (suppresses browser open, etc.)
os.environ.setdefault("LINGOSIPS_ENV", "test")

from lingosips.api.app import app
from lingosips.db.session import get_session

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    """Create an in-memory SQLite engine shared across the test session."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create all tables directly (tests don't run Alembic — migration tested separately)
    from sqlmodel import SQLModel

    import lingosips.db.models  # noqa: F401 — registers all models with SQLModel metadata

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def session(test_engine) -> AsyncSession:
    """Yield a database session that rolls back after each test."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as s:
        yield s
        await s.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncClient:
    """Yield an async HTTP client with the test DB session injected."""

    async def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
