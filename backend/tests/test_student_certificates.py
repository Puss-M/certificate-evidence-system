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


def _seed_student(db_session, student_no: str, student_name: str) -> Student:
    student = Student(
        student_no=student_no,
        student_name=student_name,
        class_name="软件工程2401",
        major_name="软件工程",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


def _seed_certificate(db_session, student: Student):
    return certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )


def test_student_certificate_list_only_returns_current_student_records(db_session) -> None:
    zhang = _seed_student(db_session, "S20260001", "张三")
    li = _seed_student(db_session, "S20260002", "李四")
    zhang_certificate = _seed_certificate(db_session, zhang)
    _seed_certificate(db_session, li)

    response = asyncio.run(_get("/api/student/certificates?student_no=S20260001"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["certificate_no"] == zhang_certificate.certificate_no
    assert data[0]["student_no"] == "S20260001"
    assert data[0]["student_name"] == "张三"
    assert data[0]["evidence_status"] == "CONFIRMED"


def test_student_certificate_detail_returns_hash_receipt_and_share_fields(db_session) -> None:
    student = _seed_student(db_session, "S20260003", "王五")
    certificate = _seed_certificate(db_session, student)

    response = asyncio.run(
        _get(f"/api/student/certificates/{certificate.certificate_no}?student_no=S20260003")
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["certificate_hash"] == certificate.certificate_hash
    assert data["receipt_id"] == certificate.receipt_id
    assert data["verify_url"] == certificate.verify_url
    assert data["qr_code_path"] == certificate.qr_code_path
    assert data["status"] == "VALID"


def test_student_certificate_download_requires_owner_and_returns_pdf(db_session) -> None:
    owner = _seed_student(db_session, "S20260004", "赵六")
    other = _seed_student(db_session, "S20260005", "陈晨")
    certificate = _seed_certificate(db_session, owner)
    _seed_certificate(db_session, other)

    forbidden = asyncio.run(
        _get(f"/api/student/certificates/{certificate.certificate_no}/download?student_no=S20260005")
    )
    assert forbidden.status_code == 404

    response = asyncio.run(
        _get(f"/api/student/certificates/{certificate.certificate_no}/download?student_no=S20260004")
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    expected_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    assert response.content == expected_path.read_bytes()


def test_student_certificate_qrcode_returns_png(db_session) -> None:
    student = _seed_student(db_session, "S20260006", "周敏")
    certificate = _seed_certificate(db_session, student)

    response = asyncio.run(
        _get(f"/api/student/certificates/{certificate.certificate_no}/qrcode?student_no=S20260006")
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    expected_path = certificate_service.PROJECT_ROOT / certificate.qr_code_path
    assert response.content == expected_path.read_bytes()


def test_student_certificate_list_returns_404_for_unknown_student(db_session) -> None:
    response = asyncio.run(_get("/api/student/certificates?student_no=UNKNOWN"))

    assert response.status_code == 404
