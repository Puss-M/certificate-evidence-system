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
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.models.certificate_template import CertificateTemplate
from app.models.evidence_receipt import EvidenceReceipt
from app.models.revocation_record import RevocationRecord
from app.schemas.verification import VerificationResult
from app.services.certificate_service import PROJECT_ROOT


logger = logging.getLogger(__name__)


INVALID_STATUS_MESSAGES = {
    "REVOKED": "证书已撤销，不再有效。",
    "REISSUED": "旧证书已补发，请查看新证书。",
    "EXPIRED": "证书已过期。",
}


def _find_certificate(db: Session, certificate_no: str) -> Certificate | None:
    return db.query(Certificate).filter(
        Certificate.certificate_no == certificate_no
    ).one_or_none()


def _build_result(
    *,
    result: str,
    certificate_no: str,
    message: str,
    receipt_exists: bool = False,
    hash_match: bool = False,
    **kwargs: object,
) -> VerificationResult:
    return VerificationResult(
        result=result,
        verify_result=result,
        certificate_no=certificate_no,
        message=message,
        verify_message=message,
        receipt_exists=receipt_exists,
        hash_match=hash_match,
        **kwargs,
    )


def _find_receipt(db: Session, certificate: Certificate) -> EvidenceReceipt | None:
    if not certificate.receipt_id:
        return None
    return (
        db.query(EvidenceReceipt)
        .filter(
            EvidenceReceipt.receipt_no == certificate.receipt_id,
            EvidenceReceipt.certificate_id == certificate.certificate_id,
        )
        .one_or_none()
    )


def _stored_file_hash(certificate: Certificate) -> str | None:
    if not certificate.pdf_path:
        return None
    path = Path(certificate.pdf_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.is_file():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _revocation_details(db: Session, certificate: Certificate) -> tuple[str | None, str | None]:
    record = (
        db.query(RevocationRecord)
        .filter(
            RevocationRecord.certificate_id == certificate.certificate_id,
            RevocationRecord.action_type == "REVOKE",
        )
        .order_by(RevocationRecord.revocation_id.desc())
        .first()
    )
    if record is None:
        return None, None
    return record.reason, record.revoked_at.isoformat()


def _common_certificate_fields(db: Session, certificate: Certificate) -> dict[str, object]:
    template = (
        db.get(CertificateTemplate, certificate.template_id)
        if certificate.template_id is not None
        else None
    )
    return {
        "student_name": certificate.student_name,
        "project_name": certificate.project_name,
        "institution_name": certificate.institution_name or (
            template.institution_name if template else None
        ),
        "certificate_hash": certificate.certificate_hash,
        "stored_hash": certificate.certificate_hash,
        "receipt_id": certificate.receipt_id,
        "status": certificate.status,
    }


def verify_by_certificate_no(db: Session, certificate_no: str) -> VerificationResult:
    """编号/扫码验真，同时校验服务端留存 PDF、证书哈希和回执记录。"""
    try:
        certificate = _find_certificate(db, certificate_no)

        if certificate is None:
            return _build_result(
                result="NOT_FOUND",
                certificate_no=certificate_no,
                message="未查询到该证书编号。",
            )

        receipt = _find_receipt(db, certificate)
        receipt_exists = receipt is not None
        stored_file_hash = _stored_file_hash(certificate)
        hash_match = bool(
            certificate.certificate_hash
            and stored_file_hash
            and stored_file_hash == certificate.certificate_hash
            and receipt
            and receipt.certificate_hash == certificate.certificate_hash
        )

        if certificate.status in INVALID_STATUS_MESSAGES:
            revocation_reason, revoked_at = _revocation_details(db, certificate)
            return _build_result(
                result=certificate.status,
                certificate_no=certificate_no,
                message=INVALID_STATUS_MESSAGES[certificate.status],
                receipt_exists=receipt_exists,
                hash_match=hash_match,
                revocation_reason=revocation_reason,
                revoked_at=revoked_at,
                **_common_certificate_fields(db, certificate),
            )

        if not receipt_exists or not certificate.certificate_hash:
            return _build_result(
                result="NO_RECEIPT",
                certificate_no=certificate_no,
                message="证书存在，但未完成存证或回执不存在。",
                hash_match=hash_match,
                **_common_certificate_fields(db, certificate),
            )

        result = "PASS" if hash_match else "HASH_MISMATCH"
        return _build_result(
            result=result,
            certificate_no=certificate_no,
            message=(
                "证书有效，哈希一致，存证回执存在。"
                if hash_match
                else "系统保存的证书文件与存证哈希不一致。"
            ),
            receipt_exists=True,
            hash_match=hash_match,
            **_common_certificate_fields(db, certificate),
        )
    except Exception:
        logger.exception("certificate number verification failed")
        return _build_result(
            result="SYSTEM_ERROR",
            certificate_no=certificate_no,
            message="验真服务暂不可用。",
        )


def verify_by_file(db: Session, certificate_no: str, file_bytes: bytes) -> VerificationResult:
    """强验证：上传PDF复验，现场计算哈希、和存证的 certificate_hash 比对。"""
    try:
        certificate = _find_certificate(db, certificate_no)

        if certificate is None:
            return _build_result(
                result="NOT_FOUND",
                certificate_no=certificate_no,
                message="未查询到该证书编号。",
            )

        receipt = _find_receipt(db, certificate)
        receipt_exists = receipt is not None

        if certificate.status in INVALID_STATUS_MESSAGES:
            revocation_reason, revoked_at = _revocation_details(db, certificate)
            return _build_result(
                result=certificate.status,
                certificate_no=certificate_no,
                message=INVALID_STATUS_MESSAGES[certificate.status],
                receipt_exists=receipt_exists,
                revocation_reason=revocation_reason,
                revoked_at=revoked_at,
                **_common_certificate_fields(db, certificate),
            )

        if not receipt_exists or not certificate.certificate_hash:
            return _build_result(
                result="NO_RECEIPT",
                certificate_no=certificate_no,
                message="证书存在，但未完成存证或回执不存在。",
                **_common_certificate_fields(db, certificate),
            )

        uploaded_hash = hashlib.sha256(file_bytes).hexdigest()
        hash_match = bool(
            uploaded_hash == certificate.certificate_hash
            and receipt
            and receipt.certificate_hash == certificate.certificate_hash
        )

        return _build_result(
            result="PASS" if hash_match else "HASH_MISMATCH",
            certificate_no=certificate_no,
            message=(
                "上传文件哈希与存证版本一致。"
                if hash_match
                else "上传文件与存证版本不一致，可能已被篡改。"
            ),
            receipt_exists=True,
            hash_match=hash_match,
            uploaded_hash=uploaded_hash,
            **_common_certificate_fields(db, certificate),
        )
    except Exception:
        logger.exception("certificate file verification failed")
        return _build_result(
            result="SYSTEM_ERROR",
            certificate_no=certificate_no,
            message="验真服务暂不可用。",
        )
