"""
证书验真服务（对应任务清单 3.3）

替换掉 4号在 api/routes/verification.py 里写的 mock 版本（MOCK_CERTIFICATES 假数据，
HASH_MISMATCH 靠硬编码特殊编号模拟），改成查真实的 certificates / evidence_receipts 表。

两个函数对应两种验证强度：
- verify_by_certificate_no：弱验证，仅按编号查询（扫码/输入编号场景）
- verify_by_file：强验证，上传PDF复验，现场对上传内容算哈希，和数据库里的
  certificate_hash 比对——这是之前讨论过的关键缺口，仅凭编号查询无法证明
  "手上这份文件没被改过"，必须靠这一步。

验真结果覆盖 docs/协作管理/接口规范.md 第8节定义的六种状态：
PASS / REVOKED / HASH_MISMATCH / NOT_FOUND / NO_RECEIPT / SYSTEM_ERROR
"""

import hashlib

from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.schemas.verification import VerificationResult


def _find_certificate(db: Session, certificate_no: str) -> Certificate | None:
    return db.query(Certificate).filter(
        Certificate.certificate_no == certificate_no
    ).one_or_none()


def verify_by_certificate_no(db: Session, certificate_no: str) -> VerificationResult:
    """弱验证：仅按编号查询，不校验文件本身是否被篡改。"""
    try:
        certificate = _find_certificate(db, certificate_no)

        if certificate is None:
            return VerificationResult(
                result="NOT_FOUND",
                certificate_no=certificate_no,
                message="Certificate number does not exist.",
            )

        if certificate.status == "REVOKED":
            return VerificationResult(
                result="REVOKED",
                certificate_no=certificate_no,
                student_name=certificate.student_name,
                certificate_hash=certificate.certificate_hash,
                receipt_id=certificate.receipt_id,
                status=certificate.status,
                message="Certificate has been revoked.",
            )

        if not certificate.receipt_id or not certificate.certificate_hash:
            return VerificationResult(
                result="NO_RECEIPT",
                certificate_no=certificate_no,
                student_name=certificate.student_name,
                status=certificate.status,
                message="Certificate exists but has no evidence receipt yet.",
            )

        return VerificationResult(
            result="PASS",
            certificate_no=certificate_no,
            student_name=certificate.student_name,
            certificate_hash=certificate.certificate_hash,
            receipt_id=certificate.receipt_id,
            status=certificate.status,
            message="Certificate is valid.",
        )
    except Exception as exc:  # 兜底，避免验真接口本身报500把调用方吓一跳
        return VerificationResult(
            result="SYSTEM_ERROR",
            certificate_no=certificate_no,
            message=f"Verification failed: {exc}",
        )


def verify_by_file(db: Session, certificate_no: str, file_bytes: bytes) -> VerificationResult:
    """强验证：上传PDF复验，现场计算哈希、和存证的 certificate_hash 比对。"""
    try:
        certificate = _find_certificate(db, certificate_no)

        if certificate is None:
            return VerificationResult(
                result="NOT_FOUND",
                certificate_no=certificate_no,
                message="Certificate number does not exist.",
            )

        if certificate.status == "REVOKED":
            return VerificationResult(
                result="REVOKED",
                certificate_no=certificate_no,
                student_name=certificate.student_name,
                certificate_hash=certificate.certificate_hash,
                receipt_id=certificate.receipt_id,
                status=certificate.status,
                message="Certificate has been revoked.",
            )

        if not certificate.receipt_id or not certificate.certificate_hash:
            return VerificationResult(
                result="NO_RECEIPT",
                certificate_no=certificate_no,
                student_name=certificate.student_name,
                status=certificate.status,
                message="Certificate exists but has no evidence receipt yet.",
            )

        uploaded_hash = hashlib.sha256(file_bytes).hexdigest()
        hash_match = uploaded_hash == certificate.certificate_hash

        return VerificationResult(
            result="PASS" if hash_match else "HASH_MISMATCH",
            certificate_no=certificate_no,
            student_name=certificate.student_name,
            certificate_hash=certificate.certificate_hash,
            receipt_id=certificate.receipt_id,
            status=certificate.status,
            message=(
                "Uploaded file hash matches stored record."
                if hash_match
                else "Uploaded file hash does not match stored record."
            ),
            hash_match=hash_match,
            uploaded_hash=uploaded_hash,
        )
    except Exception as exc:
        return VerificationResult(
            result="SYSTEM_ERROR",
            certificate_no=certificate_no,
            message=f"Verification failed: {exc}",
        )
