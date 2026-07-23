from fastapi import APIRouter

from app.core.responses import ApiResponse
from app.schemas.certificate import CertificateListItem


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
