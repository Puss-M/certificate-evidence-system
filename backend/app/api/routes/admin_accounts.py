from datetime import datetime, timedelta
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.auth import require_roles
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import AuthSession, Invitation, User


router = APIRouter(prefix="/admin")


class InvitationCreateRequest(BaseModel):
    expires_in_hours: int = Field(default=48, ge=1, le=168)


class UserStatusUpdate(BaseModel):
    is_active: bool


def _user_record(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _current_user: dict = Depends(require_roles("ADMIN")),
) -> ApiResponse[list[dict]]:
    users = db.query(User).order_by(User.created_at.asc()).all()
    return ApiResponse.success([_user_record(user) for user in users])


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("ADMIN")),
) -> ApiResponse[dict]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if user.user_id == current_user["user_id"] and not payload.is_active:
        raise HTTPException(status_code=409, detail="不能禁用当前登录的管理员账号")
    user.is_active = payload.is_active
    if not payload.is_active:
        db.query(AuthSession).filter(
            AuthSession.user_id == user.user_id,
            AuthSession.revoked_at.is_(None),
        ).update({AuthSession.revoked_at: datetime.utcnow()}, synchronize_session=False)
    db.add(
        AuditLog(
            action="账号状态变更",
            target_type="账号管理",
            target_id=str(user.user_id),
            operator=current_user["username"],
            detail=f"is_active={payload.is_active}",
        )
    )
    db.commit()
    db.refresh(user)
    return ApiResponse.success(_user_record(user))


@router.post("/invitations")
def create_teacher_invitation(
    payload: InvitationCreateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("ADMIN")),
) -> ApiResponse[dict]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=payload.expires_in_hours)
    invitation = Invitation(
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        role="TEACHER",
        created_by=current_user["user_id"],
        expires_at=expires_at,
    )
    db.add(invitation)
    db.add(
        AuditLog(
            action="创建教师邀请",
            target_type="账号管理",
            target_id=None,
            operator=current_user["username"],
            detail=f"expires_at={expires_at.isoformat()}",
        )
    )
    db.commit()
    return ApiResponse.success(
        {
            "invitation_token": token,
            "role": "TEACHER",
            "expires_at": expires_at.isoformat(),
        }
    )
