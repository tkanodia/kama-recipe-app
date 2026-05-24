from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import IngestionJob


async def create_ingestion_job(
    session: AsyncSession,
    *,
    id: str,
    user_id: str,
    source_asset_id: str,
    status: str,
    internal_state: str,
    processor_family: str,
    extra_metadata: dict | None = None,
) -> IngestionJob:
    row = IngestionJob(
        id=id,
        user_id=user_id,
        source_asset_id=source_asset_id,
        status=status,
        internal_state=internal_state,
        processor_family=processor_family,
        normalized_artifact_ids=[],
        extraction_plan=[],
        state_history=[],
        rerun_allowed=False,
        user_recoverable=True,
        extra_metadata=extra_metadata,
    )
    session.add(row)
    await session.flush()
    return row


async def get_job_by_id(session: AsyncSession, job_id: str) -> IngestionJob | None:
    return await session.get(IngestionJob, job_id)


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    *,
    status: str | None = None,
    internal_state: str | None = None,
    internal_error_state: str | None = None,
    candidate_id: str | None = None,
    extraction_plan: list | None = None,
    state_history: list | None = None,
    normalized_artifact_ids: list | None = None,
    review_mode: str | None = None,
    error_type: str | None = None,
    error_code: str | None = None,
    rerun_allowed: bool | None = None,
    last_heartbeat_at: datetime | None = None,
    completed_at: datetime | None = None,
    started_at: datetime | None = None,
) -> None:
    values: dict = {"updated_at": datetime.now(tz=UTC)}
    if status is not None:
        values["status"] = status
    if internal_state is not None:
        values["internal_state"] = internal_state
    if internal_error_state is not None:
        values["internal_error_state"] = internal_error_state
    if candidate_id is not None:
        values["candidate_id"] = candidate_id
    if extraction_plan is not None:
        values["extraction_plan"] = extraction_plan
    if state_history is not None:
        values["state_history"] = state_history
    if normalized_artifact_ids is not None:
        values["normalized_artifact_ids"] = normalized_artifact_ids
    if review_mode is not None:
        values["review_mode"] = review_mode
    if error_type is not None:
        values["error_type"] = error_type
    if error_code is not None:
        values["error_code"] = error_code
    if rerun_allowed is not None:
        values["rerun_allowed"] = rerun_allowed
    if last_heartbeat_at is not None:
        values["last_heartbeat_at"] = last_heartbeat_at
    if completed_at is not None:
        values["completed_at"] = completed_at
    if started_at is not None:
        values["started_at"] = started_at
    await session.execute(update(IngestionJob).where(IngestionJob.id == job_id).values(**values))


async def find_stuck_jobs(session: AsyncSession, *, older_than: timedelta) -> list[IngestionJob]:
    cutoff = datetime.now(tz=UTC) - older_than
    q = select(IngestionJob).where(
        IngestionJob.status == "processing",
        IngestionJob.last_heartbeat_at.is_not(None),
        IngestionJob.last_heartbeat_at < cutoff,
    )
    res = await session.execute(q)
    return list(res.scalars().all())
