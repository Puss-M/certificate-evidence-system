from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utcnow
from app.db.base import Base


class EvidenceReceipt(Base):
    __tablename__ = "evidence_receipts"

    receipt_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    receipt_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    certificate_id: Mapped[int] = mapped_column(ForeignKey("certificates.certificate_id"))
    certificate_hash: Mapped[str] = mapped_column(String(64))
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_block_hash: Mapped[str] = mapped_column(String(64))
    block_height: Mapped[int] = mapped_column(Integer)
    evidence_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    chain_type: Mapped[str] = mapped_column(String(32), default="LOCAL_HASH_CHAIN")