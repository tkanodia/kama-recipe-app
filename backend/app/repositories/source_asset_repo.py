from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import SourceAsset


async def create_source_asset(
    session: AsyncSession,
    *,
    id: str,
    user_id: str,
    source_type: str,
    original_url: str | None,
    raw_text_input: str | None,
    file_asset_ref: str | None,
    context_note: str | None,
) -> SourceAsset:
    row = SourceAsset(
        id=id,
        user_id=user_id,
        source_type=source_type,
        original_url=original_url,
        raw_text_input=raw_text_input,
        file_asset_ref=file_asset_ref,
        context_note=context_note,
    )
    session.add(row)
    await session.flush()
    return row


async def get_source_asset_by_id(session: AsyncSession, asset_id: str) -> SourceAsset | None:
    return await session.get(SourceAsset, asset_id)
