from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.responses import ErrorResponse


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        responses={
            400: {"model": ErrorResponse, "description": "请求参数错误"},
            401: {"model": ErrorResponse, "description": "未登录或 token 失效"},
            403: {"model": ErrorResponse, "description": "无权限"},
            404: {"model": ErrorResponse, "description": "数据不存在"},
            409: {"model": ErrorResponse, "description": "状态冲突"},
            422: {"model": ErrorResponse, "description": "请求字段校验失败"},
            500: {"model": ErrorResponse, "description": "系统异常"},
        },
    )

    register_exception_handlers(application)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app()
