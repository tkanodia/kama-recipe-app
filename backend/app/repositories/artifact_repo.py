"""Artifact repository — CRUD for artifacts and artifact revisions."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import Artifact, ArtifactRevision


async def create(
    session: AsyncSession,
    *,
    user_id: str,
    artifact_type: str,
    title: str,
    content: dict,
    source_recipe_ids: list[str] | None = None,
) -> Artifact:
    row = Artifact(
        id=new_id("art"),
        user_id=user_id,
        artifact_type=artifact_type,
        title=title,
        content=content,
        source_recipe_ids=source_recipe_ids or [],
        status="active",
    )
    session.add(row)
    await session.flush()
    return row


async def get_by_id(session: AsyncSession, artifact_id: str) -> Artifact | None:
    return await session.get(Artifact, artifact_id)


async def list_by_user(
    session: AsyncSession,
    user_id: str,
    *,
    artifact_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Artifact]:
    stmt = select(Artifact).where(Artifact.user_id == user_id)
    if artifact_type is not None:
        stmt = stmt.where(Artifact.artifact_type == artifact_type)
    if status is not None:
        stmt = stmt.where(Artifact.status == status)
    stmt = stmt.order_by(Artifact.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_artifact(
    session: AsyncSession,
    artifact_id: str,
    **kwargs: object,
) -> Artifact | None:
    row = await session.get(Artifact, artifact_id)
    if row is None:
        return None
    for key, value in kwargs.items():
        if hasattr(row, key):
            setattr(row, key, value)
    await session.flush()
    return row


async def archive(session: AsyncSession, artifact_id: str) -> None:
    await session.execute(
        update(Artifact)
        .where(Artifact.id == artifact_id)
        .values(status="archived")
    )


async def create_revision(
    session: AsyncSession,
    *,
    artifact_id: str,
    snapshot_payload: dict,
    change_summary: str | None = None,
) -> ArtifactRevision:
    row = ArtifactRevision(
        id=new_id("arev"),
        artifact_id=artifact_id,
        snapshot_payload=snapshot_payload,
        change_summary=change_summary,
    )
    session.add(row)
    await session.flush()
    return row


async def list_revisions(
    session: AsyncSession,
    artifact_id: str,
) -> list[ArtifactRevision]:
    stmt = (
        select(ArtifactRevision)
        .where(ArtifactRevision.artifact_id == artifact_id)
        .order_by(ArtifactRevision.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_revision(
    session: AsyncSession,
    revision_id: str,
) -> ArtifactRevision | None:
    return await session.get(ArtifactRevision, revision_id)
