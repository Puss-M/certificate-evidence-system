from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.certificate import Certificate, CertificateStatus
from app.models.certificate_batch import CertificateBatch
from app.models.certificate_template import CertificateTemplate
from app.models.evidence_receipt import EvidenceReceipt
from app.models.revocation_record import RevocationRecord
from app.models.student import Student
from app.services import certificate_service


router = APIRouter(prefix="/admin")


DEMO_PROJECTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "2026暑期软件开发实训",
        "teacher": "实训教师",
        "start_date": "2026-07-01",
        "end_date": "2026-07-14",
        "status": "ACTIVE",
    }
]

DEMO_STUDENTS: list[dict[str, Any]] = [
    {
        "student_id": 1,
        "student_no": "S20260001",
        "student_name": "Demo Student A",
        "college": "Demo College",
        "major": "Software Engineering",
        "class_name": "Class 1",
    },
    {
        "student_id": 2,
        "student_no": "S20260002",
        "student_name": "Demo Student B",
        "college": "Demo College",
        "major": "Computer Science",
        "class_name": "Class 1",
    },
]

DEMO_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": 1,
        "name": "暑期实训结业证书",
        "issuer": "示范学院",
        "course_name": "软件开发综合实训",
        "project_name": "2026暑期软件开发实训",
        "certificate_title": "实训结业证书",
        "content": "该生已完成规定的实训课程，考核合格，特发此证。",
        "issue_year": "2026",
        "fields": ["student_name", "certificate_no", "issue_date", "qr_code"],
        "enabled": True,
        "updated_at": "2026-07-14 00:00:00",
    }
]

DEMO_BATCHES: list[dict[str, Any]] = [
    {
        "batch_id": 1,
        "batch_no": "BATCH-202607-001",
        "batch_name": "2026暑期实训第一批",
        "project_name": "2026暑期软件开发实训",
        "template_id": 1,
        "student_count": 2,
        "generated": 0,
        "evidenced": 0,
        "status": "DRAFT",
    }
]

DEMO_CERTIFICATES: list[dict[str, Any]] = [
    {
        "certificate_id": 1,
        "certificate_no": "CERT-20260714-0001",
        "student_id": 1,
        "student_no": "S20260001",
        "student_name": "Demo Student A",
        "batch_id": 1,
        "template_id": 1,
        "pdf_path": "/mock/certificates/CERT-20260714-0001.pdf",
        "certificate_hash": "a" * 64,
        "qr_code_path": "/mock/qrcodes/CERT-20260714-0001.png",
        "verify_url": "/public/verify/CERT-20260714-0001",
        "receipt_id": "RCP-20260714-0001",
        "status": "VALID",
        "credential_type": "CERTIFICATE",
        "root_id": "",
        "project_name": "2026暑期软件开发实训",
        "issue_date": "2026-07-14",
        "evidence_status": "CONFIRMED",
        "previous_certificate_no": None,
        "new_certificate_no": None,
    }
]

DEMO_RECEIPTS: list[dict[str, Any]] = [
    {
        "receipt_id": "RCP-20260714-0001",
        "certificate_id": 1,
        "certificate_no": "CERT-20260714-0001",
        "certificate_hash": "a" * 64,
        "evidence_type": "LOCAL_HASH_CHAIN",
        "previous_hash": "0" * 64,
        "current_block_hash": "b" * 64,
        "block_height": 1,
        "tx_hash": None,
        "contract_address": None,
        "evidence_time": "2026-07-14 00:00:00",
        "status": "CONFIRMED",
    }
]

DEMO_AUDIT_LOGS: list[dict[str, Any]] = [
    {
        "id": 1,
        "operator": "admin",
        "action": "证书接口联调",
        "module": "可信存证",
        "target": "CERT-20260714-0001",
        "detail": "管理员前端接口联调记录",
        "result": "SUCCESS",
        "created_at": "2026-07-14 00:00:00",
        "createdAt": "2026-07-14 00:00:00",
    }
]


class StudentPayload(BaseModel):
    student_no: str | None = None
    student_name: str | None = None
    college: str | None = Field(default=None, max_length=100)
    major: str | None = None
    major_name: str | None = None
    class_name: str | None = None
    phone: str | None = None


class TemplatePayload(BaseModel):
    template_name: str | None = None
    name: str | None = None
    institution_name: str | None = None
    content_config: dict[str, Any] | None = None
    status: str | None = None


