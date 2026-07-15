from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.certificate import Certificate
from app.models.student import Student
from app.schemas.certificate import CertificateListItem
from app.services.certificate_service import PROJECT_ROOT


router = APIRouter(prefix="/student/certificates")


def _format_date(value) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d")


def _certificate_item(db: Session, certificate: Certificate) -> CertificateListItem:
    student = db.get(Student, certificate.student_id)
    new_certificate = (
        db.query(Certificate)
        .filter(Certificate.previous_certificate_no == certificate.certificate_no)
        .first()
    )
    issue_time = certificate.issue_time or certificate.created_at
    return CertificateListItem(
        certificate_id=certificate.certificate_id,
        certificate_no=certificate.certificate_no,
        student_id=certificate.student_id,
        student_no=student.student_no if student else None,
        student_name=certificate.student_name,
        batch_id=certificate.batch_id,
        template_id=certificate.template_id,
        project_name=certificate.project_name,
        issue_date=_format_date(issue_time),
        issue_time=issue_time.isoformat() if issue_time else None,
        pdf_path=certificate.pdf_path,
        certificate_hash=certificate.certificate_hash,
        qr_code_path=certificate.qr_code_path,
        verify_url=certificate.verify_url,
        receipt_id=certificate.receipt_id,
        status=certificate.status,
        evidence_status="CONFIRMED" if certificate.receipt_id else "PENDING",
        credential_type=certificate.credential_type,
        root_id=certificate.root_id,
        previous_certificate_no=certificate.previous_certificate_no,
        new_certificate_no=new_certificate.certificate_no if new_certificate else None,
    )


def _find_student(db: Session, student_no: str) -> Student:
    student = db.query(Student).filter(Student.student_no == student_no).one_or_none()
    if student is None:
        raise HTTPException(status_code=404, detail="student not found")
    return student


def _find_certificate_for_student(db: Session, certificate_no: str, student_no: str) -> Certificate:
    student = _find_student(db, student_no)
    certificate = (
        db.query(Certificate)
        .filter(
            Certificate.certificate_no == certificate_no,
            Certificate.student_id == student.student_id,
        )
        .one_or_none()
    )
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found for this student")
    return certificate


@router.get("", response_model=ApiResponse[list[CertificateListItem]])
def list_my_certificates(
    student_no: str = Query(..., description="演示版学生身份标识，后续由登录 token 替代"),
    db: Session = Depends(get_db),
) -> ApiResponse[list[CertificateListItem]]:
    student = _find_student(db, student_no)
    certificates = (
        db.query(Certificate)
        .filter(Certificate.student_id == student.student_id)
        .order_by(Certificate.issue_time.desc(), Certificate.certificate_id.desc())
        .all()
    )
    return ApiResponse.success([_certificate_item(db, certificate) for certificate in certificates])


@router.get("/{certificate_no}", response_model=ApiResponse[CertificateListItem])
def get_my_certificate_detail(
    certificate_no: str,
    student_no: str = Query(..., description="演示版学生身份标识，后续由登录 token 替代"),
    db: Session = Depends(get_db),
) -> ApiResponse[CertificateListItem]:
    certificate = _find_certificate_for_student(db, certificate_no, student_no)
    return ApiResponse.success(_certificate_item(db, certificate))


@router.get("/{certificate_no}/download")
def download_my_certificate(
    certificate_no: str,
    student_no: str = Query(..., description="演示版学生身份标识，后续由登录 token 替代"),
    db: Session = Depends(get_db),
) -> FileResponse:
    certificate = _find_certificate_for_student(db, certificate_no, student_no)
    if not certificate.pdf_path:
        raise HTTPException(status_code=404, detail="certificate pdf path is empty")

    pdf_path = PROJECT_ROOT / certificate.pdf_path
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="certificate pdf file not found")

    return FileResponse(
        path=str(pdf_path),
        filename=f"{certificate_no}.pdf",
        media_type="application/pdf",
    )


@router.get("/{certificate_no}/qrcode")
def get_my_certificate_qrcode(
    certificate_no: str,
    student_no: str = Query(..., description="演示版学生身份标识，后续由登录 token 替代"),
    db: Session = Depends(get_db),
) -> FileResponse:
    certificate = _find_certificate_for_student(db, certificate_no, student_no)
    if not certificate.qr_code_path:
        raise HTTPException(status_code=404, detail="certificate qrcode path is empty")

    qr_code_path = PROJECT_ROOT / certificate.qr_code_path
    if not qr_code_path.exists():
        raise HTTPException(status_code=404, detail="certificate qrcode file not found")

    return FileResponse(
        path=str(qr_code_path),
        filename=f"{certificate_no}_qrcode.png",
        media_type="image/png",
    )
