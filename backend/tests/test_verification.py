"""
验真接口测试（对应任务清单 3.3）。

原本 tests/test_mock_endpoints.py 里有两条针对 /api/verification 的测试，
但那时接口还是mock数据；现在换成真实数据库读写了，挪到这个独立文件，
用 conftest.py 里的 db_session fixture 造真实数据，覆盖编号验真、上传PDF复验
两种场景，以及 PASS / HASH_MISMATCH / NOT_FOUND / REVOKED 四种可以在单元测试
里真实触发的结果（NO_RECEIPT、SYSTEM_ERROR 暂时没有能自然触发的场景，服务层
的分支逻辑已经在 backend/prototype/_smoke_test_services.py 里手动验证过）。
"""
import asyncio
from datetime import datetime

import httpx

from app.main import app
from app.models.evidence_receipt import EvidenceReceipt
from app.models.revocation_record import RevocationRecord
from app.models.student import Student
from app.services import certificate_service


TEMPLATE = {
    "template_code": "TPL-001",
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}


def _seed_certificate(db_session):
    student = Student(
        student_no="2023001",
        student_name="张三",
        class_name="1班",
        major_name="软件工程",
    )
    db_session.add(student)
    db_session.commit()

    return certificate_service.generate_certificate(
        db_session,
        student_id=student.student_id,
        template=TEMPLATE,
        issue_date=datetime(2026, 7, 14),
    )


async def _get_json(path: str) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)
    assert response.status_code == 200
    return response.json()


async def _post_file(path: str, filename: str, content: bytes) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            path,
            files={"file": (filename, content, "application/pdf")},
        )
    assert response.status_code == 200
    return response.json()


def test_verify_by_certificate_no_returns_pass(db_session) -> None:
    certificate = _seed_certificate(db_session)

    data = asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}"))

    assert data["code"] == 0
    assert data["data"]["result"] == "PASS"
    assert data["data"]["verify_result"] == "PASS"
    assert data["data"]["receipt_exists"] is True
    assert data["data"]["hash_match"] is True
    assert data["data"]["certificate_hash"] == certificate.certificate_hash
    assert data["data"]["stored_hash"] == certificate.certificate_hash
    assert data["data"]["institution_name"] == TEMPLATE["institution_name"]
    assert data["data"]["verify_message"] == data["data"]["message"]


def test_verify_by_certificate_no_returns_not_found(db_session) -> None:
    data = asyncio.run(_get_json("/api/verification/CERT-NOT-EXIST"))

    assert data["data"]["result"] == "NOT_FOUND"
    assert data["data"]["receipt_exists"] is False
    assert data["data"]["hash_match"] is False


def test_verify_by_file_returns_pass_on_original_file(db_session) -> None:
    certificate = _seed_certificate(db_session)
    pdf_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    content = pdf_path.read_bytes()

    data = asyncio.run(
        _post_file(f"/api/verification/{certificate.certificate_no}/file", "cert.pdf", content)
    )

    assert data["data"]["result"] == "PASS"
    assert data["data"]["verify_result"] == "PASS"
    assert data["data"]["receipt_exists"] is True
    assert data["data"]["hash_match"] is True
    assert data["data"]["uploaded_hash"] == certificate.certificate_hash
    assert data["data"]["stored_hash"] == certificate.certificate_hash


def test_verify_by_file_returns_hash_mismatch_on_tampered_file(db_session) -> None:
    certificate = _seed_certificate(db_session)
    pdf_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    tampered = bytearray(pdf_path.read_bytes())
    tampered[-1] ^= 0xFF

    data = asyncio.run(
        _post_file(f"/api/verification/{certificate.certificate_no}/file", "cert.pdf", bytes(tampered))
    )

    assert data["data"]["result"] == "HASH_MISMATCH"
    assert data["data"]["hash_match"] is False
    assert data["data"]["uploaded_hash"] != certificate.certificate_hash


def test_verify_rejects_receipt_hash_mismatch(db_session) -> None:
    certificate = _seed_certificate(db_session)
    receipt = (
        db_session.query(EvidenceReceipt)
        .filter(EvidenceReceipt.receipt_no == certificate.receipt_id)
        .one()
    )
    receipt.certificate_hash = "0" * 64
    db_session.commit()

    data = asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}"))

    assert data["data"]["receipt_exists"] is True
    assert data["data"]["hash_match"] is False
    assert data["data"]["verify_result"] == "HASH_MISMATCH"


def test_verify_by_certificate_no_returns_no_receipt(db_session) -> None:
    certificate = _seed_certificate(db_session)
    certificate.receipt_id = None
    db_session.commit()

    data = asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}"))

    assert data["data"]["result"] == "NO_RECEIPT"
    assert data["data"]["receipt_exists"] is False
    assert data["data"]["hash_match"] is False


def test_verify_returns_revoked_for_both_endpoints(db_session) -> None:
    certificate = _seed_certificate(db_session)
    certificate.status = "REVOKED"
    db_session.add(
        RevocationRecord(
            certificate_id=certificate.certificate_id,
            action_type="REVOKE",
            reason="证书信息有误",
            operator="admin",
        )
    )
    db_session.commit()

    by_no = asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}"))
    assert by_no["data"]["result"] == "REVOKED"
    assert by_no["data"]["revocation_reason"] == "证书信息有误"
    assert by_no["data"]["revoked_at"] is not None

    pdf_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    by_file = asyncio.run(
        _post_file(
            f"/api/verification/{certificate.certificate_no}/file",
            "cert.pdf",
            pdf_path.read_bytes(),
        )
    )
    assert by_file["data"]["result"] == "REVOKED"


def test_verify_returns_reissued_for_both_endpoints(db_session) -> None:
    certificate = _seed_certificate(db_session)
    certificate.status = "REISSUED"
    db_session.commit()

    by_no = asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}"))
    assert by_no["data"]["result"] == "REISSUED"
    assert by_no["data"]["verify_message"] == "旧证书已补发，请查看新证书。"

    pdf_path = certificate_service.PROJECT_ROOT / certificate.pdf_path
    by_file = asyncio.run(
        _post_file(
            f"/api/verification/{certificate.certificate_no}/file",
            "cert.pdf",
            pdf_path.read_bytes(),
        )
    )
    assert by_file["data"]["result"] == "REISSUED"
