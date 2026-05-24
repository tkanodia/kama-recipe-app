"""Tag API — list by domain, create-or-reuse."""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.repositories import tag_repo

router = APIRouter(prefix="/tags", tags=["tags"])


class TagResponse(BaseModel):
    id: str
    name: str
    domain: str
    model_config = {"populate_by_name": True}


class TagListResponse(BaseModel):
    items: list[TagResponse]


class CreateTagBody(BaseModel):
    name: str
    domain: str


class CreateTagResponse(BaseModel):
    id: str
    name: str
    domain: str
    created: bool


@router.get("", response_model=TagListResponse)
async def list_tags(
    domain: str = Query(default="recipe"),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> TagListResponse:
    tags = await tag_repo.list_by_domain(db, domain, search=search)
    items = [TagResponse(id=t.id, name=t.name, domain=t.domain) for t in tags]
    return TagListResponse(items=items)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateTagResponse)
async def create_tag(
    body: CreateTagBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> CreateTagResponse:
    tag, created = await tag_repo.create_or_reuse(
        db, name=body.name, domain=body.domain, created_by_user_id=user_id,
    )
    await db.commit()
    return CreateTagResponse(id=tag.id, name=tag.name, domain=tag.domain, created=created)
