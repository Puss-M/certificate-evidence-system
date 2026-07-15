import asyncio

import httpx

from app.main import app


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_http_exception_uses_api_response_contract() -> None:
    response = asyncio.run(
        _request(
            "POST",
            "/api/auth/login",
            json={"username": "invalid", "password": "invalid"},
        )
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": 401,
        "message": "用户名或密码错误",
        "data": None,
    }


def test_request_validation_uses_api_response_contract() -> None:
    response = asyncio.run(_request("POST", "/api/auth/login", json={}))

    assert response.status_code == 422
    assert response.json() == {
        "code": 422,
        "message": "request validation failed",
        "data": None,
    }
