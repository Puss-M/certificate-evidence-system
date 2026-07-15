"""
证书生成服务的并发冲突重试测试。

certificate_no 和 evidence_receipts.block_height 都是"查当前最大值再+1"，
并发下两个请求可能读到同一个最大值、算出同一个号，数据库的唯一约束会挡住
其中一个（IntegrityError）。generate_certificate() 里加了重试逻辑来应对这种冲突，
这里用 mock 强制制造一次冲突，验证重试确实生效、最终两张证书拿到了不同的编号。
"""
from datetime import datetime
from unittest.mock import patch

from app.models.student import Student
from app.services import certificate_service


TEMPLATE = {
    "template_code": "TPL-001",
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}
ISSUE_DATE = datetime(2026, 7, 14)


def test_build_verify_url_uses_configured_public_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        certificate_service.settings,
        "public_verify_base_url",
        "http://127.0.0.1:8000/api/verification/",
    )

    assert (
        certificate_service._build_verify_url("CERT-20260715-0001")
        == "http://127.0.0.1:8000/api/verification/CERT-20260715-0001"
    )


def test_generate_certificate_retries_on_certificate_no_collision(db_session) -> None:
    student1 = Student(student_no="2023001", student_name="张三", class_name="1班", major_name="软件工程")
    student2 = Student(student_no="2023002", student_name="李四", class_name="1班", major_name="软件工程")
    db_session.add_all([student1, student2])
    db_session.commit()

    cert1 = certificate_service.generate_certificate(
        db_session, student_id=student1.student_id, template=TEMPLATE, issue_date=ISSUE_DATE
    )

    # 模拟并发冲突：让第二次生成时，_next_certificate_no 先返回一个和已存在证书
    # 重复的编号（制造 IntegrityError），第二次调用才返回真实计算出的可用编号。
    real_next_certificate_no = certificate_service._next_certificate_no
    call_count = {"n": 0}

    def colliding_next_certificate_no(db, issue_date):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return cert1.certificate_no
        return real_next_certificate_no(db, issue_date)

    with patch.object(
        certificate_service,
        "_next_certificate_no",
        side_effect=colliding_next_certificate_no,
    ):
        cert2 = certificate_service.generate_certificate(
            db_session, student_id=student2.student_id, template=TEMPLATE, issue_date=ISSUE_DATE
        )

    assert call_count["n"] >= 2, "没有真的触发重试，测试没有实际验证到重试逻辑"
    assert cert2.certificate_no != cert1.certificate_no
    assert cert2.receipt_id is not None

    # 关键回归检查：cert2 第一次尝试时用的是和 cert1 相同的编号（模拟冲突），
    # 如果生成过程中直接用 certificate_no 当文件名，这次失败的重试会把 cert1
    # 真正的PDF/二维码覆盖或删除掉。这里验证 cert1 的文件还在、内容哈希没变，
    # 没有被 cert2 这次冲突重试污染或删掉。
    cert1_pdf_path = certificate_service.PROJECT_ROOT / cert1.pdf_path
    assert cert1_pdf_path.exists(), "cert1 的PDF文件被重试逻辑误删了"
    assert certificate_service._compute_sha256(str(cert1_pdf_path)) == cert1.certificate_hash, (
        "cert1 的PDF内容被cert2的重试覆盖了"
    )


def test_generate_certificate_retries_on_block_height_collision(db_session) -> None:
    student1 = Student(student_no="2023003", student_name="王五", class_name="1班", major_name="软件工程")
    student2 = Student(student_no="2023004", student_name="赵六", class_name="1班", major_name="软件工程")
    db_session.add_all([student1, student2])
    db_session.commit()

    cert1 = certificate_service.generate_certificate(
        db_session, student_id=student1.student_id, template=TEMPLATE, issue_date=ISSUE_DATE
    )
    receipt1_no = cert1.receipt_id

    # 模拟回执 block_height 冲突：让第一次调用 _create_evidence_receipt 时
    # 复用已经存在的 receipt_no，第二次调用才走真实逻辑算出新的 block_height。
    real_create_receipt = certificate_service._create_evidence_receipt
    call_count = {"n": 0}

    def colliding_create_receipt(db, certificate_id, certificate_no, certificate_hash):
        call_count["n"] += 1
        if call_count["n"] == 1:
            from app.models.evidence_receipt import EvidenceReceipt

            duplicate = EvidenceReceipt(
                receipt_no=receipt1_no,  # 故意和已存在的回执撞号
                certificate_id=certificate_id,
                certificate_hash=certificate_hash,
                previous_hash="0" * 64,
                current_block_hash="1" * 64,
                block_height=999,
                evidence_time=datetime.utcnow(),
                chain_type="LOCAL_HASH_CHAIN",
            )
            db.add(duplicate)
            db.flush()
            return duplicate
        return real_create_receipt(db, certificate_id, certificate_no, certificate_hash)

    with patch.object(
        certificate_service,
        "_create_evidence_receipt",
        side_effect=colliding_create_receipt,
    ):
        cert2 = certificate_service.generate_certificate(
            db_session, student_id=student2.student_id, template=TEMPLATE, issue_date=ISSUE_DATE
        )

    assert call_count["n"] >= 2, "没有真的触发重试，测试没有实际验证到重试逻辑"
    assert cert2.receipt_id != receipt1_no
