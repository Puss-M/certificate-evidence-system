from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RevocationRecord(Base):
    __tablename__ = "revocation_records"

    revocation_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("certificates.certificate_id"))
    action_type: Mapped[str] = mapped_column(String(32), default="REVOKE")
    reason: Mapped[str] = mapped_column(String(255))
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_certificate_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
