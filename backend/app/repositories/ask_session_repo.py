"""Ask session repository — CRUD for ask sessions and messages."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import AskMessage, AskSession


async def create_session(
    session: AsyncSession,
    *,
    user_id: str,
    recipe_id: str | None = None,
) -> AskSession:
    row = AskSession(
        id=new_id("ask"),
        user_id=user_id,
        status="active",
        recipe_id=recipe_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get_session(session: AsyncSession, session_id: str) -> AskSession | None:
    return await session.get(AskSession, session_id)


async def list_sessions_by_user(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 30,
) -> list[AskSession]:
    stmt = (
        select(AskSession)
        .where(AskSession.user_id == user_id)
        .order_by(AskSession.last_active_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_message(
    session: AsyncSession,
    *,
    ask_session_id: str,
    role: str,
    content: str,
    retrieved_recipe_ids: list[str] | None = None,
    cited_recipe_ids: list[str] | None = None,
) -> AskMessage:
    row = AskMessage(
        id=new_id("amsg"),
        session_id=ask_session_id,
        role=role,
        content=content,
        retrieved_recipe_ids=retrieved_recipe_ids or [],
        cited_recipe_ids=cited_recipe_ids or [],
    )
    session.add(row)
    await session.flush()
    return row


async def list_messages(
    session: AsyncSession,
    ask_session_id: str,
) -> list[AskMessage]:
    stmt = (
        select(AskMessage)
        .where(AskMessage.session_id == ask_session_id)
        .order_by(AskMessage.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def close_session(session: AsyncSession, session_id: str) -> None:
    now = datetime.now(tz=UTC)
    await session.execute(
        update(AskSession)
        .where(AskSession.id == session_id)
        .values(status="closed", closed_at=now)
    )


async def update_last_active(session: AsyncSession, session_id: str) -> None:
    now = datetime.now(tz=UTC)
    await session.execute(
        update(AskSession)
        .where(AskSession.id == session_id)
        .values(last_active_at=now)
    )


async def find_expired_sessions(
    session: AsyncSession,
    inactive_threshold: timedelta = timedelta(minutes=15),
) -> list[AskSession]:
    cutoff = datetime.now(tz=UTC) - inactive_threshold
    stmt = (
        select(AskSession)
        .where(AskSession.status == "active", AskSession.last_active_at < cutoff)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_old_sessions(
    session: AsyncSession,
    older_than: timedelta = timedelta(days=7),
) -> int:
    cutoff = datetime.now(tz=UTC) - older_than
    stmt = select(AskSession.id).where(AskSession.created_at < cutoff)
    result = await session.execute(stmt)
    old_ids = list(result.scalars().all())
    if not old_ids:
        return 0

    await session.execute(
        delete(AskMessage).where(AskMessage.session_id.in_(old_ids))
    )
    await session.execute(
        delete(AskSession).where(AskSession.id.in_(old_ids))
    )
    return len(old_ids)
