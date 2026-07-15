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


# Merkle Proof 相关，数据库设计.md第9.3节。direction取值LEFT/RIGHT，含义见
# merkle_service.get_merkle_proof() 的注释。
class MerkleProofStep(BaseModel):
    sibling_hash: str
    direction: str


class MerkleProofResult(BaseModel):
    certificate_no: str
    certificate_hash: str | None = None
    root_no: str
    merkle_root: str
    proof: list[MerkleProofStep]
    # 拿proof + certificate_hash逐层重算，跟merkle_root比对的结果——只代表
    # "内容完整性"（有没有被篡改），不代表证书当前是否有效，两者按9.4节要求
    # 分开展示，不能混为一谈。
    verified: bool
