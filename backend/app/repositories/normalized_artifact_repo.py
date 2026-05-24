from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import NormalizedSourceArtifact


async def create_artifact(
    session: AsyncSession,
    *,
    ingestion_job_id: str,
    artifact_type: str,
    payload: dict[str, Any],
) -> NormalizedSourceArtifact:
    row = NormalizedSourceArtifact(
        id=new_id("art"),
        ingestion_job_id=ingestion_job_id,
        artifact_type=artifact_type,
        payload=payload,
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_id(session: AsyncSession, artifact_id: str) -> NormalizedSourceArtifact | None:
    return await session.get(NormalizedSourceArtifact, artifact_id)


async def find_by_job_id(
    session: AsyncSession,
    job_id: str,
) -> list[NormalizedSourceArtifact]:
    stmt = (
        select(NormalizedSourceArtifact)
        .where(NormalizedSourceArtifact.ingestion_job_id == job_id)
        .order_by(NormalizedSourceArtifact.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
