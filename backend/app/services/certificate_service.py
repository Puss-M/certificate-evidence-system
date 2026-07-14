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
- 证书编号、回执的 block_height 都是"先查最大值再+1"，并发下两个请求可能读到同一个
  最大值、算出同一个编号——这种情况数据库的唯一约束会挡住其中一个，报 IntegrityError，
  不会导致编号重复或哈希链错乱。generate_certificate() 会在这种冲突下自动重试。

不包含：Merkle Root（P2 加分项，另有方案文档，这里先不接）。
"""

import hashlib
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
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

# 证书编号 / 回执 block_height 是"查最大值+1"，并发冲突时靠重试解决，这是重试上限
MAX_GENERATE_ATTEMPTS = 5


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
# 二维码 + PDF 生成。这两个函数现在只管"往指定路径写文件"，具体用什么文件名
# 由调用方（generate_certificate）决定——生成阶段用临时文件名，落库成功后
# 才改名成正式的 {certificate_no} 文件名，原因见 generate_certificate 里的注释。
# ---------------------------------------------------------------------------
def _generate_qrcode(verify_url: str, qr_path: Path) -> None:
    img = qrcode.make(verify_url)
    img.save(qr_path)


def _generate_pdf(certificate_no: str, student: Student, template: dict,
                   issue_date: datetime, qr_code_path: Path, pdf_path: Path) -> None:
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
        str(qr_code_path),
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


def _compute_sha256(file_path: str) -> str:
    last_error: PermissionError | None = None
    for _ in range(10):
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to compute SHA-256 for {file_path}")


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

    last_error: IntegrityError | None = None

    for _ in range(MAX_GENERATE_ATTEMPTS):
        certificate_no = _next_certificate_no(db, issue_date)
        verify_url = f"{VERIFY_BASE_URL}/{certificate_no}"

        # 先写到跟 certificate_no 无关的临时文件名，落库成功后才改名成正式的
        # {certificate_no} 文件名。这一点很关键：如果直接用 certificate_no 当
        # 文件名生成，一旦这次因为并发冲突要重试，这次生成的文件会和"已经赢了
        # 这个编号"的那次证书同名，重试时的 PDF 内容会把对方的文件覆盖掉，
        # 失败后再删除又会把对方刚生成好的文件一起删掉——用临时文件名可以完全
        # 避免这种"重试把别人的证书文件冲掉"的情况。
        temp_token = uuid.uuid4().hex[:8]
        temp_qr_path = target_dir / f".tmp-{temp_token}-qrcode.png"
        temp_pdf_path = target_dir / f".tmp-{temp_token}.pdf"

        _generate_qrcode(verify_url, temp_qr_path)
        _generate_pdf(certificate_no, student, template, issue_date, temp_qr_path, temp_pdf_path)
        certificate_hash = _compute_sha256(str(temp_pdf_path))

        final_qr_path = target_dir / f"{certificate_no}_qrcode.png"
        final_pdf_path = target_dir / f"{certificate_no}.pdf"

        certificate = Certificate(
            certificate_no=certificate_no,
            student_id=student.student_id,
            student_name=student.student_name,
            batch_id=batch_id,
            template_id=template.get("template_code"),
            pdf_path=os.path.relpath(final_pdf_path, start=PROJECT_ROOT),
            certificate_hash=certificate_hash,
            qr_code_path=os.path.relpath(final_qr_path, start=PROJECT_ROOT),
            verify_url=verify_url,
            status="VALID",
            credential_type="CERTIFICATE",
        )

        try:
            db.add(certificate)
            db.flush()  # 拿到 certificate.certificate_id，供回执表外键关联

            receipt = _create_evidence_receipt(db, certificate.certificate_id, certificate_no, certificate_hash)
            certificate.receipt_id = receipt.receipt_no  # 存的是回执业务编号，不是回执表自增主键

            db.commit()
            db.refresh(certificate)

            # 落库成功、编号确定不会再跟别人冲突之后，才把临时文件改名成正式文件名。
            # 这里用 replace 而不是 rename：测试或演示环境经常会清空数据库但保留
            # outputs/certificates 目录，导致同一个 certificate_no 的旧文件仍在磁盘上。
            # 数据库唯一约束已经保证当前编号归这次成功生成所有，因此可以安全覆盖这种
            # 没有数据库记录引用的陈旧产物。
            temp_pdf_path.replace(final_pdf_path)
            temp_qr_path.replace(final_qr_path)

            return certificate
        except IntegrityError as exc:
            # 并发下两个请求可能算出同一个 certificate_no 或同一个 block_height，
            # 数据库唯一约束会挡住其中一个——回滚、丢掉这次生成的临时文件，换个号重试。
            db.rollback()
            last_error = exc
            for stray_path in (temp_pdf_path, temp_qr_path):
                try:
                    stray_path.unlink(missing_ok=True)
                except OSError:
                    pass  # 清理失败不影响重试，最多留一份没被数据库引用的临时文件

    raise RuntimeError(
        f"生成证书失败：并发冲突重试 {MAX_GENERATE_ATTEMPTS} 次仍未成功"
    ) from last_error


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
