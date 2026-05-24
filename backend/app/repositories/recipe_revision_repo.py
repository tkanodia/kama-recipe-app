from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import RecipeRevision


async def create_snapshot(
    session: AsyncSession,
    *,
    canonical_recipe_id: str,
    snapshot_payload: dict,
    change_summary: str | None = None,
) -> RecipeRevision:
    row = RecipeRevision(
        id=new_id("rev"),
        canonical_recipe_id=canonical_recipe_id,
        snapshot_payload=snapshot_payload,
        change_summary=change_summary,
    )
    session.add(row)
    await session.flush()
    return row


async def list_by_recipe(session: AsyncSession, recipe_id: str) -> list[RecipeRevision]:
    stmt = (
        select(RecipeRevision)
        .where(RecipeRevision.canonical_recipe_id == recipe_id)
        .order_by(RecipeRevision.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, revision_id: str) -> RecipeRevision | None:
    return await session.get(RecipeRevision, revision_id)
