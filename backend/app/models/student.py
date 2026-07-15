from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    student_name: Mapped[str] = mapped_column(String(64))
    college: Mapped[str | None] = mapped_column(String(100), nullable=True)
    class_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    major_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
