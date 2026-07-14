import asyncio

import httpx

from app.main import app


async def get_json(path: str) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(path)

    assert response.status_code == 200
    return response.json()


def test_students_endpoint_returns_mock_students() -> None:
    data = asyncio.run(get_json("/api/students"))

    assert data["code"] == 0
    assert data["data"][0]["student_no"] == "20260001"


def test_certificates_endpoint_returns_required_fields() -> None:
    data = asyncio.run(get_json("/api/certificates"))
    certificate = data["data"][0]

    assert certificate["certificate_no"] == "CERT-20260714-0001"
    assert certificate["student_name"] == "Test Student A"
    assert len(certificate["certificate_hash"]) == 64
    assert certificate["receipt_id"] == "RCPT-20260714-0001"
    assert certificate["status"] == "VALID"


# /api/verification 的测试挪到 tests/test_verification.py 了——那个接口现在是
# 真实数据库读写，不再是mock数据，用的是 conftest.py 里的 db_session fixture。
