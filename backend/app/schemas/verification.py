from pydantic import BaseModel


class VerificationResult(BaseModel):
    result: str
    certificate_no: str
    student_name: str | None = None
    certificate_hash: str | None = None
    receipt_id: str | None = None
    status: str | None = None
    message: str
    # 以下两个字段仅在"上传PDF复验"场景下才会有值，编号验真时保持 None
    hash_match: bool | None = None
    uploaded_hash: str | None = None