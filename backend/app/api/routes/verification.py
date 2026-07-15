import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.schemas.verification import MerkleProofResult, VerificationResult
from app.services import merkle_service, verification_service


router = APIRouter(prefix="/verification")
logger = logging.getLogger(__name__)


def _log_verification(db: Session, certificate_no: str, action: str, result: VerificationResult) -> None:
    """写审计日志埋点，字段风格跟着4号在admin.py里撤销/补发那两处的写法走
    （action中文短句、target_type固定"证书管理"、target_id用certificate_no、
    operator暂时写死"public"——验真是公开接口，还没有登录鉴权，先用这个占位，
    等有真实身份识别后再改）。"""
    try:
        db.add(
            AuditLog(
                action=action,
                target_type="证书管理",
                target_id=certificate_no[:64],
                operator="public",
                detail=f"验真结果：{result.result}",
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("failed to write verification audit log")


@router.get("/{certificate_no}", response_model=ApiResponse[VerificationResult])
def verify_certificate(
    certificate_no: str,
    db: Session = Depends(get_db),
) -> ApiResponse[VerificationResult]:
    """编号/扫码验真（弱验证）：只查证书是否存在、状态、回执是否存在，不校验文件本身。"""
    result = verification_service.verify_by_certificate_no(db, certificate_no)
    _log_verification(db, certificate_no, "证书验真-编号", result)
    return ApiResponse.success(result)


@router.post("/{certificate_no}/file", response_model=ApiResponse[VerificationResult])
async def verify_certificate_by_file(
    certificate_no: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ApiResponse[VerificationResult]:
    """上传PDF复验（强验证）：现场对上传文件计算SHA-256，和存证时记录的
    certificate_hash 比对，这是真正防篡改的一步——仅凭编号查询无法证明
    "手上这份文件没被改过"。"""
    file_bytes = await file.read()
    result = verification_service.verify_by_file(db, certificate_no, file_bytes)
    _log_verification(db, certificate_no, "证书验真-上传文件", result)
    return ApiResponse.success(result)


@router.get("/{certificate_no}/merkle-proof", response_model=ApiResponse[MerkleProofResult])
def get_merkle_proof(
    certificate_no: str,
    db: Session = Depends(get_db),
) -> ApiResponse[MerkleProofResult]:
    """
    Merkle Proof查询（P2加分项，数据库设计.md第9.3节）：给一张证书返回Proof，
    调用方可以自己逐层重算哈希，验证"这张证书确实属于某个已存证批次，内容没有
    被篡改"，不需要拿到批次内其他证书的数据。

    这里只验证"内容完整性"（Proof重算是否等于merkle_root），不判断证书当前是否
    有效——按9.4节要求，有效性要单独看certificate.status（撤销记录），两者是分开
    的两件事，不在这个接口里混着判断。批次还没算过Root时返回404，前端可以据此
    提示"该批次尚未生成Merkle Root"。
    """
    try:
        proof_data = merkle_service.get_merkle_proof(db, certificate_no)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    verified = merkle_service.verify_merkle_proof(
        proof_data["certificate_hash"], proof_data["proof"], proof_data["merkle_root"]
    )
    return ApiResponse.success(MerkleProofResult(**proof_data, verified=verified))
