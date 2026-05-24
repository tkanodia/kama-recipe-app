"""Artifacts API — generate, view, update, and version artifacts."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.repositories import artifact_repo
from app.services import meal_plan_service, shopping_list_service

log = structlog.get_logger()
router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class GenerateArtifactBody(BaseModel):
    artifactType: str
    recipeIds: list[str] | None = None
    instructions: str | None = None
    title: str | None = None
    days: int | None = 7
    mealsPerDay: int | None = 3


class UpdateArtifactBody(BaseModel):
    title: str | None = None
    content: dict | None = None


def _artifact_to_dict(artifact) -> dict:
    return {
        "id": artifact.id,
        "userId": artifact.user_id,
        "artifactType": artifact.artifact_type,
        "title": artifact.title,
        "content": artifact.content,
        "sourceRecipeIds": artifact.source_recipe_ids,
        "status": artifact.status,
        "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
        "updatedAt": artifact.updated_at.isoformat() if artifact.updated_at else None,
    }


def _revision_to_dict(rev) -> dict:
    return {
        "id": rev.id,
        "artifactId": rev.artifact_id,
        "snapshotPayload": rev.snapshot_payload,
        "changeSummary": rev.change_summary,
        "createdAt": rev.created_at.isoformat() if rev.created_at else None,
    }


def _validate_meal_plan_content(content: dict) -> None:
    days = content.get("days")
    if days is not None and not isinstance(days, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="meal_plan content.days must be an array",
        )
    if isinstance(days, list):
        for day in days:
            slots = day.get("slots")
            if slots is not None and not isinstance(slots, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Day {day.get('day')} slots must be an array",
                )
            if isinstance(slots, list):
                for slot in slots:
                    rid = slot.get("recipeId")
                    if rid is not None and not isinstance(rid, str):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="slot recipeId must be a string or null",
                        )


@router.post("/generate", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def generate_artifact(
    request: Request,
    body: GenerateArtifactBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    log.info("artifact_generate_start", artifact_type=body.artifactType, user_id=user_id)

    if body.artifactType == "shopping_list":
        if not body.recipeIds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipeIds required for shopping_list artifact",
            )
        try:
            artifact = await shopping_list_service.generate_and_persist_shopping_list(
                db,
                recipe_ids=body.recipeIds,
                user_id=user_id,
                title=body.title,
            )
        except Exception:
            log.error("artifact_generate_failed", artifact_type="shopping_list", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate artifact. Please try again.",
            )
        await db.commit()
        return _artifact_to_dict(artifact)

    if body.artifactType == "meal_plan":
        try:
            artifact = await meal_plan_service.generate_meal_plan(
                db,
                instructions=body.instructions,
                recipe_ids=body.recipeIds,
                days=body.days or 7,
                meals_per_day=body.mealsPerDay or 3,
                title=body.title,
                user_id=user_id,
            )
        except Exception:
            log.error("artifact_generate_failed", artifact_type="meal_plan", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate artifact. Please try again.",
            )
        await db.commit()
        return _artifact_to_dict(artifact)

    if body.artifactType == "pantry_feasibility":
        from app.services import pantry_service

        try:
            feasibility_data = await pantry_service.check_feasibility(db, user_id)
            title = body.title or f"Pantry Check – {__import__('datetime').date.today().isoformat()}"
            artifact = await artifact_repo.create(
                db,
                user_id=user_id,
                artifact_type="pantry_feasibility",
                title=title,
                content=feasibility_data,
                source_recipe_ids=[],
            )
        except Exception:
            log.error("artifact_generate_failed", artifact_type="pantry_feasibility", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate artifact. Please try again.",
            )
        await db.commit()
        return _artifact_to_dict(artifact)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported artifact type: {body.artifactType}",
    )


@router.get("/{artifact_id}")
@limiter.limit("60/minute")
async def get_artifact(
    request: Request,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    artifact = await artifact_repo.get_by_id(db, artifact_id)
    if artifact is None or artifact.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return _artifact_to_dict(artifact)


@router.get("")
@limiter.limit("60/minute")
async def list_artifacts(
    request: Request,
    type: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    artifacts = await artifact_repo.list_by_user(
        db, user_id, artifact_type=type, status=status_filter, limit=limit, offset=offset,
    )
    return {
        "items": [_artifact_to_dict(a) for a in artifacts],
        "total": len(artifacts),
    }


@router.patch("/{artifact_id}")
@limiter.limit("60/minute")
async def update_artifact(
    request: Request,
    artifact_id: str,
    body: UpdateArtifactBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    artifact = await artifact_repo.get_by_id(db, artifact_id)
    if artifact is None or artifact.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    if body.content is not None and artifact.artifact_type == "meal_plan":
        _validate_meal_plan_content(body.content)

    await artifact_repo.create_revision(
        db,
        artifact_id=artifact.id,
        snapshot_payload={"title": artifact.title, "content": artifact.content},
        change_summary="Auto-snapshot before update",
    )

    updates: dict = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.content is not None:
        updates["content"] = body.content

    if updates:
        artifact = await artifact_repo.update_artifact(db, artifact_id, **updates)

    await db.commit()
    return _artifact_to_dict(artifact)


@router.post("/{artifact_id}/archive")
@limiter.limit("60/minute")
async def archive_artifact(
    request: Request,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    artifact = await artifact_repo.get_by_id(db, artifact_id)
    if artifact is None or artifact.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    await artifact_repo.archive(db, artifact_id)
    await db.commit()
    return {"id": artifact_id, "status": "archived"}


@router.get("/{artifact_id}/revisions")
@limiter.limit("60/minute")
async def list_revisions(
    request: Request,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    artifact = await artifact_repo.get_by_id(db, artifact_id)
    if artifact is None or artifact.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    revisions = await artifact_repo.list_revisions(db, artifact_id)
    return {"items": [_revision_to_dict(r) for r in revisions]}


@router.post("/{artifact_id}/revisions/{revision_id}/restore")
@limiter.limit("60/minute")
async def restore_revision(
    request: Request,
    artifact_id: str,
    revision_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    artifact = await artifact_repo.get_by_id(db, artifact_id)
    if artifact is None or artifact.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    revision = await artifact_repo.get_revision(db, revision_id)
    if revision is None or revision.artifact_id != artifact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    await artifact_repo.create_revision(
        db,
        artifact_id=artifact.id,
        snapshot_payload={"title": artifact.title, "content": artifact.content},
        change_summary="Auto-snapshot before restore",
    )

    payload = revision.snapshot_payload
    updates: dict = {}
    if "title" in payload:
        updates["title"] = payload["title"]
    if "content" in payload:
        updates["content"] = payload["content"]

    if updates:
        artifact = await artifact_repo.update_artifact(db, artifact_id, **updates)

    await db.commit()
    return _artifact_to_dict(artifact)
