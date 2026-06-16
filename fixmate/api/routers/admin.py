import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fixmate.api.deps import AuthContext, ROLES, require_role
from fixmate.api.schemas import (
    CreateUserRequest,
    SetRoleRequest,
    UpdateUserRequest,
    UserOut,
)
from fixmate.core.db import session_for_org
from fixmate.core.models import AuditEvent, User


def _user_out(u: User) -> UserOut:
    return UserOut(id=u.id, name=u.name, email=u.email, role=u.role, created_at=u.created_at)

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
        return [_user_out(u) for u in rows]


@router.post("/users", status_code=201, response_model=UserOut)
async def create_user(
    body: CreateUserRequest,
    auth: AuthContext = Depends(admin_only),
) -> UserOut:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {ROLES}")
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name must not be empty")
    async with session_for_org(auth.org_id) as s:
        user = User(
            organization_id=auth.org_id,
            name=body.name.strip(),
            email=body.email,
            role=body.role,
        )
        s.add(user)
        await s.flush()
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="user",
                entity_id=user.id,
                action="create",
                before=None,
                after={"name": user.name, "email": user.email, "role": user.role},
            )
        )
        await s.commit()
        return _user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    auth: AuthContext = Depends(admin_only),
) -> UserOut:
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {ROLES}")
    async with session_for_org(auth.org_id) as s:
        user = await s.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        before = {"name": user.name, "email": user.email, "role": user.role}
        if body.name is not None:
            if not body.name.strip():
                raise HTTPException(status_code=422, detail="name must not be empty")
            user.name = body.name.strip()
        if body.email is not None:
            user.email = body.email
        if body.role is not None:
            user.role = body.role
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="user",
                entity_id=user.id,
                action="update",
                before=before,
                after={"name": user.name, "email": user.email, "role": user.role},
            )
        )
        await s.commit()
        return _user_out(user)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(admin_only),
) -> None:
    # An admin deleting themselves would lock the tenant out of user management;
    # reject it rather than risk an orphaned org.
    if user_id == auth.user_id:
        raise HTTPException(status_code=409, detail="cannot delete your own account")
    async with session_for_org(auth.org_id) as s:
        user = await s.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        s.add(
            AuditEvent(
                organization_id=auth.org_id,
                actor_id=auth.user_id,
                entity_type="user",
                entity_id=user.id,
                action="delete",
                before={"name": user.name, "email": user.email, "role": user.role},
                after=None,
            )
        )
        await s.delete(user)
        await s.commit()


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
        return _user_out(user)
