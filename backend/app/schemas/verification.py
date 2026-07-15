from pydantic import BaseModel


class VerificationResult(BaseModel):
    result: str
    verify_result: str
    certificate_no: str
    student_name: str | None = None
    project_name: str | None = None
    institution_name: str | None = None
    certificate_hash: str | None = None
    stored_hash: str | None = None
    receipt_id: str | None = None
    receipt_exists: bool
    status: str | None = None
    message: str
    verify_message: str
    hash_match: bool
    uploaded_hash: str | None = None
    revocation_reason: str | None = None
    revoked_at: str | None = None
