from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CertificateBatch(Base):
    __tablename__ = "certificate_batches"

    batch_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    batch_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 下面几个字段是新增的（补齐接口规范.md第4.3/4.4节"创建证书批次"/"批量生成证书"
    # 需要用到的信息，之前这张表只有最基础的4个字段）。都设为可空，不影响已有数据/代码：
    # - project_name：前端Batch类型里要展示的项目名称，暂时只是记录用，不关联真实的
    #   项目表（项目管理这块还没做，等做了再补外键）
    # - template_id：这批证书用哪个模板，暂时也只是记录用的整数，不做外键约束——
    #   模板内容目前还是证书生成服务里写死的默认值兜底（见certificate_batches.py里的
    #   DEFAULT_TEMPLATE），等模板管理功能做出来后再对接成真正查库
    # - student_ids：按接口规范.md，创建批次时就要传这批证书发给哪些学生
    #   （POST /admin/batches请求体里的student_ids），后面触发生成
    #   （POST /admin/batches/{batch_id}/generate）不再需要重复传一遍名单，
    #   直接用创建批次时存下来的这份名单
    project_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    template_id: Mapped[int | None] = mapped_column(nullable=True)
    student_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)