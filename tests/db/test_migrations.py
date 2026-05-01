"""Tests for the database schema and Alembic migrations.

Verifies all 5 tables exist with correct columns after migration.
AC: 6 — all tables defined correctly, migration runs cleanly.

NOTE: Alembic runs synchronously against a file-based SQLite DB.
      Async engine (aiosqlite) is only needed at runtime, not for DDL.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

# Resolve alembic.ini relative to this file so tests work regardless of CWD.
# Layout: tests/db/test_migrations.py → project root is ../../
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ALEMBIC_INI = str(_PROJECT_ROOT / "alembic.ini")


@pytest.fixture(scope="module")
def migration_db_url():
    """Create a temp SQLite file for Alembic migration tests."""
    db_path = "/tmp/lingosips_migration_test.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    yield f"sqlite:///{db_path}"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="module")
def migrated_engine(migration_db_url):
    """Engine with Alembic migrations applied."""
    # Set the test URL so Alembic env.py picks it up
    # env.py strips +aiosqlite if present, so setting async URL works too
    os.environ["LINGOSIPS_TEST_DB_URL"] = migration_db_url

    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(_ALEMBIC_INI)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(migration_db_url)
    yield engine
    engine.dispose()
    os.environ.pop("LINGOSIPS_TEST_DB_URL", None)


class TestTablesExist:
    def test_cards_table_exists(self, migrated_engine) -> None:
        """cards table exists after migration."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
            )
            assert result.fetchone() is not None, "cards table not found"

    def test_decks_table_exists(self, migrated_engine) -> None:
        """decks table exists after migration."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='decks'")
            )
            assert result.fetchone() is not None, "decks table not found"

    def test_settings_table_exists(self, migrated_engine) -> None:
        """settings table exists after migration."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
            )
            assert result.fetchone() is not None, "settings table not found"

    def test_reviews_table_exists(self, migrated_engine) -> None:
        """reviews table exists after migration."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'")
            )
            assert result.fetchone() is not None, "reviews table not found"

    def test_jobs_table_exists(self, migrated_engine) -> None:
        """jobs table exists after migration."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
            )
            assert result.fetchone() is not None, "jobs table not found"


class TestFSRSColumnsOnCards:
    def test_cards_has_fsrs_columns(self, migrated_engine) -> None:
        """cards table has all required FSRS scheduling columns."""
        with migrated_engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(cards)"))
            columns = {row[1] for row in result.fetchall()}

        required_fsrs_columns = {
            "stability",
            "difficulty",
            "due",
            "last_review",
            "reps",
            "lapses",
            "fsrs_state",
        }
        missing = required_fsrs_columns - columns
        assert not missing, f"Missing FSRS columns on cards: {missing}"

    def test_cards_has_required_columns(self, migrated_engine) -> None:
        """cards table has all required non-FSRS columns."""
        with migrated_engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(cards)"))
            columns = {row[1] for row in result.fetchall()}

        required_columns = {
            "id",
            "target_word",
            "translation",
            "deck_id",
            "target_language",
            "card_type",
            "created_at",
            "updated_at",
        }
        missing = required_columns - columns
        assert not missing, f"Missing columns on cards: {missing}"


class TestForeignKeys:
    def test_reviews_has_card_id_fk_column(self, migrated_engine) -> None:
        """reviews table has card_id column (FK to cards)."""
        with migrated_engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(reviews)"))
            columns = {row[1] for row in result.fetchall()}
        assert "card_id" in columns, "reviews.card_id column missing"


class TestIndexes:
    def test_ix_cards_due_exists(self, migrated_engine) -> None:
        """ix_cards_due index exists on cards.due for FSRS queue queries."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_cards_due'")
            )
            assert result.fetchone() is not None, "ix_cards_due index not found"

    def test_ix_cards_deck_id_exists(self, migrated_engine) -> None:
        """ix_cards_deck_id index exists."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_cards_deck_id'"
                )
            )
            assert result.fetchone() is not None, "ix_cards_deck_id index not found"

    def test_ix_reviews_card_id_exists(self, migrated_engine) -> None:
        """ix_reviews_card_id index exists."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='ix_reviews_card_id'"
                )
            )
            assert result.fetchone() is not None, "ix_reviews_card_id index not found"

    def test_ix_reviews_reviewed_at_exists(self, migrated_engine) -> None:
        """ix_reviews_reviewed_at index exists for CEFR profile aggregation."""
        with migrated_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name='ix_reviews_reviewed_at'"
                )
            )
            assert result.fetchone() is not None, "ix_reviews_reviewed_at index not found"


class TestMigrationIdempotency:
    def test_running_upgrade_head_twice_does_not_fail(self) -> None:
        """Running alembic upgrade head twice is idempotent."""
        db_path = "/tmp/lingosips_idempotent_test.db"
        if os.path.exists(db_path):
            os.remove(db_path)

        db_url = f"sqlite:///{db_path}"
        os.environ["LINGOSIPS_TEST_DB_URL"] = db_url

        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(_ALEMBIC_INI)

        # Run twice — must not raise
        command.upgrade(alembic_cfg, "head")
        command.upgrade(alembic_cfg, "head")  # second run should be a no-op

        os.environ.pop("LINGOSIPS_TEST_DB_URL", None)
        if os.path.exists(db_path):
            os.remove(db_path)
