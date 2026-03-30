"""Admin endpoints -- user and permission management."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from iotguard.api.dependencies import AdminUser, DbSession
from iotguard.core.security import Role, hash_password
from iotguard.db.models import User
from iotguard.db.repositories import PermissionRepository, UserRepository

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("viewer", pattern=r"^(admin|operator|viewer)$")


class RoleUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(admin|operator|viewer)$")


class PermissionOut(BaseModel):
    id: str
    device_id: str
    can_read: bool
    can_write: bool
    can_execute: bool
    granted_at: datetime

    class Config:
        from_attributes = True


class PermissionGrant(BaseModel):
    device_id: uuid.UUID
    can_read: bool = True
    can_write: bool = False
    can_execute: bool = False


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
async def list_users(
    user: AdminUser,
    session: DbSession,
    offset: int = 0,
    limit: int = 50,
) -> list[UserOut]:
    repo = UserRepository(session)
    users = await repo.list_all(offset=offset, limit=limit)
    return [
        UserOut(
            id=str(u.id),
            username=u.username,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    user: AdminUser,
    session: DbSession,
) -> UserOut:
    repo = UserRepository(session)
    existing = await repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    new_user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    new_user = await repo.create(new_user)
    return UserOut(
        id=str(new_user.id),
        username=new_user.username,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
    )


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def update_role(
    user_id: uuid.UUID,
    body: RoleUpdate,
    user: AdminUser,
    session: DbSession,
) -> UserOut:
    repo = UserRepository(session)
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await repo.update_role(user_id, body.role)
    await session.refresh(target)
    return UserOut(
        id=str(target.id),
        username=target.username,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    user: AdminUser,
    session: DbSession,
) -> None:
    repo = UserRepository(session)
    target = await repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await repo.deactivate(user_id)


# ---------------------------------------------------------------------------
# Permission endpoints
# ---------------------------------------------------------------------------


@router.get("/users/{user_id}/permissions", response_model=list[PermissionOut])
async def list_permissions(
    user_id: uuid.UUID,
    user: AdminUser,
    session: DbSession,
) -> list[PermissionOut]:
    repo = PermissionRepository(session)
    perms = await repo.get_user_permissions(user_id)
    return [
        PermissionOut(
            id=str(p.id),
            device_id=str(p.device_id),
            can_read=p.can_read,
            can_write=p.can_write,
            can_execute=p.can_execute,
            granted_at=p.granted_at,
        )
        for p in perms
    ]


@router.post("/users/{user_id}/permissions", response_model=PermissionOut, status_code=201)
async def grant_permission(
    user_id: uuid.UUID,
    body: PermissionGrant,
    user: AdminUser,
    session: DbSession,
) -> PermissionOut:
    repo = PermissionRepository(session)
    perm = await repo.grant(
        user_id,
        body.device_id,
        can_read=body.can_read,
        can_write=body.can_write,
        can_execute=body.can_execute,
    )
    return PermissionOut(
        id=str(perm.id),
        device_id=str(perm.device_id),
        can_read=perm.can_read,
        can_write=perm.can_write,
        can_execute=perm.can_execute,
        granted_at=perm.granted_at,
    )


@router.delete("/users/{user_id}/permissions/{device_id}", status_code=204)
async def revoke_permission(
    user_id: uuid.UUID,
    device_id: uuid.UUID,
    user: AdminUser,
    session: DbSession,
) -> None:
    repo = PermissionRepository(session)
    await repo.revoke(user_id, device_id)
