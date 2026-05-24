from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.config import get_settings
from app.core.s3 import build_asset_ref, generate_presigned_put_url

router = APIRouter(prefix="/media", tags=["media"])
settings = get_settings()


class PresignedUrlBody(BaseModel):
    file_name: str = Field(alias="fileName")
    content_type: str = Field(alias="contentType")
    context: str

    model_config = {"populate_by_name": True}


class PresignedUrlResponse(BaseModel):
    upload_url: str = Field(alias="uploadUrl")
    asset_ref: str = Field(alias="assetRef")
    expires_at: str = Field(alias="expiresAt")

    model_config = {"populate_by_name": True}


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def presigned_url(
    body: PresignedUrlBody,
    user_id: str = Depends(get_current_user_id),
) -> PresignedUrlResponse:
    if not settings.s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 not configured",
        )
    key = build_asset_ref(body.context, user_id, body.file_name)
    url, expires = generate_presigned_put_url(
        bucket=settings.s3_bucket,
        key=key,
        content_type=body.content_type,
    )
    return PresignedUrlResponse(
        uploadUrl=url,
        assetRef=key,
        expiresAt=expires.isoformat().replace("+00:00", "Z"),
    )
