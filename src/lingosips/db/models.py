"""All SQLModel table definitions for lingosips.

All 5 tables MUST live in this single file — never split across multiple files.
Alembic owns schema evolution — never use SQLModel.metadata.create_all() in production.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    """Return current UTC datetime (timezone-aware). Used as default_factory."""
    return datetime.now(UTC)


class Card(SQLModel, table=True):
    __tablename__ = "cards"

    id: int | None = Field(default=None, primary_key=True)
    target_word: str
    translation: str | None = None
    forms: str | None = None  # JSON string: {"gender": ..., "plural": ..., "conjugations": ...}
    example_sentences: str | None = None  # JSON string: list of sentences
    audio_url: str | None = None
    personal_note: str | None = None
    image_url: str | None = None
    image_skipped: bool = Field(default=False)
    card_type: str = Field(default="word")  # "word" | "sentence" | "collocation"
    deck_id: int | None = Field(default=None, foreign_key="decks.id", index=True)
    target_language: str
    # FSRS scheduling columns — ALL required from day 1
    stability: float = Field(default=0.0)
    difficulty: float = Field(default=0.0)
    due: datetime = Field(default_factory=_now, index=True)  # ix_cards_due — FSRS queue query
    last_review: datetime | None = None
    reps: int = Field(default=0)
    lapses: int = Field(default=0)
    # "New" | "Learning" | "Review" | "Relearning" | "Mature"
    fsrs_state: str = Field(default="New")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Deck(SQLModel, table=True):
    __tablename__ = "decks"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    target_language: str
    settings_overrides: str | None = None  # JSON string for deck-level defaults
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Settings(SQLModel, table=True):
    __tablename__ = "settings"

    id: int | None = Field(default=None, primary_key=True)
    native_language: str = Field(default="en")
    target_languages: str = Field(default='["es"]')  # JSON string: list of language codes
    active_target_language: str = Field(default="es")
    auto_generate_audio: bool = Field(default=True)
    auto_generate_images: bool = Field(default=False)
    default_practice_mode: str = Field(default="self_assess")  # "self_assess" | "write" | "speak"
    cards_per_session: int = Field(default=20)
    onboarding_completed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: int | None = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="cards.id", index=True)
    rating: int  # 1=Again, 2=Hard, 3=Good, 4=Easy
    reviewed_at: datetime = Field(
        default_factory=_now, index=True
    )  # ix_reviews_reviewed_at — CEFR profile aggregation
    # Post-review FSRS state snapshot (for CEFR profile aggregation)
    stability_after: float
    difficulty_after: float
    fsrs_state_after: str
    reps_after: int
    lapses_after: int


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    job_type: str  # "import_enrichment" | "audio_batch" | "model_download"
    status: str = Field(default="pending")  # "pending" | "running" | "complete" | "failed"
    progress_done: int = Field(default=0)
    progress_total: int = Field(default=0)
    current_item: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
