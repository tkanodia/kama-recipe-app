"""Ingredient API — search, create, update aliases."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.repositories import ingredient_repo

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

VALID_CATEGORIES = {
    "produce",           # fruits, vegetables, fresh herbs
    "meat_seafood",      # chicken, beef, shrimp, etc.
    "dairy",             # milk, cheese, yogurt, butter, cream
    "grains_bread",      # rice, pasta, flour, bread, oats
    "spices_seasoning",  # cumin, salt, pepper, paprika, dried herbs
    "oils_vinegars",     # olive oil, sesame oil, balsamic, soy sauce
    "canned_jarred",     # canned tomatoes, beans, coconut milk, broth
    "frozen",            # frozen peas, frozen berries
    "baking",            # sugar, baking powder, vanilla extract, chocolate
    "nuts_seeds",        # almonds, sesame seeds, peanut butter
    "beverages",         # wine (cooking), stock, juice
    "other",             # anything that doesn't fit
}


class IngredientResponse(BaseModel):
    id: str
    name: str
    category: str
    aliases: list[str]
    match_confidence: str | None = Field(default=None, alias="matchConfidence")
    model_config = {"populate_by_name": True}


class CreateIngredientBody(BaseModel):
    name: str
    category: str


class UpdateAliasesBody(BaseModel):
    aliases: list[str]


@router.get("")
async def search_ingredients(
    search: str = Query(default="", min_length=0),
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    if not search.strip():
        return {"items": []}
    results = await ingredient_repo.search(db, search, limit=limit)
    return {"items": [IngredientResponse(**r).model_dump(by_alias=True) for r in results]}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IngredientResponse)
async def create_ingredient(
    body: CreateIngredientBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> IngredientResponse:
    cat = body.category.strip().lower()
    if cat not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid category '{body.category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
        )
    existing = await ingredient_repo.find_by_name(db, body.name)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ingredient already exists")
    ing = await ingredient_repo.create(
        db, name=body.name, category=cat,
        created_by_system=False, created_by_user_id=user_id,
    )
    await db.commit()
    return IngredientResponse(id=ing.id, name=ing.name, category=ing.category, aliases=ing.aliases)


@router.patch("/{ingredient_id}", response_model=IngredientResponse)
async def update_aliases(
    ingredient_id: str,
    body: UpdateAliasesBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> IngredientResponse:
    ing = await ingredient_repo.update_aliases(db, ingredient_id, body.aliases)
    if ing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    await db.commit()
    return IngredientResponse(id=ing.id, name=ing.name, category=ing.category, aliases=ing.aliases)
