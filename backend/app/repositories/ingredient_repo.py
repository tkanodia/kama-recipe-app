"""Ingredient repository — CRUD, three-tier search (exact, alias, fuzzy trigram)."""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import Ingredient


async def create(
    session: AsyncSession,
    *,
    name: str,
    category: str = "other",
    aliases: list[str] | None = None,
    notes: str | None = None,
    created_by_system: bool = True,
    created_by_user_id: str | None = None,
) -> Ingredient:
    row = Ingredient(
        id=new_id("ing"),
        name=name.strip(),
        category=category.strip().lower(),
        aliases=aliases or [],
        notes=notes,
        created_by_system=created_by_system,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_id(session: AsyncSession, ingredient_id: str) -> Ingredient | None:
    return await session.get(Ingredient, ingredient_id)


async def find_by_name(session: AsyncSession, name: str) -> Ingredient | None:
    stmt = select(Ingredient).where(func.lower(Ingredient.name) == name.strip().lower())
    result = await session.execute(stmt)
    return result.scalars().first()


async def search(
    session: AsyncSession,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Three-tier search: exact name, alias ILIKE, trigram similarity."""
    q = query.strip().lower()
    if not q:
        return []

    results: list[dict] = []
    seen_ids: set[str] = set()

    def _row_to_dict(row: Ingredient, confidence: str) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "aliases": row.aliases,
            "matchConfidence": confidence,
        }

    # Tier 1: Exact name match
    exact_stmt = select(Ingredient).where(func.lower(Ingredient.name) == q)
    exact = await session.execute(exact_stmt)
    for row in exact.scalars().all():
        results.append(_row_to_dict(row, "exact"))
        seen_ids.add(row.id)

    if len(results) >= limit:
        return results[:limit]

    # Tier 2a: Exact alias match (any element in the JSON array matches exactly)
    exact_alias_stmt = (
        select(Ingredient)
        .where(
            text(
                "EXISTS (SELECT 1 FROM jsonb_array_elements_text(aliases) AS a "
                "WHERE lower(a) = :q)"
            ).bindparams(q=q)
        )
        .limit(limit)
    )
    try:
        exact_alias_result = await session.execute(exact_alias_stmt)
        for row in exact_alias_result.scalars().all():
            if row.id not in seen_ids:
                results.append(_row_to_dict(row, "alias"))
                seen_ids.add(row.id)
    except Exception:
        pass

    if len(results) >= limit:
        return results[:limit]

    # Tier 2b: Alias substring match (fallback for partial alias matches)
    alias_stmt = (
        select(Ingredient)
        .where(Ingredient.aliases.op("::text")(text("")).ilike(f"%{q}%"))
        .limit(limit)
    )
    try:
        alias_result = await session.execute(alias_stmt)
        for row in alias_result.scalars().all():
            if row.id not in seen_ids:
                results.append(_row_to_dict(row, "alias"))
                seen_ids.add(row.id)
    except Exception:
        pass

    if len(results) >= limit:
        return results[:limit]

    # Tier 3: Name ILIKE prefix/contains fallback
    like_stmt = (
        select(Ingredient)
        .where(Ingredient.name.ilike(f"%{q}%"))
        .limit(limit)
    )
    like_result = await session.execute(like_stmt)
    for row in like_result.scalars().all():
        if row.id not in seen_ids:
            results.append(_row_to_dict(row, "fuzzy"))
            seen_ids.add(row.id)

    return results[:limit]


async def update_aliases(
    session: AsyncSession,
    ingredient_id: str,
    new_aliases: list[str],
) -> Ingredient | None:
    ing = await session.get(Ingredient, ingredient_id)
    if ing is None:
        return None

    existing = {a.strip().lower() for a in ing.aliases}
    updated = list(ing.aliases)
    for alias in new_aliases:
        cleaned = alias.strip()
        if cleaned.lower() not in existing and cleaned.lower() != ing.name.lower():
            updated.append(cleaned)
            existing.add(cleaned.lower())

    ing.aliases = updated
    await session.flush()
    return ing
