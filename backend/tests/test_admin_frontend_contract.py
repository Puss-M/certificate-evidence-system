import asyncio
from datetime import datetime

import httpx

from app.main import app
from app.models.student import Student
from app.services import certificate_service


TEMPLATE = {
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "合格",
}


async def request_json(method: str, path: str, **kwargs) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.request(method, path, **kwargs)
    assert response.status_code == 200
    return response.json()


async def request_response(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_admin_login_matches_frontend_contract() -> None:
    data = asyncio.run(
        request_json("POST", "/api/auth/login", json={"username": "admin", "password": "123456"})
    )

    assert data["code"] == 0
    assert data["data"]["token"]
    assert data["data"]["role"] == "ADMIN"


def test_admin_students_returns_page_result(db_session) -> None:
    db_session.add(
        Student(
            student_no="S20260001",
            student_name="Demo Student A",
            college="计算机学院",
            class_name="Class 1",
            major_name="Software Engineering",
        )
    )
    db_session.commit()

    data = asyncio.run(request_json("GET", "/api/admin/students?current=1&size=10"))

    assert data["code"] == 0
    assert data["data"]["total"] == 1
    assert data["data"]["records"][0]["student_no"] == "S20260001"
    assert data["data"]["records"][0]["college"] == "计算机学院"


def test_admin_student_college_is_created_and_updated(db_session) -> None:
    created = asyncio.run(
        request_json(
            "POST",
            "/api/admin/students",
            json={
                "student_no": "S20260005",
                "student_name": "Demo Student E",
                "college": "计算机学院",
                "major": "软件工程",
                "class_name": "Class 2",
            },
        )
    )

    student_id = created["data"]["student_id"]
    assert created["data"]["college"] == "计算机学院"

    updated = asyncio.run(
        request_json(
            "PUT",
            f"/api/admin/students/{student_id}",
            json={"college": "人工智能学院"},
        )
    )

    assert updated["data"]["college"] == "人工智能学院"
    assert db_session.get(Student, student_id).college == "人工智能学院"


def test_admin_student_rejects_overlong_college(db_session) -> None:
    response = asyncio.run(
        request_response(
            "POST",
            "/api/admin/students",
            json={
                "student_no": "S20260006",
                "student_name": "Demo Student F",
                "college": "学" * 101,
            },
        )
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert db_session.query(Student).filter_by(student_no="S20260006").one_or_none() is None


def test_admin_frontend_page_endpoints_are_available(db_session) -> None:
    paths = [
        "/api/admin/dashboard/statistics",
        "/api/admin/projects?current=1&size=10",
        "/api/admin/students?current=1&size=10",
        "/api/admin/templates?current=1&size=10",
        "/api/admin/certificate-batches?current=1&size=10",
        "/api/admin/certificates?current=1&size=10",
        "/api/admin/evidence/receipts?current=1&size=10",
        "/api/admin/evidence/integrity",
        "/api/admin/audit-logs?current=1&size=10",
    ]

    for path in paths:
        data = asyncio.run(request_json("GET", path))
        assert data["code"] == 0, path
        assert "data" in data, path


def test_admin_certificates_and_receipts_use_generated_chain_data(db_session) -> None:
    student = Student(
        student_no="S20260002",
        student_name="Demo Student B",
        class_name="Class 1",
        major_name="Software Engineering",
    )
    db_session.add(student)
    db_session.commit()

    certificate = certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )

    certificates = asyncio.run(request_json("GET", "/api/admin/certificates?current=1&size=10"))
    receipts = asyncio.run(request_json("GET", "/api/admin/evidence/receipts?current=1&size=10"))
    integrity = asyncio.run(request_json("GET", "/api/admin/evidence/integrity"))

    first_certificate = certificates["data"]["records"][0]
    first_receipt = receipts["data"]["records"][0]

    assert first_certificate["certificate_no"] == certificate.certificate_no
    assert first_certificate["project_name"] == TEMPLATE["project_name"]
    assert first_certificate["issue_date"] == "2026-07-14"
    assert first_certificate["evidence_status"] == "CONFIRMED"
    assert first_receipt["receipt_id"] == certificate.receipt_id
    assert first_receipt["evidence_type"] == "LOCAL_HASH_CHAIN"
    assert integrity["data"]["valid"] is True


def test_admin_issue_endpoint_generates_certificates_for_frontend(db_session) -> None:
    student = Student(
        student_no="S20260003",
        student_name="Demo Student C",
        class_name="Class 1",
        major_name="Software Engineering",
    )
    db_session.add(student)
    db_session.commit()

    data = asyncio.run(
        request_json(
            "POST",
            "/api/admin/certificate-batches/1/issue",
            json={
                "project_id": 1,
                "template_id": 1,
                "batch_id": 1,
                "student_ids": [student.student_id],
                "issue_date": "2026-07-14",
            },
        )
    )

    assert data["data"]["success_count"] == 1
    assert data["data"]["failed_count"] == 0


def test_admin_revoke_accepts_certificate_no_from_frontend(db_session) -> None:
    student = Student(
        student_no="S20260004",
        student_name="Demo Student D",
        class_name="Class 1",
        major_name="Software Engineering",
    )
    db_session.add(student)
    db_session.commit()

    certificate = certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )

    data = asyncio.run(
        request_json(
            "POST",
            f"/api/admin/certificates/{certificate.certificate_no}/revoke",
            json={"reason": "frontend revoke by certificate_no"},
        )
    )

    assert data["data"]["certificate_no"] == certificate.certificate_no
    assert data["data"]["status"] == "REVOKED"
