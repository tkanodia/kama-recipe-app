from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import CookJournalEntry, JournalEntryMedia


async def create_entry(
    session: AsyncSession,
    *,
    canonical_recipe_id: str,
    user_id: str,
    body: str,
    cooked_on: str | None = None,
    tags: list[dict] | None = None,
    media_refs: list[str] | None = None,
) -> CookJournalEntry:
    entry = CookJournalEntry(
        id=new_id("jrnl"),
        canonical_recipe_id=canonical_recipe_id,
        user_id=user_id,
        body=body,
        cooked_on=cooked_on,
        tags=tags or [],
    )
    session.add(entry)
    await session.flush()

    if media_refs:
        for i, ref in enumerate(media_refs[:2]):
            media = JournalEntryMedia(
                id=new_id("jmedia"),
                journal_entry_id=entry.id,
                asset_ref=ref,
                display_order=i,
            )
            session.add(media)
        await session.flush()

    return entry


async def list_by_recipe(
    session: AsyncSession,
    recipe_id: str,
    limit: int = 20,
    cursor: str | None = None,
) -> list[CookJournalEntry]:
    stmt = (
        select(CookJournalEntry)
        .where(CookJournalEntry.canonical_recipe_id == recipe_id)
        .order_by(CookJournalEntry.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, entry_id: str) -> CookJournalEntry | None:
    return await session.get(CookJournalEntry, entry_id)


async def delete_entry(session: AsyncSession, entry_id: str) -> None:
    await session.execute(delete(JournalEntryMedia).where(JournalEntryMedia.journal_entry_id == entry_id))
    await session.execute(delete(CookJournalEntry).where(CookJournalEntry.id == entry_id))


async def get_media_for_entry(session: AsyncSession, entry_id: str) -> list[JournalEntryMedia]:
    stmt = (
        select(JournalEntryMedia)
        .where(JournalEntryMedia.journal_entry_id == entry_id)
        .order_by(JournalEntryMedia.display_order)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
