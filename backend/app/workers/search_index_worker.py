"""Search index worker — generate embeddings and upsert recipe points to Qdrant.

Runs as an in-process background task (same pattern as journal_summary_worker).
"""

from __future__ import annotations

import structlog

from app.core.database import SessionLocal
from app.services.background_runner import enqueue

log = structlog.get_logger()


def index_recipe_send(recipe_id: str) -> None:
    """Enqueue a recipe for (re-)indexing in Qdrant."""
    enqueue(_index_recipe, recipe_id, task_name=f"search-index-{recipe_id}")


async def _index_recipe(recipe_id: str) -> None:
    from app.repositories import canonical_recipe_repo, recipe_search_index_repo
    from app.services.embedding_service import (
        EMBEDDING_MODEL,
        compose_source_text,
        generate_dense_embedding,
        generate_sparse_vector,
    )
    from app.services.qdrant_client_service import upsert_recipe_point

    async with SessionLocal() as session:
        recipe = await canonical_recipe_repo.get_by_id(session, recipe_id)
        if recipe is None:
            log.warning("search_index_recipe_missing", recipe_id=recipe_id)
            return

        try:
            source_text = compose_source_text(recipe)
            dense_vector = await generate_dense_embedding(source_text)
            sparse_vector = generate_sparse_vector(source_text)

            tag_ids = [
                t.get("id", "") for t in (recipe.recipe_tags or []) if isinstance(t, dict)
            ]
            ingredient_ids = [
                i.get("ingredientId", "") or i.get("id", "")
                for i in (recipe.ingredients or [])
                if isinstance(i, dict)
            ]

            payload = {
                "userId": recipe.user_id,
                "title": recipe.title,
                "tagIds": [tid for tid in tag_ids if tid],
                "ingredientIds": [iid for iid in ingredient_ids if iid],
                "cookTimeMinutes": recipe.cook_time_minutes,
                "prepTimeMinutes": recipe.prep_time_minutes,
                "servings": recipe.servings,
            }

            await upsert_recipe_point(recipe_id, dense_vector, sparse_vector, payload)

            await recipe_search_index_repo.mark_indexed(
                session,
                recipe_id,
                source_text=source_text,
                embedding_model=EMBEDDING_MODEL,
            )
            await session.commit()

            log.info(
                "search_index_updated",
                recipe_id=recipe_id,
                source_text_len=len(source_text),
            )
        except Exception:
            log.error("search_index_failed", recipe_id=recipe_id, exc_info=True)
