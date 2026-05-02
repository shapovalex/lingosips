"""Test-only utility endpoints — only mounted when LINGOSIPS_ENV=test.

These endpoints are never available in production. They exist solely to
support E2E test isolation (resetting DB state between Playwright tests).
"""

import structlog
from fastapi import APIRouter
from sqlmodel import delete

from lingosips.db.models import Card, Deck, Job, Review
from lingosips.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.delete("/reset", status_code=204)
async def reset_test_db() -> None:
    """Delete all cards, decks, reviews, jobs, and settings.

    Only available when LINGOSIPS_ENV=test. Resets the DB to a clean state
    for E2E test isolation. Never call in production.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Review))
        await session.execute(delete(Job))
        await session.execute(delete(Card))
        await session.execute(delete(Deck))
        # Settings are NOT deleted — each test suite manages its own settings
        # state via completeOnboarding() / direct API calls.
        await session.commit()
    logger.info("test_db_reset_complete")
