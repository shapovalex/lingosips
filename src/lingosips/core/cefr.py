"""CEFR profile computation engine.

Aggregates vocabulary breadth, grammar coverage, recall rate by card type,
and active/passive session ratio to produce a CEFR level estimate (A1–C2).

No FastAPI imports. Takes AsyncSession, returns dataclasses.
Cache is a module-level dict — safe in single-threaded asyncio context.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import case, func, select
from sqlalchemy import distinct as sa_distinct
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.db.models import Card, PracticeSession, Review

logger = structlog.get_logger(__name__)

# ── CEFR level thresholds ─────────────────────────────────────────────────────
# (upper_exclusive_threshold, level_name)
THRESHOLDS: list[tuple[int, str]] = [
    (50, "A1"),
    (150, "A2"),
    (500, "B1"),
    (1200, "B2"),
    (2500, "C1"),
]
LEVELS: list[str] = ["A1", "A2", "B1", "B2", "C1", "C2"]

# ── Module-level profile cache ────────────────────────────────────────────────
# Key: target_language string. Value: CefrProfile.
# Dict ops are safe without locks in Python asyncio (single-threaded event loop).
_profile_cache: dict[str, "CefrProfile"] = {}


@dataclass
class CefrProfile:
    """Aggregated CEFR knowledge profile for a target language."""

    level: str | None  # None when review_count < 10
    vocabulary_breadth: int  # count of cards in Review/Mature state
    grammar_coverage: int  # count of distinct form-type keys
    recall_rate_by_card_type: dict[str, float]  # {card_type: recall_rate}
    active_passive_ratio: float | None  # None when no session mode data
    explanation: str  # human-readable description


# ── Cache management ──────────────────────────────────────────────────────────


def invalidate_profile_cache(target_language: str) -> None:
    """Remove cached profile for the given language.

    Safe to call synchronously from any async context — pure dict.pop().
    Called from api/practice.py after a card is rated (AC4).
    """
    _profile_cache.pop(target_language, None)


# ── Public API ────────────────────────────────────────────────────────────────


async def get_profile(target_language: str, db: AsyncSession) -> CefrProfile:
    """Return CEFR profile for target_language, using cache when available.

    Cache hit: returns cached CefrProfile without touching DB.
    Cache miss: computes all dimensions, stores result in cache, returns it.
    """
    if target_language in _profile_cache:
        return _profile_cache[target_language]

    profile = await _compute_profile(target_language, db)
    _profile_cache[target_language] = profile
    return profile


# ── Dimension computations ────────────────────────────────────────────────────


async def compute_vocabulary_breadth(db: AsyncSession, target_language: str) -> int:
    """Count cards in Review or Mature FSRS state for the target language (AC1)."""
    result = await db.execute(
        select(func.count(Card.id)).where(
            Card.target_language == target_language,
            Card.fsrs_state.in_(["Review", "Mature"]),
        )
    )
    return result.scalar_one() or 0


async def compute_grammar_coverage(db: AsyncSession, target_language: str) -> int:
    """Count distinct top-level form-type keys across all cards' forms JSON (AC1).

    Skips cards with null forms or invalid JSON — never crashes.
    """
    result = await db.execute(
        select(Card.forms).where(
            Card.target_language == target_language,
            Card.forms.isnot(None),
        )
    )
    rows = result.scalars().all()

    form_types: set[str] = set()
    for forms_json in rows:
        try:
            forms_dict = json.loads(forms_json)
            if isinstance(forms_dict, dict):
                form_types.update(forms_dict.keys())
        except (json.JSONDecodeError, TypeError):
            continue  # skip malformed JSON — do not crash

    return len(form_types)


async def compute_recall_rate_by_card_type(
    db: AsyncSession, target_language: str
) -> dict[str, float]:
    """Compute recall rate per card_type for reviews in the last 30 days (AC1).

    Uses SQLAlchemy JOIN for efficiency — no Python-side filtering.
    Rating >= 3 (Good or Easy) counts as correct.
    """
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    result = await db.execute(
        select(
            Card.card_type,
            func.count(Review.id).label("total"),
            func.sum(case((Review.rating >= 3, 1), else_=0)).label("correct"),
        )
        .join(Card, Card.id == Review.card_id)
        .where(Card.target_language == target_language)
        .where(Review.reviewed_at >= thirty_days_ago)
        .group_by(Card.card_type)
    )
    rows = result.all()
    return {
        row.card_type: (row.correct or 0) / row.total
        for row in rows
        if row.total > 0 and row.card_type is not None
    }


async def compute_active_passive_ratio(db: AsyncSession, target_language: str) -> float | None:
    """Compute ratio of active (write/speak) sessions to all sessions (AC1).

    Returns None when no sessions have mode data for this language.
    Null mode is treated as self_assess (passive).
    """
    result = await db.execute(
        select(
            PracticeSession.mode,
            func.count(sa_distinct(Review.session_id)).label("session_count"),
        )
        .join(Review, Review.session_id == PracticeSession.id)
        .join(Card, Card.id == Review.card_id)
        .where(Card.target_language == target_language)
        .where(Review.session_id.isnot(None))
        .group_by(PracticeSession.mode)
    )
    rows = result.all()

    if not rows:
        return None

    total = sum(r.session_count for r in rows)
    active = sum(r.session_count for r in rows if r.mode in ("write", "speak"))
    return active / total if total > 0 else None


# ── Level mapping ─────────────────────────────────────────────────────────────


def map_to_cefr_level(
    vocab_breadth: int,
    grammar_coverage: int,
    review_count: int,
) -> str | None:
    """Map vocabulary breadth + grammar coverage to a CEFR level (AC2, AC3).

    Returns None when review_count < 10 (insufficient data).
    Grammar boost: if grammar_coverage >= 5 and vocab >= 80% of next threshold,
    advance one step. Capped at C2.
    """
    if review_count < 10:
        return None

    base_level = "C2"
    upper: int | None = None
    for threshold, level in THRESHOLDS:
        if vocab_breadth < threshold:
            base_level = level
            upper = threshold
            break

    # Grammar boost: advance one step if coverage >= 5 and vocab >= 80% of upper
    if grammar_coverage >= 5 and upper is not None:
        if vocab_breadth >= 0.8 * upper:
            idx = LEVELS.index(base_level)
            if idx + 1 < len(LEVELS):
                base_level = LEVELS[idx + 1]

    return base_level


# ── Private helpers ───────────────────────────────────────────────────────────


async def _count_reviews_for_language(db: AsyncSession, target_language: str) -> int:
    """Count total reviews for cards of the specified language (for null-check)."""
    result = await db.execute(
        select(func.count(Review.id))
        .join(Card, Card.id == Review.card_id)
        .where(Card.target_language == target_language)
    )
    return result.scalar_one() or 0


async def _compute_profile(target_language: str, db: AsyncSession) -> CefrProfile:
    """Compute all CEFR dimensions from DB and build CefrProfile.

    Checks review count FIRST — returns sparse-data profile without running
    expensive aggregation queries when count < 10.
    """
    review_count = await _count_reviews_for_language(db, target_language)

    if review_count < 10:
        return CefrProfile(
            level=None,
            vocabulary_breadth=0,
            grammar_coverage=0,
            recall_rate_by_card_type={},
            active_passive_ratio=None,
            explanation="Practice more cards to generate your profile",
        )

    vocab_breadth = await compute_vocabulary_breadth(db, target_language)
    grammar_cov = await compute_grammar_coverage(db, target_language)
    recall_rate = await compute_recall_rate_by_card_type(db, target_language)
    active_passive = await compute_active_passive_ratio(db, target_language)
    level = map_to_cefr_level(vocab_breadth, grammar_cov, review_count)

    explanation = (
        f"You have demonstrated {level} vocabulary and grammar coverage."
        if level is not None
        else "Practice more cards to generate your profile"
    )

    return CefrProfile(
        level=level,
        vocabulary_breadth=vocab_breadth,
        grammar_coverage=grammar_cov,
        recall_rate_by_card_type=recall_rate,
        active_passive_ratio=active_passive,
        explanation=explanation,
    )
