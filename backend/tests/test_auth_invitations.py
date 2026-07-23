import asyncio

import httpx
from pwdlib import PasswordHash

from app.core.config import settings
from app.main import app
from app.models.user import User


async def request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def create_user(db_session, *, username: str, role: str) -> User:
    user = User(
        username=username,
        display_name=username,
        password_hash=PasswordHash.recommended().hash("long-test-password"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login_headers(username: str) -> dict[str, str]:
    response = asyncio.run(
        request(
            "POST",
            "/api/auth/login",
            json={"username": username, "password": "long-test-password"},
        )
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_invited_teacher_registers_once_and_cannot_manage_accounts(db_session) -> None:
    create_user(db_session, username="owner", role="ADMIN")
    owner_headers = login_headers("owner")

    invitation = asyncio.run(
        request("POST", "/api/admin/invitations", headers=owner_headers, json={"expires_in_hours": 2})
    )
    assert invitation.status_code == 200
    token = invitation.json()["data"]["invitation_token"]

    registration_payload = {
        "invitation_token": token,
        "username": "teammate",
        "display_name": "Teammate",
        "password": "another-long-password",
    }
    registered = asyncio.run(request("POST", "/api/auth/register/invitation", json=registration_payload))
    assert registered.status_code == 200
    teacher_headers = {"Authorization": f"Bearer {registered.json()['data']['token']}"}
    assert asyncio.run(request("GET", "/api/admin/users", headers=teacher_headers)).status_code == 403
    assert asyncio.run(request("POST", "/api/auth/register/invitation", json=registration_payload)).status_code == 400


def test_logout_and_account_disable_revoke_existing_tokens(db_session) -> None:
    owner = create_user(db_session, username="owner2", role="ADMIN")
    teacher = create_user(db_session, username="teacher2", role="TEACHER")
    owner_headers = login_headers(owner.username)
    teacher_headers = login_headers(teacher.username)

    assert asyncio.run(request("POST", "/api/auth/logout", headers=teacher_headers)).status_code == 200
    assert asyncio.run(request("GET", "/api/auth/me", headers=teacher_headers)).status_code == 401

    active_teacher_headers = login_headers(teacher.username)
    disabled = asyncio.run(
        request(
            "PATCH",
            f"/api/admin/users/{teacher.user_id}/status",
            headers=owner_headers,
            json={"is_active": False},
        )
    )
    assert disabled.status_code == 200
    assert asyncio.run(request("GET", "/api/auth/me", headers=active_teacher_headers)).status_code == 401


def test_demo_login_is_disabled_outside_explicit_test_mode(db_session) -> None:
    previous_value = settings.enable_demo_auth
    settings.enable_demo_auth = False
    try:
        response = asyncio.run(
            request("POST", "/api/auth/login", json={"username": "admin", "password": "123456"})
        )
        assert response.status_code == 401
    finally:
        settings.enable_demo_auth = previous_value
