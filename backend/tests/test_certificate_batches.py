"""
批次创建/查询/触发生成接口测试（POST /api/admin/batches、
GET /api/admin/batches、POST /api/admin/batches/{batch_id}/generate）。

覆盖：建批次时传student_ids会存下来、查批次列表（含实时统计的generated/evidenced）、
触发生成成功场景（不需要请求体，用建批次时存的student_ids）、批次不存在报404、
批次里某个student_id不存在不影响其他人生成。
"""
import asyncio

import httpx

from app.api.routes.certificate_batches import _load_template_dict
from app.main import app
from app.models.certificate import Certificate
from app.models.certificate_template import CertificateTemplate
from app.models.project import Project
from app.models.student import Student


async def _post_json(
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    if headers is None:
        headers = {"Authorization": "Bearer demo-admin-token"}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=payload, headers=headers)


async def _get_json(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers={"Authorization": "Bearer demo-admin-token"})


async def _put_json(path: str, payload: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.put(
            path,
            json=payload,
            headers={"Authorization": "Bearer demo-admin-token"},
        )


async def _delete_json(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.delete(path, headers={"Authorization": "Bearer demo-admin-token"})


def test_batch_routes_require_write_role(db_session) -> None:
    payload = {"batch_name": "权限测试批次", "student_ids": []}

    unauthenticated = asyncio.run(_post_json("/api/admin/batches", payload, headers={}))
    auditor = asyncio.run(
        _post_json(
            "/api/admin/batches",
            payload,
            headers={"Authorization": "Bearer demo-auditor-token"},
        )
    )
    teacher = asyncio.run(
        _post_json(
            "/api/admin/batches",
            payload,
            headers={"Authorization": "Bearer demo-teacher-token"},
        )
    )

    assert unauthenticated.status_code == 401
    assert auditor.status_code == 403
    assert teacher.status_code == 200


def test_create_batch_stores_student_ids(db_session) -> None:
    student1 = Student(student_no="2023401", student_name="小明", class_name="1班")
    student2 = Student(student_no="2023402", student_name="小红", class_name="1班")
    db_session.add_all([student1, student2])
    db_session.commit()

    create_resp = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {
                "batch_name": "2026暑期实训第一批",
                "project_name": "软件开发实训",
                "student_ids": [student1.student_id, student2.student_id],
            },
        )
    )
    assert create_resp.status_code == 200
    created = create_resp.json()["data"]
    assert created["batch_name"] == "2026暑期实训第一批"
    assert created["student_count"] == 2
    assert created["generated"] == 0
    assert created["status"] == "DRAFT"

    list_resp = asyncio.run(_get_json("/api/admin/batches"))
    assert list_resp.status_code == 200
    page = list_resp.json()["data"]
    assert page["total"] == 1
    assert page["current"] == 1
    assert page["size"] == 10
    assert page["records"][0]["batch_id"] == created["batch_id"]

    page_resp = asyncio.run(_get_json("/api/admin/batches?current=1&size=10"))
    assert page_resp.status_code == 200
    page = page_resp.json()["data"]
    assert page["total"] == 1
    assert page["records"][0]["batch_id"] == created["batch_id"]


def test_update_and_delete_batch_match_frontend_routes(db_session) -> None:
    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "old name", "project_name": "old project", "student_ids": []},
        )
    ).json()["data"]["batch_id"]

    update_resp = asyncio.run(
        _put_json(
            f"/api/admin/batches/{batch_id}",
            {"batch_name": "new name", "project_name": "new project", "status": "IMPORTED"},
        )
    )

    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["batch_name"] == "new name"
    assert updated["project_name"] == "new project"
    assert updated["status"] == "IMPORTED"

    delete_resp = asyncio.run(_delete_json(f"/api/admin/batches/{batch_id}"))
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["deleted"] is True


def test_delete_batch_with_generated_certificates_returns_conflict(db_session) -> None:
    student = Student(student_no="2023411", student_name="protected batch student")
    db_session.add(student)
    db_session.commit()
    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "protected batch", "student_ids": [student.student_id]},
        )
    ).json()["data"]["batch_id"]
    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))
    assert generate_resp.status_code == 200

    delete_resp = asyncio.run(_delete_json(f"/api/admin/batches/{batch_id}"))

    assert delete_resp.status_code == 409
    assert "证书" in delete_resp.json()["message"]


def test_generate_batch_rejects_template_id_that_does_not_exist(db_session) -> None:
    student = Student(student_no="2023412", student_name="missing template student")
    db_session.add(student)
    db_session.commit()
    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {
                "batch_name": "missing template batch",
                "template_id": 999999,
                "student_ids": [student.student_id],
            },
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))

    assert generate_resp.status_code == 404
    assert "template_id=999999" in generate_resp.json()["message"]
    assert db_session.query(Certificate).count() == 0


