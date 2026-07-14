"""
证书下载接口测试（GET /api/certificates/{certificate_no}/download）。
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


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def test_download_certificate_returns_pdf_bytes(db_session) -> None:
    student = Student(student_no="2023501", student_name="下载测试", class_name="1班")
    db_session.add(student)
    db_session.commit()

    certificate = certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )

    response = asyncio.run(_get(f"/api/certificates/{certificate.certificate_no}/download"))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    expected_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    assert response.content == expected_path.read_bytes()


def test_download_certificate_returns_404_for_unknown_certificate_no(db_session) -> None:
    response = asyncio.run(_get("/api/certificates/CERT-NOT-EXIST/download"))
    assert response.status_code == 404
