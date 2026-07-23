"""
本次新增的两块功能的测试：
1. POST /api/admin/batches/{id}/generate-with-signature ——批量生成时贴一张
   导师签章图片（4:1裁剪、只在模板配置了mentor_signature字段时接受）。
2. GET /api/admin/templates/{id}/preview ——用真实生成逻辑渲染示例PDF，
   替代前端之前纯CSS画的假预览。

都是照着 test_certificate_batches.py 里 httpx.AsyncClient + demo-admin-token
的既有测试写法来的。
"""
import asyncio
import io
import json

import httpx
from PIL import Image

from app.main import app
from app.models.certificate_template import CertificateTemplate
from app.models.project import Project
from app.models.student import Student
from app.services import template_service


ADMIN_HEADERS = {"Authorization": "Bearer demo-admin-token"}


def _make_signature_bytes(size=(600, 200)) -> bytes:
    img = Image.new("RGB", size, (30, 60, 120))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_template(db_session, *, fields: list[str], project_id: int) -> CertificateTemplate:
    template = CertificateTemplate(
        template_name="签章测试模板",
        template_code="TPL-SIG-TEST",
        institution_name="示范学院",
        content=template_service.serialize_content_config({
            "project_id": project_id,
            "project_name": "签章测试项目",
            "certificate_title": "实训结业证书",
            "content": "该生已完成规定的实训课程，考核合格，特发此证。",
            "issue_year": "2026",
            "fields": fields,
        }),
        status="ACTIVE",
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


async def _post_multipart(path: str, data: dict, files: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, data=data, files=files, headers=ADMIN_HEADERS)


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers=ADMIN_HEADERS)


async def _post_json(path: str, payload: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=payload, headers=ADMIN_HEADERS)


def test_generate_with_signature_rejects_template_without_mentor_signature_field(db_session) -> None:
    project = Project(project_name="项目A", teacher_name="老师", status="ACTIVE")
    db_session.add(project)
    db_session.commit()

    # fields 里没有 mentor_signature
    template = _create_template(db_session, fields=["student_name", "certificate_no"], project_id=project.project_id)

    create_resp = asyncio.run(_post_json("/api/admin/batches", {"template_id": template.template_id}))
    assert create_resp.status_code == 200, create_resp.text
    batch_id = create_resp.json()["data"]["batch_id"]

    resp = asyncio.run(_post_multipart(
        f"/api/admin/batches/{batch_id}/generate-with-signature",
        data={"student_ids": "[]", "issue_date": "2026-07-23"},
        files={"mentor_signature": ("sig.png", _make_signature_bytes(), "image/png")},
    ))
    assert resp.status_code == 422
    # 项目里全局有个自定义异常处理器，把HTTPException.detail包进ApiResponse的
    # message字段里返回（跟所有成功响应统一走ApiResponse.success()的风格一致），
    # 不是FastAPI默认的{"detail": ...}格式。
    assert "导师签章" in resp.json()["message"]


def test_generate_with_signature_crops_to_4_to_1_and_embeds(db_session) -> None:
    project = Project(project_name="项目B", teacher_name="老师", status="ACTIVE")
    db_session.add(project)
    db_session.commit()

    template = _create_template(
        db_session,
        fields=["student_name", "certificate_no", "mentor_signature", "issue_date", "qr_code"],
        project_id=project.project_id,
    )

    student = Student(student_no="S20260900", student_name="签章测试生", class_name="1班", major_name="软件工程")
    db_session.add(student)
    db_session.commit()

    create_resp = asyncio.run(_post_json("/api/admin/batches", {"template_id": template.template_id}))
    batch_id = create_resp.json()["data"]["batch_id"]

    resp = asyncio.run(_post_multipart(
        f"/api/admin/batches/{batch_id}/generate-with-signature",
        data={"student_ids": json.dumps([student.student_id]), "issue_date": "2026-07-23"},
        # 故意传一张不是4:1的图（600x200，比例3:1），验证服务端会自动裁剪
        files={"mentor_signature": ("sig.png", _make_signature_bytes((600, 200)), "image/png")},
    ))
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["generated_count"] == 1
    assert body["failed_count"] == 0


def test_preview_template_renders_real_pdf_and_skips_unselected_fields(db_session) -> None:
    project = Project(project_name="项目C", teacher_name="老师", status="ACTIVE")
    db_session.add(project)
    db_session.commit()

    # 故意只勾选 qr_code：正文、成绩等级、导师签章都不该出现在预览PDF里
    template = _create_template(db_session, fields=["qr_code"], project_id=project.project_id)

    resp = asyncio.run(_get(f"/api/admin/templates/{template.template_id}/preview"))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert len(resp.content) > 500
