"""Local-only convenience endpoint for demo auto-login.

In local dev the web client can skip manual org/user UUID entry by calling
``GET /dev/auto-login``, which resolves (and, the first time, provisions) an
admin of the demo tenant. It is double-gated (``dev_auth`` *and*
``dev_auto_login``) and runs as a bootstrap operation outside any tenant context,
so it must never be reachable in a real deployment — ``main._guard_auth_config``
already forbids ``dev_auth`` outside ``local``.
"""

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from fixmate.api.schemas import DevIdentityOut
from fixmate.core.models import Organization, User
from fixmate.core.settings import settings

router = APIRouter(prefix="/dev", tags=["dev"])

# The fixed display name of the auto-provisioned dev admin. Reused on every call
# so re-running never creates duplicate admins in the demo tenant.
AUTO_ADMIN_NAME = "Auto Admin"
AUTO_ADMIN_EMAIL = "admin@demo.fixmate.local"


@router.get("/auto-login", response_model=DevIdentityOut)
async def auto_login() -> DevIdentityOut:
    """Resolve (and provision) an admin identity for the demo tenant (dev only).

    Gated twice: only when DEV_AUTH and DEV_AUTO_LOGIN are both on. This is a
    bootstrap operation outside any tenant context, so it runs on the owner
    connection (like ingestion.registry) — it must not be reachable in a real
    deployment, which main._guard_auth_config already forbids for DEV_AUTH.
    """
    if not (settings.dev_auth and settings.dev_auto_login):
        raise HTTPException(status_code=404, detail="dev auto-login is disabled")

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            org_id = await conn.scalar(
                select(Organization.id).where(Organization.name == settings.dev_demo_org)
            )
            if org_id is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"demo org {settings.dev_demo_org!r} not found; "
                        "run scripts/seed_demo.py first"
                    ),
                )
            user_id = await conn.scalar(
                select(User.id).where(
                    User.organization_id == org_id, User.name == AUTO_ADMIN_NAME
                )
            )
            if user_id is None:
                user_id = await conn.scalar(
                    User.__table__.insert()
                    .values(
                        organization_id=org_id,
                        name=AUTO_ADMIN_NAME,
                        email=AUTO_ADMIN_EMAIL,
                        role="admin",
                    )
                    .returning(User.id)
                )
    finally:
        await engine.dispose()

    return DevIdentityOut(org_id=uuid.UUID(str(org_id)), user_id=uuid.UUID(str(user_id)), role="admin")
