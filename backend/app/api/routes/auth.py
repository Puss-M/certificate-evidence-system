from pydantic import BaseModel
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.responses import ApiResponse


router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


DEMO_USERS = {
    "admin": {"user_id": 1, "display_name": "系统管理员", "role": "ADMIN"},
    "teacher": {"user_id": 2, "display_name": "实训教师", "role": "TEACHER"},
    "auditor": {"user_id": 3, "display_name": "审计员", "role": "AUDITOR"},
}


def require_roles(*allowed_roles: str):
    def dependency(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="未登录或 token 失效")
        token = authorization.removeprefix("Bearer ").strip()
        for username, user in DEMO_USERS.items():
            if token == f"demo-{username}-token":
                if user["role"] not in allowed_roles:
                    raise HTTPException(status_code=403, detail="无权限执行此操作")
                return {"username": username, **user}
        raise HTTPException(status_code=401, detail="未登录或 token 失效")

    return dependency


def require_admin_access(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    """Protect admin routes while keeping auditors read-only."""
    safe_methods = {"GET", "HEAD", "OPTIONS"}
    allowed_roles = ("ADMIN", "TEACHER", "AUDITOR") if request.method in safe_methods else (
        "ADMIN",
        "TEACHER",
    )
    return require_roles(*allowed_roles)(authorization)


@router.post("/login")
def login(payload: LoginRequest) -> ApiResponse[dict]:
    # 仅供本地联调前端权限路由。正式账号系统必须接 users 表和密码哈希。
    user = DEMO_USERS.get(payload.username)
    if user is None or payload.password != "123456":
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return ApiResponse.success(
        {
            "token": f"demo-{payload.username}-token",
            "user_id": user["user_id"],
            "username": payload.username,
            "display_name": user["display_name"],
            "role": user["role"],
        }
    )
