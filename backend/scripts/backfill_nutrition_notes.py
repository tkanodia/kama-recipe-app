"""Backfill nutrition + notes on existing canonical recipes by re-extracting from source URLs.

Usage:
    cd backend && uv run python -m scripts.backfill_nutrition_notes
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.tables import CanonicalRecipe, SourceAsset
from app.tools.extraction_tools import check_schema_markup, schema_recipe_extract
from app.tools.fetch_tools import httpx_fetch
from app.tools.notes_extractor import extract_chef_notes_from_html, extract_chef_notes_llm

log = structlog.get_logger()


async def backfill() -> None:
    async with SessionLocal() as session:
        stmt = (
            select(CanonicalRecipe)
            .where(CanonicalRecipe.nutrition.is_(None))
            .where(CanonicalRecipe.source_asset_id.isnot(None))
        )
        result = await session.execute(stmt)
        recipes = result.scalars().all()

        log.info("backfill_start", recipe_count=len(recipes))

        for recipe in recipes:
            try:
                sa = await session.get(SourceAsset, recipe.source_asset_id)
                if not sa or not sa.original_url:
                    log.info("skip_no_url", recipe_id=recipe.id)
                    continue

                url = sa.original_url
                log.info("backfill_recipe", recipe_id=recipe.id, url=url)

                fetch_result = await httpx_fetch(url)
                if not fetch_result.success:
                    log.warning("fetch_failed", recipe_id=recipe.id, url=url)
                    continue

                html = fetch_result.signals.get("html", "")
                has_schema = fetch_result.signals.get("has_recipe_schema", False)

                nutrition = None
                notes: list[dict] = []

                if has_schema:
                    schema_result = check_schema_markup(html)
                    if schema_result.success and schema_result.signals.get("recipeSchema"):
                        extract_result = schema_recipe_extract(schema_result.signals["recipeSchema"])
                        if extract_result.success and extract_result.candidate_update:
                            nutrition = extract_result.candidate_update.get("nutrition")

                html_notes = extract_chef_notes_from_html(html)
                if html_notes:
                    notes = html_notes
                else:
                    from app.tools.fetch_tools import extract_page_text
                    text_result = extract_page_text(html, url)
                    if text_result.success:
                        cleaned = text_result.signals.get("cleanedText", "")
                        if cleaned and len(cleaned) >= 100:
                            notes = await extract_chef_notes_llm(cleaned)

                updates: dict = {}
                if nutrition:
                    updates["nutrition"] = nutrition
                if notes:
                    updates["notes"] = notes

                if updates:
                    await session.execute(
                        update(CanonicalRecipe)
                        .where(CanonicalRecipe.id == recipe.id)
                        .values(**updates)
                    )
                    await session.commit()
                    log.info(
                        "backfill_done",
                        recipe_id=recipe.id,
                        has_nutrition=bool(nutrition),
                        notes_count=len(notes),
                    )
                else:
                    log.info("backfill_no_data", recipe_id=recipe.id)

            except Exception:
                log.error("backfill_error", recipe_id=recipe.id, exc_info=True)
                continue

    log.info("backfill_complete")


if __name__ == "__main__":
    asyncio.run(backfill())
