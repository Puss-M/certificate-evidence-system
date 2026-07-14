from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.responses import ApiResponse
from app.db.session import get_db
from app.schemas.verification import VerificationResult
from app.services import verification_service


router = APIRouter(prefix="/verification")


@router.get("/{certificate_no}", response_model=ApiResponse[VerificationResult])
def verify_certificate(
    certificate_no: str,
    db: Session = Depends(get_db),
) -> ApiResponse[VerificationResult]:
    """编号/扫码验真（弱验证）：只查证书是否存在、状态、回执是否存在，不校验文件本身。"""
    result = verification_service.verify_by_certificate_no(db, certificate_no)
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
    return ApiResponse.success(result)
