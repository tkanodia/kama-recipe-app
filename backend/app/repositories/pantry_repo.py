"""Pantry repository — CRUD for user pantry items."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import PantryItem


async def add_items(
    session: AsyncSession,
    user_id: str,
    ingredient_ids: list[str],
) -> list[PantryItem]:
    existing = await get_ingredient_ids_for_user(session, user_id)
    added: list[PantryItem] = []
    for ingredient_id in ingredient_ids:
        if ingredient_id in existing:
            continue
        row = PantryItem(
            id=new_id("ptry"),
            user_id=user_id,
            ingredient_id=ingredient_id,
        )
        session.add(row)
        added.append(row)
        existing.add(ingredient_id)
    await session.flush()
    return added


async def remove_items(
    session: AsyncSession,
    pantry_item_ids: list[str],
    user_id: str,
) -> None:
    await session.execute(
        delete(PantryItem).where(
            PantryItem.id.in_(pantry_item_ids),
            PantryItem.user_id == user_id,
        )
    )


async def get_all_by_user(
    session: AsyncSession,
    user_id: str,
) -> list[PantryItem]:
    stmt = (
        select(PantryItem)
        .where(PantryItem.user_id == user_id)
        .order_by(PantryItem.added_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_ingredient_ids_for_user(
    session: AsyncSession,
    user_id: str,
) -> set[str]:
    stmt = select(PantryItem.ingredient_id).where(PantryItem.user_id == user_id)
    result = await session.execute(stmt)
    return set(result.scalars().all())
