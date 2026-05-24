"""Pantry API — manage user pantry items and check recipe feasibility."""

import structlog
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.tables import Ingredient, PantryItem
from app.services import pantry_service

log = structlog.get_logger()
router = APIRouter(prefix="/pantry", tags=["pantry"])


class AddPantryItemsBody(BaseModel):
    ingredientIds: list[str]


class AddFromTextBody(BaseModel):
    text: str


class RemovePantryItemsBody(BaseModel):
    pantryItemIds: list[str]


@router.get("")
@limiter.limit("60/minute")
async def list_pantry(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    stmt = (
        select(PantryItem, Ingredient)
        .join(Ingredient, PantryItem.ingredient_id == Ingredient.id)
        .where(PantryItem.user_id == user_id)
        .order_by(PantryItem.added_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        {
            "id": pantry_item.id,
            "ingredientId": pantry_item.ingredient_id,
            "ingredientName": ingredient.name,
            "ingredientCategory": ingredient.category,
            "addedAt": pantry_item.added_at.isoformat() if pantry_item.added_at else None,
        }
        for pantry_item, ingredient in rows
    ]
    return {"items": items, "totalCount": len(items)}


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def add_pantry_items(
    request: Request,
    body: AddPantryItemsBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    result = await pantry_service.add_pantry_items(db, body.ingredientIds, user_id)
    await db.commit()
    return result


@router.post("/from-text", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def add_from_text(
    request: Request,
    body: AddFromTextBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    result = await pantry_service.add_from_text(db, body.text, user_id)
    await db.commit()
    return result


@router.delete("")
@limiter.limit("60/minute")
async def remove_pantry_items(
    request: Request,
    body: RemovePantryItemsBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    await pantry_service.remove_pantry_items(db, body.pantryItemIds, user_id)
    await db.commit()
    return {"removed": body.pantryItemIds}


@router.post("/feasibility")
@limiter.limit("60/minute")
async def check_feasibility(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    log.info("pantry_feasibility_request", user_id=user_id)
    return await pantry_service.check_feasibility(db, user_id)
