from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

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