class BatchPayload(BaseModel):
    batch_name: str | None = None
    batch_no: str | None = None
    project_name: str | None = None
    template_id: int | None = None
    status: str | None = None


class IssuePayload(BaseModel):
    project_id: int | None = None
    template_id: int | None = None
    batch_id: int | None = None
    student_ids: list[int] = []
    issue_date: str | None = None


class RevokePayload(BaseModel):
    reason: str = "管理员撤销证书"


class ReissuePayload(BaseModel):
    reason: str = "管理员补发证书"
    issue_date: str | None = None


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def _parse_issue_date(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="issue_date must be YYYY-MM-DD") from exc


def _page(records: list[dict[str, Any]], current: int = 1, size: int = 10,
          keyword: str | None = None, status: str | None = None) -> dict[str, Any]:
    current = max(int(current or 1), 1)
    size = max(int(size or 10), 1)
    keyword_text = (keyword or "").lower()
    status_text = status or ""

    def matches(record: dict[str, Any]) -> bool:
        if keyword_text and keyword_text not in str(record).lower():
            return False
        row_status = str(record.get("status") or record.get("result") or "")
        if not row_status and "enabled" in record:
            row_status = "ENABLED" if record["enabled"] else "DISABLED"
        if status_text and row_status != status_text:
            return False
        return True

    filtered = [record for record in records if matches(record)]
    start = (current - 1) * size
    return {
        "records": filtered[start:start + size],
        "total": len(filtered),
        "current": current,
        "size": size,
    }


def _next_id(records: list[dict[str, Any]], key: str) -> int:
    return max([int(record.get(key, 0)) for record in records] or [0]) + 1


def _student_record(student: Student) -> dict[str, Any]:
    return {
        "student_id": student.student_id,
        "student_no": student.student_no,
        "student_name": student.student_name,
        "college": student.college or "",
        "major": student.major_name or "",
        "class_name": student.class_name or "",
        "phone": "",
    }


def _template_record(template: CertificateTemplate) -> dict[str, Any]:
    return {
        "template_id": template.template_id,
        "name": template.template_name,
        "issuer": "示范学院",
        "course_name": "软件开发综合实训",
        "project_name": "2026暑期软件开发实训",
        "certificate_title": "实训结业证书",
        "content": template.content or "",
        "issue_year": "2026",
        "fields": ["student_name", "certificate_no", "issue_date", "qr_code"],
        "enabled": template.status == "ACTIVE",
        "updated_at": _format_datetime(template.created_at),
    }


def _batch_record(db: Session, batch: CertificateBatch) -> dict[str, Any]:
    certificates = db.query(Certificate).filter(Certificate.batch_id == batch.batch_id).all()
    evidenced = sum(1 for certificate in certificates if certificate.receipt_id)
    return {
        "batch_id": batch.batch_id,
        "batch_no": batch.batch_no,
        "batch_name": batch.batch_name,
        "project_name": "2026暑期软件开发实训",
        "template_id": 1,
        "student_count": len(certificates),
        "generated": len(certificates),
        "evidenced": evidenced,
        "status": batch.status,
    }


def _certificate_record(db: Session, certificate: Certificate) -> dict[str, Any]:
    student = db.get(Student, certificate.student_id)
    new_certificate = db.query(Certificate).filter(
        Certificate.previous_certificate_no == certificate.certificate_no
    ).first()
    issue_time = certificate.issue_time or certificate.created_at

    return {
        "certificate_id": certificate.certificate_id,
        "certificate_no": certificate.certificate_no,
        "student_id": certificate.student_id,
        "student_no": student.student_no if student else "",
        "student_name": certificate.student_name,
        "batch_id": certificate.batch_id or 0,
        "template_id": certificate.template_id or 0,
        "pdf_path": certificate.pdf_path or "",
        "certificate_hash": certificate.certificate_hash or "",
        "qr_code_path": certificate.qr_code_path or "",
        "verify_url": certificate.verify_url or "",
        "receipt_id": certificate.receipt_id or "",
        "status": certificate.status,
        "credential_type": certificate.credential_type,
        "root_id": certificate.root_id or "",
        "project_name": certificate.project_name,
        "issue_date": _format_date(issue_time),
        "evidence_status": "CONFIRMED" if certificate.receipt_id else "PENDING",
        "previous_certificate_no": certificate.previous_certificate_no,
        "new_certificate_no": new_certificate.certificate_no if new_certificate else None,
    }


