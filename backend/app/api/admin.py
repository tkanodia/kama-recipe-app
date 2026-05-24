"""Admin endpoints — embedding backfill and recipe re-indexing."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.config import get_settings
from app.core.database import get_db
from app.models.tables import CanonicalRecipe, RecipeSearchIndexStatus

log = structlog.get_logger()
router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(user_id: str = Depends(get_current_user_id)) -> str:
    settings = get_settings()
    if user_id not in settings.admin_user_id_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user_id


class BackfillResponse(BaseModel):
    enqueued: int
    message: str


class RegenerateResponse(BaseModel):
    recipe_id: str = Field(alias="recipeId")
    message: str
    model_config = {"populate_by_name": True}


@router.post("/embeddings/backfill", response_model=BackfillResponse)
async def backfill_embeddings(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_admin),
) -> BackfillResponse:
    """Find all canonical recipes without a non-stale index status and enqueue them."""
    from app.repositories import recipe_search_index_repo
    from app.workers.search_index_worker import index_recipe_send

    indexed_recipe_ids_stmt = select(RecipeSearchIndexStatus.canonical_recipe_id).where(
        RecipeSearchIndexStatus.stale.is_(False)
    )
    indexed_result = await db.execute(indexed_recipe_ids_stmt)
    indexed_ids = set(indexed_result.scalars().all())

    all_recipes_stmt = select(CanonicalRecipe.id)
    all_result = await db.execute(all_recipes_stmt)
    all_ids = list(all_result.scalars().all())

    enqueued = 0
    for recipe_id in all_ids:
        if recipe_id in indexed_ids:
            continue
        await recipe_search_index_repo.mark_stale(db, recipe_id, reason="backfill")
        index_recipe_send(recipe_id)
        enqueued += 1

    await db.commit()

    log.info("backfill_enqueued", count=enqueued, total_recipes=len(all_ids))
    return BackfillResponse(enqueued=enqueued, message=f"Enqueued {enqueued} recipes for indexing")


@router.post("/recipes/{recipe_id}/regenerate-embedding", response_model=RegenerateResponse)
async def regenerate_embedding(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_admin),
) -> RegenerateResponse:
    """Force re-index a single recipe."""
    from app.repositories import canonical_recipe_repo, recipe_search_index_repo
    from app.workers.search_index_worker import index_recipe_send

    recipe = await canonical_recipe_repo.get_by_id(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    await recipe_search_index_repo.mark_stale(db, recipe_id, reason="admin_regenerate")
    await db.commit()
    index_recipe_send(recipe_id)

    return RegenerateResponse(recipeId=recipe_id, message="Re-indexing enqueued")
