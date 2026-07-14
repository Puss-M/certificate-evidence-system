"""
批次创建/查询/触发生成接口测试（POST /api/admin/batches、
GET /api/admin/batches、POST /api/admin/batches/{batch_id}/generate）。

覆盖：建批次时传student_ids会存下来、查批次列表（含实时统计的generated/evidenced）、
触发生成成功场景（不需要请求体，用建批次时存的student_ids）、批次不存在报404、
批次里某个student_id不存在不影响其他人生成。
"""
import asyncio

import httpx

from app.main import app
from app.models.student import Student


async def _post_json(path: str, payload: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=payload)


async def _get_json(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


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
    batches = list_resp.json()["data"]
    assert len(batches) == 1
    assert batches[0]["batch_id"] == created["batch_id"]


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

    detail = asyncio.run(_get_json("/api/admin/batches")).json()["data"][0]
    assert detail["generated"] == 2
    assert detail["evidenced"] == 2  # 当前设计里生成和存证是原子完成的，见certificate_service.py注释
    assert detail["status"] == "GENERATED"


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