def _receipt_record(db: Session, receipt: EvidenceReceipt) -> dict[str, Any]:
    certificate = db.get(Certificate, receipt.certificate_id)
    return {
        "receipt_id": receipt.receipt_no,
        "certificate_id": receipt.certificate_id,
        "certificate_no": certificate.certificate_no if certificate else "",
        "certificate_hash": receipt.certificate_hash,
        "evidence_type": receipt.chain_type,
        "previous_hash": receipt.previous_hash,
        "current_block_hash": receipt.current_block_hash,
        "block_height": receipt.block_height,
        "tx_hash": None,
        "contract_address": None,
        "evidence_time": _format_datetime(receipt.evidence_time),
        "status": "CONFIRMED",
    }


def _audit_record(log: AuditLog) -> dict[str, Any]:
    created_at = _format_datetime(log.created_at)
    return {
        "id": log.audit_id,
        "operator": log.operator or "system",
        "action": log.action,
        "module": log.target_type,
        "target": log.target_id or "",
        "detail": log.detail,
        "result": "SUCCESS",
        "created_at": created_at,
        "createdAt": created_at,
    }


def _ensure_template(db: Session, template_id: int | None) -> int | None:
    if template_id is None:
        return None
    if db.get(CertificateTemplate, template_id) is None:
        db.add(
            CertificateTemplate(
                template_id=template_id,
                template_name=f"Template {template_id}",
                template_code=f"TPL-{template_id:03d}",
                content="Demo certificate template for integration testing.",
                status="ACTIVE",
            )
        )
        db.flush()
    return template_id


def _ensure_batch(db: Session, batch_id: int | None) -> int | None:
    if batch_id is None:
        return None
    if db.get(CertificateBatch, batch_id) is None:
        db.add(
            CertificateBatch(
                batch_id=batch_id,
                batch_no=f"BATCH-{batch_id:04d}",
                batch_name=f"Batch {batch_id}",
                status="DRAFT",
            )
        )
        db.flush()
    return batch_id


def _get_certificate_by_identifier(db: Session, identifier: str) -> Certificate | None:
    if identifier.isdigit():
        certificate = db.get(Certificate, int(identifier))
        if certificate is not None:
            return certificate
    return db.query(Certificate).filter(Certificate.certificate_no == identifier).one_or_none()


def _certificate_template_dict(template_id: int | None, project_name: str | None = None) -> dict[str, Any]:
    return {
        "template_id": template_id,
        "template_code": f"TPL-{template_id or 1:03d}",
        "institution_name": "示范学院",
        "project_name": project_name or "2026暑期软件开发实训",
        "grade_level": "合格",
    }


