"""Core deck management — no FastAPI, no SQLModel table-level imports except Card/Deck/Settings.

All business logic for deck CRUD lives here. The api/decks.py router only validates,
delegates to these functions, and converts ValueError to HTTP exceptions.
"""

import json
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from lingosips.db.models import Card, Deck, Settings


async def list_decks(session: AsyncSession, target_language: str) -> list[dict]:
    """Return all decks for target_language with precomputed card_count and due_card_count.

    Uses a single aggregated SQL query (outerjoin) — no N+1 queries.
    outerjoin ensures decks with 0 cards are still included.
    func.sum() returns None when no matching cards — always coerce with `int(x or 0)`.
    """
    now = datetime.now(UTC)
    stmt = (
        select(
            Deck,
            func.count(Card.id).label("card_count"),
            func.sum(case((Card.due <= now, 1), else_=0)).label("due_card_count"),
        )
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.target_language == target_language)
        .group_by(Deck.id)
        .order_by(Deck.name)
    )
    result = await session.execute(stmt)
    return [
        {"deck": row[0], "card_count": row[1], "due_card_count": int(row[2] or 0)}
        for row in result.all()
    ]


async def get_deck(deck_id: int, session: AsyncSession) -> Deck:
    """Fetch a single deck by ID.

    Raises ValueError if not found — router converts to 404.
    """
    result = await session.execute(select(Deck).where(Deck.id == deck_id))
    deck = result.scalar_one_or_none()
    if deck is None:
        raise ValueError(f"Deck {deck_id} does not exist")
    return deck


async def create_deck(
    name: str,
    target_language: str,
    session: AsyncSession,
) -> Deck:
    """Create a deck. Raises ValueError('conflict') if name+language already exists.

    Also adds target_language to Settings.target_languages if not already present.
    Name is expected to already be stripped by the caller (router strips whitespace).
    """
    # Duplicate check — same name + same language = conflict
    existing = await session.execute(
        select(Deck).where(Deck.name == name, Deck.target_language == target_language)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("conflict")

    deck = Deck(name=name, target_language=target_language)
    session.add(deck)

    # Reconcile target_languages in settings (deferred from Story 1.4)
    # Adds language to the known list if it isn't there yet.
    result = await session.execute(select(Settings).limit(1))
    settings = result.scalars().first()
    if settings is not None:
        langs: list[str] = json.loads(settings.target_languages)
        if target_language not in langs:
            langs.append(target_language)
            settings.target_languages = json.dumps(langs)
            settings.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(deck)
    return deck


async def update_deck(
    deck_id: int,
    update_data: dict,
    session: AsyncSession,
) -> Deck:
    """Partially update a deck. Only keys present in update_data are changed.

    Raises ValueError('not_found') if deck not found.
    Raises ValueError('conflict') on duplicate name within same language.
    Skips conflict check when the name is unchanged (renaming to own name is OK).
    """
    deck = await get_deck(deck_id, session)

    # settings_overrides: serialize dict → JSON string, None → None (clears overrides)
    if "settings_overrides" in update_data:
        value = update_data.pop("settings_overrides")
        deck.settings_overrides = json.dumps(value) if value is not None else None

    if "name" in update_data:
        new_name = update_data["name"]
        # Only check for conflict if the name actually changed
        if new_name != deck.name:
            existing = await session.execute(
                select(Deck).where(
                    Deck.name == new_name,
                    Deck.target_language == deck.target_language,
                    Deck.id != deck_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError("conflict")
        deck.name = new_name

    deck.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(deck)
    return deck


async def delete_deck(deck_id: int, session: AsyncSession) -> None:
    """Delete a deck. Cards that belonged to it have deck_id set to None (not deleted).

    Raises ValueError if deck not found.
    Cards are explicitly nulled out — do NOT rely on SQLite's implicit FK behaviour.
    """
    deck = await get_deck(deck_id, session)
    # Null out deck_id on all cards in this deck (cards remain in collection)
    await session.execute(
        sql_update(Card).where(Card.deck_id == deck_id).values(deck_id=None)
    )
    await session.delete(deck)
    await session.commit()
