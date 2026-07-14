from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.certificate import Certificate
from app.schemas.certificate import CertificateListItem
from app.services.certificate_service import PROJECT_ROOT


router = APIRouter(prefix="/certificates")


MOCK_CERTIFICATES = [
    CertificateListItem(
        certificate_id=1,
        certificate_no="CERT-20260714-0001",
        student_id=1,
        student_name="Test Student A",
        batch_id="BATCH-20260714-01",
        template_id="TPL-001",
        pdf_path="mock/certificates/CERT-20260714-0001.pdf",
        certificate_hash="a" * 64,
        qr_code_path="mock/qrcodes/CERT-20260714-0001.png",
        verify_url="http://127.0.0.1:8000/verify/CERT-20260714-0001",
        receipt_id="RCPT-20260714-0001",
        status="VALID",
        credential_type="CERTIFICATE",
        root_id=None,
    ),
    CertificateListItem(
        certificate_id=2,
        certificate_no="CERT-20260714-0002",
        student_id=2,
        student_name="Test Student B",
        batch_id="BATCH-20260714-01",
        template_id="TPL-001",
        pdf_path="mock/certificates/CERT-20260714-0002.pdf",
        certificate_hash="b" * 64,
        qr_code_path="mock/qrcodes/CERT-20260714-0002.png",
        verify_url="http://127.0.0.1:8000/verify/CERT-20260714-0002",
        receipt_id="RCPT-20260714-0002",
        status="REVOKED",
        credential_type="CERTIFICATE",
        root_id=None,
    ),
]


@router.get("", response_model=ApiResponse[list[CertificateListItem]])
def list_certificates() -> ApiResponse[list[CertificateListItem]]:
    return ApiResponse.success(MOCK_CERTIFICATES)


@router.get("/{certificate_no}/download")
def download_certificate(certificate_no: str, db: Session = Depends(get_db)) -> FileResponse:
    """
    按证书编号下载已生成的PDF文件（对应验收演示脚本里"学生端下载某张证书"）。
    这里用certificate_no而不是certificate_id做查询key，跟验真接口保持一致——
    证书编号是对外暴露的标识，内部自增主键不对外用。
    """
    certificate = (
        db.query(Certificate)
        .filter(Certificate.certificate_no == certificate_no)
        .first()
    )
    if certificate is None:
        raise HTTPException(status_code=404, detail=f"证书不存在：{certificate_no}")
    if not certificate.pdf_path:
        raise HTTPException(status_code=404, detail="该证书记录缺少PDF文件路径")

    pdf_path = PROJECT_ROOT / certificate.pdf_path
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="证书文件不存在，可能已被清理")

    return FileResponse(
        path=str(pdf_path),
        filename=f"{certificate_no}.pdf",
        media_type="application/pdf",
    )