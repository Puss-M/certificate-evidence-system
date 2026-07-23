from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CertificateStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    EVIDENCED = "EVIDENCED"
    VALID = "VALID"
    REVOKED = "REVOKED"
    REISSUED = "REISSUED"
    EXPIRED = "EXPIRED"


class Certificate(Base):
    __tablename__ = "certificates"

    certificate_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    certificate_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id"))
    student_name: Mapped[str] = mapped_column(String(64))
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("certificate_batches.batch_id"),
        nullable=True,
    )
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("certificate_templates.template_id"),
        nullable=True,
    )
    credential_type: Mapped[str] = mapped_column(String(32), default="CERTIFICATE")
    project_name: Mapped[str] = mapped_column(String(200), default="软件开发实训")
    institution_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    certificate_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qr_code_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verify_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=CertificateStatus.DRAFT.value)
    root_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_certificate_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
