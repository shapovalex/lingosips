"""Async SQLite database engine and session factory.

DB file location: ~/.lingosips/lingosips.db — never configurable, never relative path.
WAL mode is enabled on every new connection for better concurrent read performance.
All DB access goes through get_session() — never create raw SQLite connections.
"""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Test override: use in-memory DB when running under pytest
_TEST_DB_URL = os.environ.get("LINGOSIPS_TEST_DB_URL")

DB_DIR = Path.home() / ".lingosips"
DB_PATH = DB_DIR / "lingosips.db"

_DATABASE_URL = _TEST_DB_URL or f"sqlite+aiosqlite:///{DB_PATH}"

# In-memory SQLite (used in tests) requires StaticPool for shared state across connections
if ":memory:" in _DATABASE_URL:
    engine = create_async_engine(
        _DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
else:
    engine = create_async_engine(
        _DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )


@listens_for(engine.sync_engine, "connect")
def _set_wal_mode(dbapi_conn, connection_record):  # noqa: ARG001
    """Enable WAL journal mode on every new connection for better concurrency."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
