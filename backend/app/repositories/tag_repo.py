"""Tag repository — list by domain, find by name+domain, create-or-reuse."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.models.tables import Tag


async def list_by_domain(
    session: AsyncSession,
    domain: str,
    search: str | None = None,
) -> list[Tag]:
    stmt = select(Tag).where(Tag.domain == domain)
    if search:
        stmt = stmt.where(Tag.name.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Tag.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_by_name_and_domain(
    session: AsyncSession,
    name: str,
    domain: str,
) -> Tag | None:
    stmt = select(Tag).where(
        func.lower(Tag.name) == name.strip().lower(),
        Tag.domain == domain,
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def create(
    session: AsyncSession,
    *,
    name: str,
    domain: str,
    created_by_system: bool = False,
    created_by_user_id: str | None = None,
) -> Tag:
    row = Tag(
        id=new_id("tag"),
        name=name.strip(),
        domain=domain,
        created_by_system=created_by_system,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    await session.flush()
    return row


async def create_or_reuse(
    session: AsyncSession,
    *,
    name: str,
    domain: str,
    created_by_user_id: str | None = None,
) -> tuple[Tag, bool]:
    """Returns (tag, created). If name+domain already exists, returns existing."""
    existing = await find_by_name_and_domain(session, name, domain)
    if existing:
        return existing, False
    new_tag = await create(
        session,
        name=name,
        domain=domain,
        created_by_user_id=created_by_user_id,
    )
    return new_tag, True