def test_generate_batch_creates_certificate_for_each_stored_student(db_session) -> None:
    student1 = Student(student_no="2023403", student_name="小刚", class_name="1班")
    student2 = Student(student_no="2023404", student_name="小丽", class_name="1班")
    db_session.add_all([student1, student2])
    db_session.commit()

    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "测试批次", "student_ids": [student1.student_id, student2.student_id]},
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))

    assert generate_resp.status_code == 200
    result = generate_resp.json()["data"]
    assert result["batch_id"] == batch_id
    assert result["generated_count"] == 2
    assert result["failed_count"] == 0

    detail = asyncio.run(_get_json("/api/admin/batches")).json()["data"]["records"][0]
    assert detail["generated"] == 2
    assert detail["evidenced"] == 2  # 当前设计里生成和存证是原子完成的，见certificate_service.py注释
    assert detail["status"] == "GENERATED"


def test_generate_batch_accepts_frontend_student_ids_body(db_session) -> None:
    student = Student(student_no="2023410", student_name="frontend user", class_name="1")
    template = CertificateTemplate(
        template_name="frontend selected template",
        template_code="TPL-FRONTEND-SELECTED",
        institution_name="计算机学院",
        content='{"project_name":"证书存证项目","grade_level":"优秀"}',
        status="ACTIVE",
    )
    db_session.add_all([student, template])
    db_session.commit()

    generation_template = _load_template_dict(db_session, template.template_id)
    assert generation_template["institution_name"] == "计算机学院"
    assert generation_template["project_name"] == "证书存证项目"
    assert generation_template["grade_level"] == "优秀"

    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "frontend selected students", "student_ids": []},
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(
        _post_json(
            f"/api/admin/batches/{batch_id}/generate",
            {
                "template_id": template.template_id,
                "student_ids": [student.student_id],
                "issue_date": "2026-07-14",
            },
        )
    )

    assert generate_resp.status_code == 200
    result = generate_resp.json()["data"]
    assert result["generated_count"] == 1
    assert result["failed_count"] == 0

    evidence_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/evidence"))
    assert evidence_resp.status_code == 200
    evidence_data = evidence_resp.json()["data"]
    assert evidence_data["success_count"] == 1
    assert len(evidence_data["receipt_ids"]) == 1
    assert evidence_data["evidenced"] == 1
    assert evidence_data["newly_evidenced"] == 0


def test_generate_batch_uses_selected_persisted_project(db_session) -> None:
    student = Student(student_no="2023499", student_name="Project Student")
    project = Project(
        project_name="Selected Project",
        teacher_name="Project Teacher",
        status="ACTIVE",
    )
    template = CertificateTemplate(
        template_name="Project Template",
        template_code="TPL-PROJECT-SELECTED",
        institution_name="Project Institution",
        content='{"project_name":"Template Default Project"}',
        status="ACTIVE",
    )
    db_session.add_all([student, project, template])
    db_session.commit()

    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "Project Batch", "student_ids": []},
        )
    ).json()["data"]["batch_id"]

    response = asyncio.run(
        _post_json(
            f"/api/admin/batches/{batch_id}/generate",
            {
                "project_id": project.project_id,
                "template_id": template.template_id,
                "student_ids": [student.student_id],
                "issue_date": "2026-07-17",
            },
        )
    )

    assert response.status_code == 200
    certificate = db_session.query(Certificate).one()
    assert certificate.project_name == "Selected Project"
    assert certificate.institution_name == "Project Institution"

    batch_list = asyncio.run(_get_json("/api/admin/batches"))
    batch_data = batch_list.json()["data"]["records"][0]
    assert batch_data["project_id"] == project.project_id
    assert batch_data["project_name"] == "Selected Project"


def test_generate_batch_reports_failure_for_missing_student_without_blocking_others(db_session) -> None:
    student = Student(student_no="2023405", student_name="小强", class_name="1班")
    db_session.add(student)
    db_session.commit()

    non_existent_student_id = 999999
    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "测试批次2", "student_ids": [student.student_id, non_existent_student_id]},
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))

    result = generate_resp.json()["data"]
    assert result["generated_count"] == 1
    assert result["failed_count"] == 1
    assert result["failures"][0]["student_id"] == non_existent_student_id


def test_generate_batch_returns_404_for_unknown_batch(db_session) -> None:
    response = asyncio.run(_post_json("/api/admin/batches/99999/generate"))
    assert response.status_code == 404
