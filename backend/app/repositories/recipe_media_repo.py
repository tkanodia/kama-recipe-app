from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import RecipeMedia


async def create(
    session: AsyncSession,
    *,
    canonical_recipe_id: str,
    role: str,
    source: str,
    asset_ref: str,
    thumbnail_ref: str | None = None,
    display_order: int | None = None,
) -> RecipeMedia:
    row = RecipeMedia(
        id=new_id("media"),
        canonical_recipe_id=canonical_recipe_id,
        role=role,
        source=source,
        asset_ref=asset_ref,
        thumbnail_ref=thumbnail_ref,
        display_order=display_order,
    )
    session.add(row)
    await session.flush()
    return row


async def find_by_recipe(session: AsyncSession, recipe_id: str) -> list[RecipeMedia]:
    stmt = (
        select(RecipeMedia)
        .where(RecipeMedia.canonical_recipe_id == recipe_id)
        .order_by(RecipeMedia.display_order.asc().nulls_last())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, media_id: str) -> RecipeMedia | None:
    return await session.get(RecipeMedia, media_id)


async def update_role(session: AsyncSession, media_id: str, role: str) -> None:
    await session.execute(update(RecipeMedia).where(RecipeMedia.id == media_id).values(role=role))


async def demote_hero(session: AsyncSession, recipe_id: str) -> None:
    await session.execute(
        update(RecipeMedia)
        .where(RecipeMedia.canonical_recipe_id == recipe_id, RecipeMedia.role == "hero")
        .values(role="source_gallery")
    )


async def delete_media(session: AsyncSession, media_id: str) -> None:
    await session.execute(delete(RecipeMedia).where(RecipeMedia.id == media_id))
