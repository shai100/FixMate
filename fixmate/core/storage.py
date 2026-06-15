import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from fixmate.core.settings import settings

# Single client; boto3 clients are thread-safe and cheap to reuse.
_client = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
    config=Config(signature_version="s3v4"),
)


def ensure_bucket() -> None:
    try:
        _client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        _client.create_bucket(Bucket=settings.s3_bucket)


def put_object(org_id: uuid.UUID, key_suffix: str, data: bytes, content_type: str) -> str:
    # Every key is prefixed with the tenant's org id (CLAUDE.md §6): isolation
    # at the storage layer mirrors Postgres RLS.
    key = f"{org_id}/{key_suffix}"
    ensure_bucket()
    _client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    return key


def object_exists(key: str) -> bool:
    try:
        _client.head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def presigned_url(key: str, expires_in: int = 3600) -> str:
    # Objects are tenant-prefixed and the bucket is private; a short-lived signed
    # URL lets the client fetch a figure without exposing the bucket publicly.
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
