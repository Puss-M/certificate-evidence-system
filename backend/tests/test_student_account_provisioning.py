import asyncio

import httpx
from pwdlib import PasswordHash

from app.main import app
from app.models.student import Student
from app.models.user import User


async def request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def login_headers(username: str, password: str) -> dict[str, str]:
    response = asyncio.run(request("POST", "/api/auth/login", json={"username": username, "password": password}))
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_admin_can_provision_reset_and_revoke_student_account_sessions(db_session) -> None:
    admin_password = "administrator-test-password"
    admin = User(
        username="account-admin",
        display_name="Account Admin",
        password_hash=PasswordHash.recommended().hash(admin_password),
        role="ADMIN",
    )
    student = Student(student_no="S20269999", student_name="测试学生")
    db_session.add_all([admin, student])
    db_session.commit()
    admin_headers = login_headers(admin.username, admin_password)

    provisioned = asyncio.run(
        request(
            "POST",
            "/api/admin/students/accounts/provision",
            headers=admin_headers,
            json={"student_ids": [student.student_id]},
        )
    )
    assert provisioned.status_code == 200
    credential = provisioned.json()["data"]["created"][0]
    assert credential["student_no"] == student.student_no
    assert credential["initial_password"]

    student_login = asyncio.run(
        request(
            "POST",
            "/api/auth/login",
            json={"username": student.student_no, "password": credential["initial_password"]},
        )
    )
    assert student_login.status_code == 200
    assert student_login.json()["data"]["role"] == "STUDENT"
    assert student_login.json()["data"]["must_change_password"] is True
    student_headers = {"Authorization": f"Bearer {student_login.json()['data']['token']}"}
    assert asyncio.run(request("GET", "/api/student/certificates", headers=student_headers)).status_code == 403

    changed = asyncio.run(
        request(
            "POST",
            "/api/auth/change-password",
            headers=student_headers,
            json={"current_password": credential["initial_password"], "new_password": "student-new-password"},
        )
    )
    assert changed.status_code == 200
    assert asyncio.run(request("GET", "/api/student/certificates", headers=student_headers)).status_code == 200

    reset = asyncio.run(
        request(
            "POST",
            f"/api/admin/students/{student.student_id}/account/reset-password",
            headers=admin_headers,
        )
    )
    assert reset.status_code == 200
    assert asyncio.run(request("GET", "/api/student/certificates", headers=student_headers)).status_code == 401

    repeated = asyncio.run(
        request(
            "POST",
            "/api/admin/students/accounts/provision",
            headers=admin_headers,
            json={"student_ids": [student.student_id]},
        )
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["created"] == []
    assert repeated.json()["data"]["skipped"][0]["reason"] == "学生账号已开通"
