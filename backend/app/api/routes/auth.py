from datetime import datetime, timedelta
import hashlib
import secrets

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.db.session import SessionLocal
from app.models.user import AuthSession, Invitation, User


router = APIRouter(prefix="/auth")
PASSWORD_HASH = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
DEMO_USERS = {
    "admin": {"user_id": 1, "display_name": "系统管理员", "role": "ADMIN"},
    "teacher": {"user_id": 2, "display_name": "实训教师", "role": "TEACHER"},
    "auditor": {"user_id": 3, "display_name": "审计员", "role": "AUDITOR"},
}


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class InvitationRegistrationRequest(BaseModel):
    invitation_token: str = Field(min_length=20, max_length=256)
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = value.strip()
        if not username or any(not (char.isalnum() or char in "._-") for char in username):
            raise ValueError("用户名只能包含字母、数字、点、下划线和连字符")
        return username

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        display_name = value.strip()
        if not display_name:
            raise ValueError("显示名称不能为空")
        return display_name


def _auth_secret() -> str:
    if not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="服务器认证配置缺失")
    return settings.jwt_secret


def get_auth_db():
    """Allow only the isolated legacy-demo test contract to run without a database."""
    if SessionLocal is None:
        if settings.enable_demo_auth:
            yield None
            return
        raise RuntimeError("DATABASE_URL is not configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _serialize_user(user: User | dict) -> dict:
    if isinstance(user, dict):
        return user
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
    }


def _create_token(user: User, db: Session) -> str:
    secret = _auth_secret()
    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(minutes=settings.auth_access_token_minutes)
    jti = secrets.token_urlsafe(32)
    payload = {
        "sub": str(user.user_id),
        "role": user.role,
        "jti": jti,
        "iat": issued_at,
        "exp": expires_at,
    }
    db.add(AuthSession(jti=jti, user_id=user.user_id, expires_at=expires_at))
    db.commit()
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _demo_user_for_token(token: str) -> dict | None:
    if not settings.enable_demo_auth:
        return None
    for username, user in DEMO_USERS.items():
        if token == f"demo-{username}-token":
            return {"username": username, **user, "is_active": True, "demo": True}
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或 token 失效")
    token = authorization.removeprefix("Bearer ").strip()
    demo_user = _demo_user_for_token(token)
    if demo_user is not None:
        return demo_user

    try:
        payload = jwt.decode(token, _auth_secret(), algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
        jti = str(payload["jti"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="未登录或 token 失效") from exc

    user = db.get(User, user_id)
    session = db.get(AuthSession, jti)
    if (
        user is None
        or not user.is_active
        or session is None
        or session.user_id != user.user_id
        or session.revoked_at is not None
        or session.expires_at <= datetime.utcnow()
    ):
        raise HTTPException(status_code=401, detail="未登录或 token 失效")
    return {**_serialize_user(user), "jti": jti}


def require_roles(*allowed_roles: str):
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="无权限执行此操作")
        return current_user

    return dependency


def require_admin_access(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    safe_methods = {"GET", "HEAD", "OPTIONS"}
    auditor_paths = ("/api/admin/evidence/", "/api/admin/audit-logs")
    if current_user["role"] == "AUDITOR":
        if request.method in safe_methods and request.url.path.startswith(auditor_paths):
            return current_user
        raise HTTPException(status_code=403, detail="无权限执行此操作")
    if current_user["role"] not in ("ADMIN", "TEACHER"):
        raise HTTPException(status_code=403, detail="无权限执行此操作")
    return current_user


def _login_response(user: User, db: Session) -> ApiResponse[dict]:
    return ApiResponse.success({"token": _create_token(user, db), **_serialize_user(user)})


@router.post("/login")
def login(payload: LoginRequest, db: Session | None = Depends(get_auth_db)) -> ApiResponse[dict]:
    username = payload.username.strip()
    if settings.enable_demo_auth:
        demo_user = DEMO_USERS.get(username)
        if demo_user is not None and payload.password == "123456":
            return ApiResponse.success({"token": f"demo-{username}-token", "username": username, **demo_user})

    if db is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active or not PASSWORD_HASH.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _login_response(user, db)


@router.post("/logout")
def logout(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    jti = current_user.get("jti")
    if jti:
        session = db.get(AuthSession, jti)
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            db.commit()
    return ApiResponse.success({"logged_out": True})


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)) -> ApiResponse[dict]:
    return ApiResponse.success({key: value for key, value in current_user.items() if key not in {"jti", "demo"}})


@router.post("/register/invitation")
def register_from_invitation(
    payload: InvitationRegistrationRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    now = datetime.utcnow()
    token_hash = hashlib.sha256(payload.invitation_token.encode("utf-8")).hexdigest()
    invitation = (
        db.query(Invitation)
        .filter(Invitation.token_hash == token_hash)
        .with_for_update()
        .first()
    )
    if (
        invitation is None
        or invitation.role != "TEACHER"
        or invitation.used_at is not None
        or invitation.expires_at <= now
    ):
        raise HTTPException(status_code=400, detail="邀请链接无效、已使用或已过期")
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    invitation.used_at = now
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=PASSWORD_HASH.hash(payload.password),
        role=invitation.role,
    )
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    return _login_response(user, db)
