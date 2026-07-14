"""
证书生成服务（对应任务清单 3.1 / 3.4）

这是 backend/prototype/certificate_prototype.py、certificate_batch.py 里已经跑通验证过的
证书生成 + 本地哈希链存证逻辑，正式迁移进 app/services/，改成直接读写数据库：

- 证书编号的序号不再由调用方手写，而是查 certificates 表里当天已有的最大编号
- 哈希链的 previous_hash / block_height 不再依赖本地 .local_chain_state.json 文件，
  改成查 evidence_receipts 表里 block_height 最大的一条记录（全局递增，不分批次）
- 每次生成都会往 certificates 表插入一行证书记录、往 evidence_receipts 表插入一行回执记录，
  两者通过 certificate_id（外键）关联，Certificate.receipt_id 存的是回执的业务编号
  （evidence_receipts.receipt_no），不是回执表的自增主键，这一点容易搞混，多留意。

不包含：Merkle Root（P2 加分项，另有方案文档，这里先不接）。
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import func
from sqlalchemy.orm import Session
import qrcode

from app.models.certificate import Certificate
from app.models.evidence_receipt import EvidenceReceipt
from app.models.student import Student


# ---------------------------------------------------------------------------
# 基础配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "certificates"

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

VERIFY_BASE_URL = "https://cert-evidence-system.local/verify"  # 演示用占位域名，部署时替换


# ---------------------------------------------------------------------------
# 证书编号：查数据库里今天已有的最大编号，取下一个序号
# ---------------------------------------------------------------------------
def _next_certificate_no(db: Session, issue_date: datetime) -> str:
    date_str = issue_date.strftime("%Y%m%d")
    prefix = f"CERT-{date_str}-"

    max_no = db.query(func.max(Certificate.certificate_no)).filter(
        Certificate.certificate_no.like(f"{prefix}%")
    ).scalar()

    if max_no is None:
        next_seq = 1
    else:
        next_seq = int(max_no.split("-")[-1]) + 1

    return f"{prefix}{next_seq:04d}"


# ---------------------------------------------------------------------------
# 二维码 + PDF 生成，逻辑和原型脚本完全一致（先出二维码、再画进PDF、最后对成品PDF算哈希）
# ---------------------------------------------------------------------------
def _generate_qrcode(certificate_no: str, output_dir: Path) -> tuple[str, str]:
    verify_url = f"{VERIFY_BASE_URL}/{certificate_no}"
    qr_path = output_dir / f"{certificate_no}_qrcode.png"
    img = qrcode.make(verify_url)
    img.save(qr_path)
    return str(qr_path), verify_url


def _generate_pdf(certificate_no: str, student: Student, template: dict,
                   issue_date: datetime, qr_code_path: str, output_dir: Path) -> str:
    pdf_path = output_dir / f"{certificate_no}.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    c.setFont("STSong-Light", 26)
    c.drawCentredString(width / 2, height - 130, "结 业 证 书")

    c.setFont("STSong-Light", 13)
    lines = [
        f"姓名：{student.student_name}　　学号：{student.student_no}",
        "",
        f"经考核，已完成「{template['project_name']}」全部课程内容，",
        f"成绩等级：{template['grade_level']}，特发此证。",
        "",
        f"颁发机构：{template['institution_name']}",
        f"证书编号：{certificate_no}",
        f"颁发日期：{issue_date.strftime('%Y年%m月%d日')}",
    ]
    y = height - 210
    for line in lines:
        c.drawCentredString(width / 2, y, line)
        y -= 28

    qr_size = 62
    c.drawImage(
        qr_code_path,
        width - qr_size - 60,
        50,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.setFont("STSong-Light", 8)
    c.drawCentredString(width - qr_size / 2 - 60, 40, "扫码验真")

    c.setFont("STSong-Light", 8)
    c.drawString(60, 66, "本证书内容哈希已写入本地存证链。")
    c.drawString(60, 52, "（模拟数据，仅用于课程实训演示）")

    c.showPage()
    c.save()
    return str(pdf_path)


def _compute_sha256(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# 本地哈希链回执：查数据库里 block_height 最大的一条记录作为"上一条"，
# 不再依赖本地文件。这样多个请求/多个部署实例并发生成证书时，
# 链的顺序由数据库保证，不会因为本地文件不同步而错乱。
# ---------------------------------------------------------------------------
def _create_evidence_receipt(db: Session, certificate_id: int, certificate_no: str,
                              certificate_hash: str) -> EvidenceReceipt:
    last_receipt = db.query(EvidenceReceipt).order_by(
        EvidenceReceipt.block_height.desc()
    ).first()

    if last_receipt is None:
        previous_hash = "0" * 64
        block_height = 1
    else:
        previous_hash = last_receipt.current_block_hash
        block_height = last_receipt.block_height + 1

    evidence_time = datetime.utcnow()
    evidence_time_str = evidence_time.strftime("%Y-%m-%d %H:%M:%S")

    raw = f"{block_height}{certificate_no}{certificate_hash}{previous_hash}{evidence_time_str}"
    current_block_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    receipt_no = f"RCP-{evidence_time.strftime('%Y%m%d')}-{block_height:04d}"

    receipt = EvidenceReceipt(
        receipt_no=receipt_no,
        certificate_id=certificate_id,
        certificate_hash=certificate_hash,
        previous_hash=previous_hash,
        current_block_hash=current_block_hash,
        block_height=block_height,
        evidence_time=evidence_time,
        chain_type="LOCAL_HASH_CHAIN",
    )
    db.add(receipt)
    db.flush()
    return receipt


# ---------------------------------------------------------------------------
# 单张证书生成的完整流程：编号 -> 二维码 -> PDF -> 哈希 -> 存证回执 -> 写入数据库
# ---------------------------------------------------------------------------
def generate_certificate(
    db: Session,
    *,
    student_id: int,
    template: dict,
    issue_date: datetime,
    batch_id: str | None = None,
    output_dir: Path | None = None,
) -> Certificate:
    student = db.get(Student, student_id)
    if student is None:
        raise ValueError(f"student_id={student_id} 不存在，请先确认学生数据已导入")

    target_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(target_dir, exist_ok=True)

    certificate_no = _next_certificate_no(db, issue_date)

    qr_code_path, verify_url = _generate_qrcode(certificate_no, target_dir)
    pdf_path = _generate_pdf(certificate_no, student, template, issue_date, qr_code_path, target_dir)
    certificate_hash = _compute_sha256(pdf_path)

    certificate = Certificate(
        certificate_no=certificate_no,
        student_id=student.student_id,
        student_name=student.student_name,
        batch_id=batch_id,
        template_id=template.get("template_code"),
        pdf_path=os.path.relpath(pdf_path, start=PROJECT_ROOT),
        certificate_hash=certificate_hash,
        qr_code_path=os.path.relpath(qr_code_path, start=PROJECT_ROOT),
        verify_url=verify_url,
        status="VALID",
        credential_type="CERTIFICATE",
    )
    db.add(certificate)
    db.flush()  # 拿到 certificate.certificate_id，供回执表外键关联

    receipt = _create_evidence_receipt(db, certificate.certificate_id, certificate_no, certificate_hash)
    certificate.receipt_id = receipt.receipt_no  # 存的是回执业务编号，不是回执表自增主键

    db.commit()
    db.refresh(certificate)
    return certificate


# ---------------------------------------------------------------------------
# 批量生成：对一批 student_id 依次调用 generate_certificate，
# 每张证书仍然各自完整走一遍流程，哈希链在数据库层面保持全局递增、逐条相连。
# ---------------------------------------------------------------------------
def generate_certificate_batch(
    db: Session,
    *,
    student_ids: list[int],
    template: dict,
    issue_date: datetime,
    batch_id: str,
    output_dir: Path | None = None,
) -> list[Certificate]:
    return [
        generate_certificate(
            db,
            student_id=student_id,
            template=template,
            issue_date=issue_date,
            batch_id=batch_id,
            output_dir=output_dir,
        )
        for student_id in student_ids
    ]
