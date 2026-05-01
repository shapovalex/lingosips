"""Alembic environment configuration.

Uses SQLModel metadata. Migrations run with a synchronous SQLite connection
(aiosqlite is only needed by the app at runtime, not for schema DDL).
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine
from sqlmodel import SQLModel

# Import all models so SQLModel metadata is populated before autogenerate
import lingosips.db.models  # noqa: F401

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Interpret the config file for Python logging (if present and not overridden)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel metadata — all tables must be imported above for autogenerate to work
target_metadata = SQLModel.metadata


def _get_database_url() -> str:
    """Resolve the synchronous SQLite URL for migrations.

    Strips the +aiosqlite driver since Alembic DDL runs synchronously.
    Uses LINGOSIPS_TEST_DB_URL env var when running under tests (also strips async driver).
    """
    test_url = os.environ.get("LINGOSIPS_TEST_DB_URL")
    if test_url:
        # Strip async driver if present: sqlite+aiosqlite:///path → sqlite:///path
        return test_url.replace("sqlite+aiosqlite://", "sqlite://")

    db_path = Path.home() / ".lingosips" / "lingosips.db"
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a synchronous engine.

    Alembic DDL (CREATE TABLE, CREATE INDEX) does not require an async engine.
    The app uses aiosqlite at runtime for query performance; migrations use the
    standard synchronous SQLite driver.

    The engine is explicitly disposed after migrations to release the underlying
    SQLite connection immediately, preventing ResourceWarning from the GC.
    """
    url = _get_database_url()
    connectable = create_engine(url, echo=False)
    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
