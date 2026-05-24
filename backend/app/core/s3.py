import uuid
from datetime import UTC, datetime, timedelta

import boto3
from botocore.client import BaseClient
from botocore.config import Config as BotoConfig

from app.core.config import get_settings

_settings = get_settings()
_client: BaseClient | None = None


def get_s3_client() -> BaseClient:
    global _client
    if _client is None:
        kwargs: dict = {
            "region_name": _settings.aws_region,
        }
        if _settings.aws_access_key_id and _settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = _settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = _settings.aws_secret_access_key
        if _settings.s3_endpoint_url:
            kwargs["endpoint_url"] = _settings.s3_endpoint_url
            kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})
        _client = boto3.client("s3", **kwargs)
    return _client


def build_asset_ref(context: str, user_id: str, file_name: str) -> str:
    safe = file_name.replace("/", "_")
    uid = uuid.uuid4().hex[:12]
    return f"uploads/{user_id}/{context}/{uid}_{safe}"


def generate_presigned_put_url(
    *,
    bucket: str,
    key: str,
    content_type: str,
    expires_seconds: int = 900,
) -> tuple[str, datetime]:
    client = get_s3_client()
    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_seconds,
    )
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=expires_seconds)
    return url, expires_at


def delete_objects(*, bucket: str, keys: list[str]) -> None:
    """Delete one or more objects from S3. Silently ignores missing keys."""
    if not keys:
        return
    client = get_s3_client()
    batches = [keys[i:i + 1000] for i in range(0, len(keys), 1000)]
    for batch in batches:
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
        )


def generate_presigned_get_url(
    *,
    bucket: str,
    key: str,
    expires_seconds: int = 3600,
) -> str:
    """Generate a presigned GET URL for reading an S3 object."""
    client = get_s3_client()
    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )
