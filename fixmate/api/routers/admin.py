import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fixmate.api.deps import AuthContext, ROLES, require_role
from fixmate.api.schemas import SetRoleRequest, UserOut
from fixmate.core.db import session_for_org
from fixmate.core.models import AuditEvent, User

# User/role management is admin-only (FR-14): only an admin may change who can
# curate. The guard rejects techs and curators with 403 before any handler runs.
admin_only = require_role("admin")

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(auth: AuthContext = Depends(admin_only)) -> list[UserOut]:
    async with session_for_org(auth.org_id) as s:
        rows = (
            (await s.execute(select(User).order_by(User.created_at))).scalars().all()
        )
        return [
            UserOut(id=u.id, name=u.name, email=u.email, role=u.role, created_at=u.created_at)
            for u in rows
        ]


@router.post("/users/{user_id}/role", response_model=UserOut)
async def set_user_role(
    user_id: uuid.UUID,
    body: SetRoleRequest,
    auth: AuthContext = Depends(admin_only),
) -> UserOut:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {ROLES}")
    async with session_for_org(auth.org_id) as s:
        user = await s.get(User, user_id)
        # RLS scopes the query to the admin's org, so a cross-tenant id reads as
        # absent — a 404, never a leak.
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        before = {"role": user.role}
        user.role = body.role
        # Every role change is an audited state change (CLAUDE.md §4.5 / §8.2).
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="user",
                entity_id=user.id,
                action="set_role",
                before=before,
                after={"role": body.role},
            )
        )
        await s.commit()
        return UserOut(
            id=user.id, name=user.name, email=user.email, role=user.role, created_at=user.created_at
        )
