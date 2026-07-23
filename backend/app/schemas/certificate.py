from pydantic import BaseModel


class CertificateListItem(BaseModel):
    certificate_id: int
    certificate_no: str
    student_id: int
    student_no: str | None = None
    student_name: str
    batch_id: int | str | None = None
    template_id: int | str | None = None
    project_name: str | None = None
    institution_name: str | None = None
    issue_date: str | None = None
    issue_time: str | None = None
    pdf_path: str | None = None
    certificate_hash: str | None = None
    qr_code_path: str | None = None
    verify_url: str | None = None
    receipt_id: str | None = None
    status: str
    evidence_status: str | None = None
    credential_type: str = "CERTIFICATE"
    root_id: str | None = None
    previous_certificate_no: str | None = None
    new_certificate_no: str | None = None
