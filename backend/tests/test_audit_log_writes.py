"""
证书生成、验真这两个动作的审计日志埋点测试。

撤销、补发的审计日志是4号在admin.py里写的，已经有他自己的覆盖；这里只测
我们自己负责的这两处：批量生成触发的POST /admin/batches/{id}/generate，
和验真的两个接口（按编号、按上传文件）。
"""
import asyncio
from datetime import datetime

import httpx

from app.main import app
from app.models.audit_log import AuditLog
from app.models.student import Student
from app.services import certificate_service


TEMPLATE = {
    "template_code": "TPL-001",
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}


async def _post_json(path: str, payload: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=payload)


async def _get_json(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def test_generate_batch_writes_audit_log_per_certificate(db_session) -> None:
    student1 = Student(student_no="2023601", student_name="日志测试甲", class_name="1班")
    student2 = Student(student_no="2023602", student_name="日志测试乙", class_name="1班")
    db_session.add_all([student1, student2])
    db_session.commit()

    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "审计日志测试批次", "student_ids": [student1.student_id, student2.student_id]},
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))
    assert generate_resp.json()["data"]["generated_count"] == 2

    logs = db_session.query(AuditLog).filter(AuditLog.action == "证书生成").all()
    assert len(logs) == 2
    for log in logs:
        assert log.target_type == "证书管理"
        assert log.target_id.startswith("CERT-")
        assert str(batch_id) in log.detail


def test_verification_endpoints_write_audit_log(db_session) -> None:
    student = Student(student_no="2023603", student_name="验真日志测试", class_name="1班")
    db_session.add(student)
    db_session.commit()

    certificate = certificate_service.generate_certificate(
        db_session, student_id=student.student_id, template=TEMPLATE, issue_date=datetime(2026, 7, 15)
    )

    # 按编号验真
    asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}"))
    # 按文件上传验真
    pdf_path = certificate_service.PROJECT_ROOT / certificate.pdf_path

    async def _upload() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                f"/api/verification/{certificate.certificate_no}/file",
                files={"file": ("cert.pdf", pdf_path.read_bytes(), "application/pdf")},
            )

    asyncio.run(_upload())

    logs = (
        db_session.query(AuditLog)
        .filter(AuditLog.target_id == certificate.certificate_no, AuditLog.action.like("证书验真%"))
        .all()
    )
    assert len(logs) == 2
    actions = {log.action for log in logs}
    assert actions == {"证书验真-编号", "证书验真-上传文件"}
    assert all("PASS" in log.detail for log in logs)
