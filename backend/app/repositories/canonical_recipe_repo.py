"""Canonical recipe repository — create, get, update, delete, list."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import cast, delete, func, select, update
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import (
    CanonicalRecipe, CookJournalEntry, JournalEntryMedia,
    RecipeMedia, RecipeRevision,
)


async def create(
    session: AsyncSession,
    *,
    user_id: str,
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
    field_provenance_map: dict | None = None,
    source_asset_id: str | None = None,
    origin_recipe_candidate_id: str | None = None,
    promoted_from_draft: bool = False,
    promoted_at: datetime | None = None,
) -> CanonicalRecipe:
    row = CanonicalRecipe(
        id=new_id("rec"),
        user_id=user_id,
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
        field_provenance_map=field_provenance_map or {},
        source_asset_id=source_asset_id,
        origin_recipe_candidate_id=origin_recipe_candidate_id,
        promoted_from_draft=promoted_from_draft,
        promoted_at=promoted_at,
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_id(session: AsyncSession, recipe_id: str) -> CanonicalRecipe | None:
    return await session.get(CanonicalRecipe, recipe_id)


async def list_by_user(
    session: AsyncSession,
    user_id: str,
    *,
    search: str | None = None,
    tag_ids: list[str] | None = None,
    sort: str = "updated_desc",
    cursor: str | None = None,
    limit: int = 20,
) -> list[CanonicalRecipe]:
    stmt = select(CanonicalRecipe).where(CanonicalRecipe.user_id == user_id)

    if search:
        stmt = stmt.where(
            CanonicalRecipe.title.ilike(f"%{search}%")
            | CanonicalRecipe.description.ilike(f"%{search}%")
        )

    if tag_ids:
        for tag_id in tag_ids:
            stmt = stmt.where(
                CanonicalRecipe.recipe_tags.cast(PG_JSONB).contains(
                    cast([{"id": tag_id}], PG_JSONB)
                )
            )

    cursor_dt: datetime | None = None
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError:
            pass

    if sort == "updated_desc":
        if cursor_dt:
            stmt = stmt.where(CanonicalRecipe.updated_at < cursor_dt)
        stmt = stmt.order_by(CanonicalRecipe.updated_at.desc())
    elif sort == "created_desc":
        if cursor_dt:
            stmt = stmt.where(CanonicalRecipe.created_at < cursor_dt)
        stmt = stmt.order_by(CanonicalRecipe.created_at.desc())
    elif sort == "title_asc":
        stmt = stmt.order_by(CanonicalRecipe.title.asc())
    else:
        if cursor_dt:
            stmt = stmt.where(CanonicalRecipe.updated_at < cursor_dt)
        stmt = stmt.order_by(CanonicalRecipe.updated_at.desc())

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_fields(
    session: AsyncSession,
    recipe_id: str,
    **fields: Any,
) -> None:
    values = {k: v for k, v in fields.items() if v is not None}
    values["updated_at"] = datetime.now(tz=UTC)
    await session.execute(
        update(CanonicalRecipe).where(CanonicalRecipe.id == recipe_id).values(**values)
    )


async def delete_cascade(session: AsyncSession, recipe_id: str) -> list[str]:
    """Delete recipe and all associated data. Returns asset_refs for S3 cleanup."""
    asset_refs: list[str] = []

    # Collect media asset refs (both main and thumbnails)
    media_stmt = select(RecipeMedia.asset_ref, RecipeMedia.thumbnail_ref).where(
        RecipeMedia.canonical_recipe_id == recipe_id
    )
    media_result = await session.execute(media_stmt)
    for row in media_result.all():
        if row[0]:
            asset_refs.append(row[0])
        if row[1]:
            asset_refs.append(row[1])

    journal_media_stmt = (
        select(JournalEntryMedia.asset_ref)
        .join(CookJournalEntry, CookJournalEntry.id == JournalEntryMedia.journal_entry_id)
        .where(CookJournalEntry.canonical_recipe_id == recipe_id)
    )
    jm_result = await session.execute(journal_media_stmt)
    asset_refs.extend(jm_result.scalars().all())

    # Delete in dependency order
    journal_ids_stmt = select(CookJournalEntry.id).where(CookJournalEntry.canonical_recipe_id == recipe_id)
    journal_ids = (await session.execute(journal_ids_stmt)).scalars().all()
    if journal_ids:
        await session.execute(
            delete(JournalEntryMedia).where(JournalEntryMedia.journal_entry_id.in_(journal_ids))
        )
    await session.execute(delete(CookJournalEntry).where(CookJournalEntry.canonical_recipe_id == recipe_id))
    await session.execute(delete(RecipeMedia).where(RecipeMedia.canonical_recipe_id == recipe_id))
    await session.execute(delete(RecipeRevision).where(RecipeRevision.canonical_recipe_id == recipe_id))
    await session.execute(delete(CanonicalRecipe).where(CanonicalRecipe.id == recipe_id))

    return asset_refs


async def count_journal_entries(session: AsyncSession, recipe_id: str) -> int:
    stmt = select(func.count()).where(CookJournalEntry.canonical_recipe_id == recipe_id)
    result = await session.execute(stmt)
    return result.scalar_one()


async def count_revisions(session: AsyncSession, recipe_id: str) -> int:
    stmt = select(func.count()).where(RecipeRevision.canonical_recipe_id == recipe_id)
    result = await session.execute(stmt)
    return result.scalar_one()
