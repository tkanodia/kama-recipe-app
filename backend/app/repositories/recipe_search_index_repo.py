"""Repository for RecipeSearchIndexStatus — tracks per-recipe embedding state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import RecipeSearchIndexStatus


async def create(
    session: AsyncSession,
    *,
    canonical_recipe_id: str,
    stale_reason: str = "new_recipe",
) -> RecipeSearchIndexStatus:
    now = datetime.now(tz=UTC)
    row = RecipeSearchIndexStatus(
        id=new_id("sidx"),
        canonical_recipe_id=canonical_recipe_id,
        stale=True,
        stale_reason=stale_reason,
        stale_since=now,
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_recipe_id(
    session: AsyncSession, canonical_recipe_id: str
) -> RecipeSearchIndexStatus | None:
    stmt = select(RecipeSearchIndexStatus).where(
        RecipeSearchIndexStatus.canonical_recipe_id == canonical_recipe_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_stale(
    session: AsyncSession,
    canonical_recipe_id: str,
    *,
    reason: str = "content_changed",
) -> None:
    now = datetime.now(tz=UTC)
    existing = await get_by_recipe_id(session, canonical_recipe_id)
    if existing is None:
        await create(session, canonical_recipe_id=canonical_recipe_id, stale_reason=reason)
    else:
        await session.execute(
            update(RecipeSearchIndexStatus)
            .where(RecipeSearchIndexStatus.canonical_recipe_id == canonical_recipe_id)
            .values(stale=True, stale_reason=reason, stale_since=now)
        )
    await session.flush()


async def mark_indexed(
    session: AsyncSession,
    canonical_recipe_id: str,
    *,
    source_text: str,
    embedding_model: str,
) -> None:
    now = datetime.now(tz=UTC)
    await session.execute(
        update(RecipeSearchIndexStatus)
        .where(RecipeSearchIndexStatus.canonical_recipe_id == canonical_recipe_id)
        .values(
            stale=False,
            stale_reason=None,
            stale_since=None,
            source_text=source_text,
            embedding_model=embedding_model,
            indexed_at=now,
        )
    )
    await session.flush()


async def find_all_stale(
    session: AsyncSession, *, limit: int = 100
) -> list[RecipeSearchIndexStatus]:
    stmt = (
        select(RecipeSearchIndexStatus)
        .where(RecipeSearchIndexStatus.stale.is_(True))
        .order_by(RecipeSearchIndexStatus.stale_since.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_by_recipe_id(
    session: AsyncSession, canonical_recipe_id: str
) -> None:
    await session.execute(
        delete(RecipeSearchIndexStatus).where(
            RecipeSearchIndexStatus.canonical_recipe_id == canonical_recipe_id
        )
    )
    await session.flush()
