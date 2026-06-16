"""Object-storage wrapper for binary files (original PDFs, extracted figures).

Large binaries do not belong in Postgres, so FixMate keeps them in an
S3-compatible object store: MinIO when running locally, AWS S3 in the cloud.
Both speak the same API, so this module talks to whichever one ``settings``
points at without caring which it is.

Tenant isolation (CLAUDE.md §6) is enforced the same way it is in the database:
every object key is prefixed with the owning organization's id, so one tenant's
files live under a path another tenant never reads. A single shared boto3 client
is created at import time (boto3 clients are thread-safe and cheap to reuse).
"""

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
    """Create the configured bucket if it does not already exist (idempotent).

    Called before every upload so a fresh environment "just works"; a HEAD that
    fails is taken to mean "not there yet" and triggers a create.
    """
    try:
        _client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        _client.create_bucket(Bucket=settings.s3_bucket)


def put_object(org_id: uuid.UUID, key_suffix: str, data: bytes, content_type: str) -> str:
    """Upload bytes for a tenant and return the full storage key.

    Args:
        org_id: Owning tenant; becomes the leading path segment of the key.
        key_suffix: Path within the tenant's space (e.g. ``"figures/abc.png"``).
        data: Raw file bytes.
        content_type: MIME type stored alongside the object (e.g. ``"image/png"``).

    Returns:
        The full object key (``"<org_id>/<key_suffix>"``) to persist in the DB
        so the object can be fetched again later.
    """
    # Every key is prefixed with the tenant's org id (CLAUDE.md §6): isolation
    # at the storage layer mirrors Postgres RLS.
    key = f"{org_id}/{key_suffix}"
    ensure_bucket()
    _client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    return key


def delete_object(key: str) -> None:
    """Best-effort delete of one object by its full key.

    Swallows errors on purpose: the database row is the source of truth, so an
    object that is already gone (or never existed) must not fail the request
    (CLAUDE.md §2.4).
    """
    try:
        _client.delete_object(Bucket=settings.s3_bucket, Key=key)
    except ClientError:
        pass


def object_exists(key: str) -> bool:
    """Return True if an object with this key is present in the bucket."""
    try:
        _client.head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def presigned_url(key: str, expires_in: int = 3600) -> str:
    """Return a temporary, signed HTTPS URL that grants read access to one object.

    The bucket itself is private. Rather than proxy every image through the API,
    we hand the browser a URL that embeds a time-limited signature, so the client
    can fetch a figure directly from object storage.

    Args:
        key: Full object key to grant access to.
        expires_in: Seconds the URL stays valid (default 1 hour).
    """
    # Objects are tenant-prefixed and the bucket is private; a short-lived signed
    # URL lets the client fetch a figure without exposing the bucket publicly.
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
