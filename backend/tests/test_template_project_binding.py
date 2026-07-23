"""模板绑定项目后的接口一致性测试。"""
import asyncio

import httpx

from app.main import app
from app.models.project import Project
from app.models.student import Student


ADMIN_HEADERS = {"Authorization": "Bearer demo-admin-token"}


async def _request(method: str, path: str, payload: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, json=payload, headers=ADMIN_HEADERS)


def test_template_project_binding_is_validated_and_kept_in_sync(db_session) -> None:
    project = Project(project_name="原项目名", teacher_name="教师", status="ACTIVE")
    other_project = Project(project_name="另一项目", teacher_name="教师", status="ACTIVE")
    db_session.add_all([project, other_project])
    db_session.commit()

    template_response = asyncio.run(
        _request(
            "POST",
            "/api/admin/templates",
            {
                "template_name": "绑定项目模板",
                "institution_name": "示范学院",
                "content_config": {"project_id": project.project_id, "project_name": "伪造名称"},
            },
        )
    )
    assert template_response.status_code == 200
    template = template_response.json()["data"]
    assert template["content_config"]["project_id"] == project.project_id
    assert template["content_config"]["project_name"] == "原项目名"

    mismatch = asyncio.run(
        _request(
            "POST",
            "/api/admin/batches",
            {
                "batch_name": "错误项目批次",
                "project_id": other_project.project_id,
                "template_id": template["template_id"],
                "student_ids": [],
            },
        )
    )
    assert mismatch.status_code == 409

    student = Student(student_no="20260001", student_name="测试学生")
    db_session.add(student)
    db_session.commit()
    batch = asyncio.run(
        _request(
            "POST",
            "/api/admin/batches",
            {
                "batch_name": "正确项目批次",
                "project_id": project.project_id,
                "template_id": template["template_id"],
                "student_ids": [student.student_id],
            },
        )
    ).json()["data"]
    generation_mismatch = asyncio.run(
        _request(
            "POST",
            f"/api/admin/batches/{batch['batch_id']}/generate",
            {"project_id": other_project.project_id, "issue_date": "2026-07-23"},
        )
    )
    assert generation_mismatch.status_code == 409

    renamed = asyncio.run(
        _request("PUT", f"/api/admin/projects/{project.project_id}", {"name": "新项目名"})
    )
    assert renamed.status_code == 200
    templates = asyncio.run(_request("GET", "/api/admin/templates?current=1&size=10"))
    assert templates.json()["data"]["records"][0]["content_config"]["project_name"] == "新项目名"


def test_project_bound_by_template_cannot_be_deleted(db_session) -> None:
    project = Project(project_name="受保护项目", teacher_name="教师", status="ACTIVE")
    db_session.add(project)
    db_session.commit()
    created = asyncio.run(
        _request(
            "POST",
            "/api/admin/templates",
            {"template_name": "受保护模板", "content_config": {"project_id": project.project_id}},
        )
    )
    assert created.status_code == 200

    deleted = asyncio.run(_request("DELETE", f"/api/admin/projects/{project.project_id}"))
    assert deleted.status_code == 409
    assert "证书模板绑定" in deleted.json()["message"]