@router.get("/dashboard/statistics")
def dashboard_statistics(db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    certificates = db.query(Certificate).all()
    receipts = db.query(EvidenceReceipt).order_by(EvidenceReceipt.block_height.desc()).limit(5).all()
    logs = db.query(AuditLog).order_by(AuditLog.audit_id.desc()).limit(5).all()

    if not certificates:
        return ApiResponse.success(
            {
                "projectCount": len(DEMO_PROJECTS),
                "student_count": len(DEMO_STUDENTS),
                "certificateCount": len(DEMO_CERTIFICATES),
                "evidencedCount": len(DEMO_RECEIPTS),
                "validCount": 1,
                "revokedCount": 0,
                "recentReceipts": DEMO_RECEIPTS[:5],
                "recentLogs": DEMO_AUDIT_LOGS[:5],
            }
        )

    return ApiResponse.success(
        {
            "projectCount": len(DEMO_PROJECTS),
            "student_count": db.query(Student).count(),
            "certificateCount": len(certificates),
            "evidencedCount": sum(1 for certificate in certificates if certificate.receipt_id),
            "validCount": sum(1 for certificate in certificates if certificate.status == "VALID"),
            "revokedCount": sum(1 for certificate in certificates if certificate.status == "REVOKED"),
            "recentReceipts": [_receipt_record(db, receipt) for receipt in receipts],
            "recentLogs": [_audit_record(log) for log in logs] or DEMO_AUDIT_LOGS[:5],
        }
    )


@router.get("/projects")
def list_projects(current: int = 1, size: int = 10, keyword: str | None = None,
                  status: str | None = None) -> ApiResponse[dict[str, Any]]:
    return ApiResponse.success(_page(DEMO_PROJECTS, current, size, keyword, status))


@router.post("/projects")
def create_project(payload: dict[str, Any]) -> ApiResponse[dict[str, Any]]:
    record = {"id": _next_id(DEMO_PROJECTS, "id"), **payload}
    DEMO_PROJECTS.insert(0, record)
    return ApiResponse.success(record)


@router.put("/projects/{project_id}")
def update_project(project_id: int, payload: dict[str, Any]) -> ApiResponse[dict[str, Any]]:
    for record in DEMO_PROJECTS:
        if record["id"] == project_id:
            record.update(payload)
            return ApiResponse.success(record)
    raise HTTPException(status_code=404, detail="project not found")


@router.delete("/projects/{project_id}")
def delete_project(project_id: int) -> ApiResponse[dict[str, Any]]:
    DEMO_PROJECTS[:] = [record for record in DEMO_PROJECTS if record["id"] != project_id]
    return ApiResponse.success({"deleted": True})


@router.get("/students")
def list_students(current: int = 1, size: int = 10, keyword: str | None = None,
                  status: str | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    students = db.query(Student).order_by(Student.student_id.desc()).all()
    records = [_student_record(student) for student in students] or DEMO_STUDENTS
    return ApiResponse.success(_page(records, current, size, keyword, status))


@router.post("/students")
def create_student(payload: StudentPayload, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    if not payload.student_no or not payload.student_name:
        raise HTTPException(status_code=422, detail="student_no and student_name are required")
    student = Student(
        student_no=payload.student_no,
        student_name=payload.student_name,
        college=payload.college,
        class_name=payload.class_name,
        major_name=payload.major_name or payload.major,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return ApiResponse.success(_student_record(student))


@router.put("/students/{student_id}")
def update_student(student_id: int, payload: StudentPayload,
                   db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student not found")
    if payload.student_no is not None:
        student.student_no = payload.student_no
    if payload.student_name is not None:
        student.student_name = payload.student_name
    if payload.college is not None:
        student.college = payload.college
    if payload.class_name is not None:
        student.class_name = payload.class_name
    if payload.major is not None or payload.major_name is not None:
        student.major_name = payload.major_name or payload.major
    db.commit()
    db.refresh(student)
    return ApiResponse.success(_student_record(student))


@router.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student not found")
    db.delete(student)
    db.commit()
    return ApiResponse.success({"deleted": True})


@router.post("/_legacy/students/import-placeholder", include_in_schema=False)
async def import_students(file: UploadFile = File(...), batch_name: str = Form(""),
                          template_id: int = Form(0)) -> ApiResponse[dict[str, Any]]:
    # 当前仅完成接口联调，不解析上传文件内容，避免把本地隐私数据误写入数据库。
    await file.close()
    return ApiResponse.success(
        {
            "success_count": 0,
            "failed_count": 0,
            "failures": [],
            "message": "Import endpoint is connected; parsing will be implemented after template is finalized.",
        }
    )


@router.get("/templates")
def list_templates(current: int = 1, size: int = 10, keyword: str | None = None,
                   status: str | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    templates = db.query(CertificateTemplate).order_by(CertificateTemplate.template_id.desc()).all()
    records = [_template_record(template) for template in templates] or DEMO_TEMPLATES
    return ApiResponse.success(_page(records, current, size, keyword, status))


@router.post("/templates")
def create_template(payload: TemplatePayload, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    content_config = payload.content_config or {}
    template = CertificateTemplate(
        template_name=payload.template_name or payload.name or "Certificate Template",
        template_code=f"TPL-{int(datetime.utcnow().timestamp())}",
        content=str(content_config),
        status=payload.status or "ACTIVE",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return ApiResponse.success(_template_record(template))


@router.put("/templates/{template_id}")
def update_template(template_id: int, payload: TemplatePayload,
                    db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    template = db.get(CertificateTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    if payload.template_name or payload.name:
        template.template_name = payload.template_name or payload.name or template.template_name
    if payload.content_config is not None:
        template.content = str(payload.content_config)
    if payload.status is not None:
        template.status = payload.status
    db.commit()
    db.refresh(template)
    return ApiResponse.success(_template_record(template))


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    template = db.get(CertificateTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    db.delete(template)
    db.commit()
    return ApiResponse.success({"deleted": True})


@router.get("/certificate-batches")
def list_batches(current: int = 1, size: int = 10, keyword: str | None = None,
                 status: str | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    batches = db.query(CertificateBatch).order_by(CertificateBatch.batch_id.desc()).all()
    records = [_batch_record(db, batch) for batch in batches] or DEMO_BATCHES
    return ApiResponse.success(_page(records, current, size, keyword, status))


@router.post("/certificate-batches")
def create_batch(payload: BatchPayload, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    batch = CertificateBatch(
        batch_no=payload.batch_no or f"BATCH-{int(datetime.utcnow().timestamp())}",
        batch_name=payload.batch_name or "Certificate Batch",
        status=payload.status or "DRAFT",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return ApiResponse.success(_batch_record(db, batch))


@router.put("/certificate-batches/{batch_id}")
def update_batch(batch_id: int, payload: BatchPayload,
                 db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    if payload.batch_name is not None:
        batch.batch_name = payload.batch_name
    if payload.batch_no is not None:
        batch.batch_no = payload.batch_no
    if payload.status is not None:
        batch.status = payload.status
    db.commit()
    db.refresh(batch)
    return ApiResponse.success(_batch_record(db, batch))


@router.delete("/certificate-batches/{batch_id}")
def delete_batch(batch_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    db.delete(batch)
    db.commit()
    return ApiResponse.success({"deleted": True})


@router.get("/certificates")
def list_certificates(current: int = 1, size: int = 10, keyword: str | None = None,
                      status: str | None = None, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    certificates = db.query(Certificate).order_by(Certificate.certificate_id.desc()).all()
    records = [_certificate_record(db, certificate) for certificate in certificates] or DEMO_CERTIFICATES
    return ApiResponse.success(_page(records, current, size, keyword, status))


@router.post("/certificate-batches/{batch_id}/issue")
def issue_certificates(batch_id: int, payload: IssuePayload,
                       db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    template_id = _ensure_template(db, payload.template_id)
    actual_batch_id = _ensure_batch(db, batch_id)
    db.commit()

    issue_date = _parse_issue_date(payload.issue_date)
    template = _certificate_template_dict(template_id)
    failures: list[dict[str, Any]] = []
    success_count = 0

    for student_id in payload.student_ids:
        try:
            certificate_service.generate_certificate(
                db,
                student_id=student_id,
                template=template,
                issue_date=issue_date,
                batch_id=actual_batch_id,
            )
            success_count += 1
        except Exception as exc:
            failures.append({"student_id": student_id, "reason": str(exc)})

    return ApiResponse.success(
        {
            "success_count": success_count,
            "failed_count": len(failures),
            "failures": failures,
        }
    )


@router.post("/certificates/{certificate_id}/evidence")
def evidence_certificate(certificate_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")
    if not certificate.certificate_hash:
        raise HTTPException(status_code=400, detail="certificate hash is empty")
    if not certificate.receipt_id:
        receipt = certificate_service._create_evidence_receipt(
            db,
            certificate.certificate_id,
            certificate.certificate_no,
            certificate.certificate_hash,
        )
        certificate.receipt_id = receipt.receipt_no
    db.commit()
    db.refresh(certificate)
    return ApiResponse.success(_certificate_record(db, certificate))


@router.post("/certificate-batches/{batch_id}/evidence")
def evidence_batch(batch_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    certificates = db.query(Certificate).filter(Certificate.batch_id == batch_id).all()
    for certificate in certificates:
        if certificate.certificate_hash and not certificate.receipt_id:
            receipt = certificate_service._create_evidence_receipt(
                db,
                certificate.certificate_id,
                certificate.certificate_no,
                certificate.certificate_hash,
            )
            certificate.receipt_id = receipt.receipt_no
    db.commit()
    return ApiResponse.success({"evidenced": len(certificates)})


@router.post("/certificates/{certificate_identifier}/revoke")
def revoke_certificate(certificate_identifier: str, payload: RevokePayload,
                       db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    certificate = _get_certificate_by_identifier(db, certificate_identifier)
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")
    certificate.status = CertificateStatus.REVOKED.value
    db.add(
        RevocationRecord(
            certificate_id=certificate.certificate_id,
            action_type="REVOKE",
            reason=payload.reason,
            operator="admin",
        )
    )
    db.add(
        AuditLog(
            action="证书撤销",
            target_type="证书管理",
            target_id=certificate.certificate_no[:64],
            operator="admin",
            detail=payload.reason,
        )
    )
    db.commit()
    db.refresh(certificate)
    return ApiResponse.success(_certificate_record(db, certificate))


@router.post("/certificates/{certificate_id}/reissue")
def reissue_certificate(certificate_id: int, payload: ReissuePayload,
                        db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    old_certificate = db.get(Certificate, certificate_id)
    if old_certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")

    new_certificate = certificate_service.generate_certificate(
        db,
        student_id=old_certificate.student_id,
        template=_certificate_template_dict(old_certificate.template_id, old_certificate.project_name),
        issue_date=_parse_issue_date(payload.issue_date),
        batch_id=old_certificate.batch_id,
        previous_certificate_no=old_certificate.certificate_no,
    )

    old_certificate.status = CertificateStatus.REISSUED.value
    db.add(
        RevocationRecord(
            certificate_id=old_certificate.certificate_id,
            action_type="REISSUE",
            reason=payload.reason,
            operator="admin",
            new_certificate_no=new_certificate.certificate_no,
        )
    )
    db.add(
        AuditLog(
            action="证书补发",
            target_type="证书管理",
            target_id=old_certificate.certificate_no[:64],
            operator="admin",
            detail=f"{payload.reason}; new={new_certificate.certificate_no}",
        )
    )
    db.commit()
    db.refresh(old_certificate)
    db.refresh(new_certificate)
    return ApiResponse.success(
        {
            "old_certificate": _certificate_record(db, old_certificate),
            "new_certificate": _certificate_record(db, new_certificate),
        }
    )


@router.delete("/certificates/{certificate_id}")
def delete_certificate(certificate_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="certificate not found")
    if certificate.status == CertificateStatus.DRAFT.value:
        db.delete(certificate)
        db.commit()
        return ApiResponse.success({"deleted": True})
    return ApiResponse.success({"deleted": False, "message": "issued certificates are kept for audit"})


@router.get("/evidence/receipts")
def list_receipts(current: int = 1, size: int = 10, keyword: str | None = None,
                  status: str | None = None, evidence_type: str | None = None,
                  db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    receipts = db.query(EvidenceReceipt).order_by(EvidenceReceipt.block_height.desc()).all()
    records = [_receipt_record(db, receipt) for receipt in receipts] or DEMO_RECEIPTS
    if evidence_type:
        records = [record for record in records if record.get("evidence_type") == evidence_type]
    return ApiResponse.success(_page(records, current, size, keyword, status))


@router.get("/evidence/receipts/{receipt_id}")
def get_receipt(receipt_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    receipt = db.query(EvidenceReceipt).filter(EvidenceReceipt.receipt_no == receipt_id).one_or_none()
    if receipt is not None:
        return ApiResponse.success(_receipt_record(db, receipt))
    for record in DEMO_RECEIPTS:
        if record["receipt_id"] == receipt_id:
            return ApiResponse.success(record)
    raise HTTPException(status_code=404, detail="receipt not found")


@router.get("/evidence/integrity")
def check_integrity(db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    receipts = db.query(EvidenceReceipt).order_by(EvidenceReceipt.block_height.asc()).all()
    if not receipts:
        return ApiResponse.success({"valid": True, "message": "No receipt data yet."})

    expected_previous_hash = "0" * 64
    for receipt in receipts:
        if receipt.previous_hash != expected_previous_hash:
            return ApiResponse.success(
                {
                    "valid": False,
                    "message": "Local hash chain is broken.",
                    "brokenHeight": receipt.block_height,
                }
            )
        expected_previous_hash = receipt.current_block_hash

    return ApiResponse.success({"valid": True, "message": "本地哈希链完整性校验通过"})


@router.get("/audit-logs")
def list_audit_logs(current: int = 1, size: int = 10, keyword: str | None = None,
                    status: str | None = None, module: str | None = None,
                    db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    logs = db.query(AuditLog).order_by(AuditLog.audit_id.desc()).all()
    records = [_audit_record(log) for log in logs] or DEMO_AUDIT_LOGS
    if module:
        records = [record for record in records if record.get("module") == module]
    return ApiResponse.success(_page(records, current, size, keyword, status))


@router.get("/audit-logs/{audit_id}")
def get_audit_log(audit_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict[str, Any]]:
    log = db.get(AuditLog, audit_id)
    if log is not None:
        return ApiResponse.success(_audit_record(log))
    for record in DEMO_AUDIT_LOGS:
        if record["id"] == audit_id:
            return ApiResponse.success(record)
    raise HTTPException(status_code=404, detail="audit log not found")
