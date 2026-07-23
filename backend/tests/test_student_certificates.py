import asyncio
from datetime import datetime

import httpx
from pwdlib import PasswordHash

from app.main import app
from app.models.student import Student
from app.models.user import User
from app.services import certificate_service


TEMPLATE = {
    "template_code": "TPL-001",
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


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


def _student_headers(db_session, student: Student, *, must_change_password: bool = False) -> dict[str, str]:
    password = "student-initial-password"
    db_session.add(
        User(
            username=student.student_no,
            display_name=student.student_name,
            password_hash=PasswordHash.recommended().hash(password),
            role="STUDENT",
            student_id=student.student_id,
            must_change_password=must_change_password,
        )
    )
    db_session.commit()
    response = asyncio.run(
        _request("POST", "/api/auth/login", json={"username": student.student_no, "password": password})
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def _seed_certificate(db_session, student: Student):
    return certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )


def test_student_certificate_list_uses_logged_in_student_not_query_parameter(db_session) -> None:
    zhang = _seed_student(db_session, "S20260001", "张三")
    li = _seed_student(db_session, "S20260002", "李四")
    zhang_certificate = _seed_certificate(db_session, zhang)
    _seed_certificate(db_session, li)
    headers = _student_headers(db_session, zhang)

    response = asyncio.run(
        _request("GET", "/api/student/certificates?student_no=S20260002", headers=headers)
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["certificate_no"] == zhang_certificate.certificate_no
    assert data[0]["student_no"] == "S20260001"
    assert asyncio.run(_request("GET", "/api/student/certificates")).status_code == 401


def test_student_certificate_detail_download_and_qrcode_enforce_owner(db_session) -> None:
    owner = _seed_student(db_session, "S20260004", "赵六")
    other = _seed_student(db_session, "S20260005", "陈晨")
    certificate = _seed_certificate(db_session, owner)
    owner_headers = _student_headers(db_session, owner)
    other_headers = _student_headers(db_session, other)

    detail = asyncio.run(
        _request("GET", f"/api/student/certificates/{certificate.certificate_no}", headers=owner_headers)
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["certificate_hash"] == certificate.certificate_hash

    forbidden = asyncio.run(
        _request(
            "GET", f"/api/student/certificates/{certificate.certificate_no}/download", headers=other_headers
        )
    )
    assert forbidden.status_code == 404

    download = asyncio.run(
        _request(
            "GET", f"/api/student/certificates/{certificate.certificate_no}/download", headers=owner_headers
        )
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"

    qrcode = asyncio.run(
        _request(
            "GET", f"/api/student/certificates/{certificate.certificate_no}/qrcode", headers=owner_headers
        )
    )
    assert qrcode.status_code == 200
    assert qrcode.headers["content-type"] == "image/png"


def test_student_with_initial_password_must_change_it_before_access(db_session) -> None:
    student = _seed_student(db_session, "S20260006", "周敏")
    _seed_certificate(db_session, student)
    headers = _student_headers(db_session, student, must_change_password=True)

    blocked = asyncio.run(_request("GET", "/api/student/certificates", headers=headers))
    assert blocked.status_code == 403

    changed = asyncio.run(
        _request(
            "POST",
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": "student-initial-password", "new_password": "student-updated-password"},
        )
    )
    assert changed.status_code == 200
    assert asyncio.run(_request("GET", "/api/student/certificates", headers=headers)).status_code == 200
