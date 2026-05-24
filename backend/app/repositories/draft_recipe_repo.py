"""Draft recipe repository — create, get, update, delete, list."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import DraftRecipe


async def create(
    session: AsyncSession,
    *,
    user_id: str,
    origin_source_asset_id: str,
    origin_recipe_candidate_id: str,
    title: str,
    ingredients: list[dict],
    steps: list[dict],
    description: str | None = None,
    prep_time_minutes: int | None = None,
    cook_time_minutes: int | None = None,
    servings: int | None = None,
    recipe_tags: list[dict] | None = None,
    nutrition: dict | None = None,
    notes: list[dict] | None = None,
    how_to_serve: str | None = None,
) -> DraftRecipe:
    promotion_eligible = bool(title and ingredients and steps)
    row = DraftRecipe(
        id=new_id("draft"),
        user_id=user_id,
        origin_source_asset_id=origin_source_asset_id,
        origin_recipe_candidate_id=origin_recipe_candidate_id,
        title=title,
        ingredients=ingredients,
        steps=steps,
        description=description,
        prep_time_minutes=prep_time_minutes,
        cook_time_minutes=cook_time_minutes,
        servings=servings,
        recipe_tags=recipe_tags or [],
        nutrition=nutrition,
        notes=notes or [],
        how_to_serve=how_to_serve,
        promotion_eligible=promotion_eligible,
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_id(session: AsyncSession, draft_id: str) -> DraftRecipe | None:
    return await session.get(DraftRecipe, draft_id)


async def list_by_user(
    session: AsyncSession,
    user_id: str,
    limit: int = 20,
) -> list[DraftRecipe]:
    stmt = (
        select(DraftRecipe)
        .where(DraftRecipe.user_id == user_id)
        .order_by(DraftRecipe.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_fields(
    session: AsyncSession,
    draft_id: str,
    **fields: Any,
) -> None:
    values = {k: v for k, v in fields.items() if v is not None}
    values["updated_at"] = datetime.now(tz=UTC)

    # If promotion_eligible was explicitly passed (e.g. from review), honour it.
    # Otherwise, recompute when content fields change (edits reset review status).
    if "promotion_eligible" not in fields:
        title = values.get("title")
        ingredients = values.get("ingredients")
        steps = values.get("steps")
        if title is not None or ingredients is not None or steps is not None:
            draft = await session.get(DraftRecipe, draft_id)
            if draft:
                t = title or draft.title
                i = ingredients or draft.ingredients
                s = steps or draft.steps
                values["promotion_eligible"] = bool(t and i and s)

    await session.execute(update(DraftRecipe).where(DraftRecipe.id == draft_id).values(**values))


async def delete_draft(session: AsyncSession, draft_id: str) -> None:
    await session.execute(delete(DraftRecipe).where(DraftRecipe.id == draft_id))
