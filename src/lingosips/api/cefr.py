"""FastAPI router for CEFR profile — GET /cefr/profile.

Router only — no aggregation logic. All computation delegated to core/cefr.py.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.core import cefr as core_cefr
from lingosips.db.session import get_session

router = APIRouter()


class CefrProfileResponse(BaseModel):
    """Response shape for GET /cefr/profile."""

    level: str | None  # null when < 10 reviews
    vocabulary_breadth: int
    grammar_coverage: int
    recall_rate_by_card_type: dict[str, float]  # empty dict when no reviews
    active_passive_ratio: float | None  # null when no session mode data
    explanation: str  # always present


@router.get("/profile", response_model=CefrProfileResponse)
async def get_cefr_profile(
    target_language: str = Query(...),  # required — missing → 422 auto from FastAPI
    session: AsyncSession = Depends(get_session),
) -> CefrProfileResponse:
    """Return the CEFR knowledge profile for the specified target language.

    Aggregates vocabulary breadth, grammar forms coverage, recall rate by card
    type, and active/passive session ratio. Result is cached per language;
    cache is invalidated automatically after card ratings (AC4).

    Raises:
        422: Missing target_language query param (RFC 7807 via validation_exception_handler)
    """
    profile = await core_cefr.get_profile(target_language, session)
    return CefrProfileResponse(
        level=profile.level,
        vocabulary_breadth=profile.vocabulary_breadth,
        grammar_coverage=profile.grammar_coverage,
        recall_rate_by_card_type=profile.recall_rate_by_card_type,
        active_passive_ratio=profile.active_passive_ratio,
        explanation=profile.explanation,
    )
