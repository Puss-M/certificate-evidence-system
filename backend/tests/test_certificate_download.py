"""
证书下载接口测试：公共端不允许下载，管理员和学生各走鉴权接口。
"""
import asyncio
from datetime import datetime

import httpx

from app.main import app
from app.models.student import Student
from app.services import certificate_service


TEMPLATE = {
    "template_code": "TPL-001",
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}


async def _get(path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers=headers)


def test_admin_download_certificate_returns_pdf_bytes(db_session) -> None:
    student = Student(student_no="2023501", student_name="下载测试", class_name="1班")
    db_session.add(student)
    db_session.commit()

    certificate = certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )

    response = asyncio.run(
        _get(
            f"/api/admin/certificates/{certificate.certificate_no}/download",
            headers={"Authorization": "Bearer demo-admin-token"},
        )
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    expected_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    assert response.content == expected_path.read_bytes()


def test_admin_download_requires_authentication_and_unknown_certificate_is_404(db_session) -> None:
    unauthenticated = asyncio.run(_get("/api/admin/certificates/CERT-NOT-EXIST/download"))
    response = asyncio.run(
        _get(
            "/api/admin/certificates/CERT-NOT-EXIST/download",
            headers={"Authorization": "Bearer demo-admin-token"},
        )
    )
    assert unauthenticated.status_code == 401
    assert response.status_code == 404


def test_public_download_route_is_not_available(db_session) -> None:
    response = asyncio.run(_get("/api/certificates/CERT-NOT-EXIST/download"))
    assert response.status_code == 404
