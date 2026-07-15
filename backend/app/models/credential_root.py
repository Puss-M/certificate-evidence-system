from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CredentialRoot(Base):
    """Merkle Root 记录（数据库设计.md 第9.1/9.2节）。

    一个批次"存证"完成后计算一次，root_no 是业务编号（格式仿照 certificate_no /
    receipt_no：ROOT-YYYYMMDD-序号），Certificate.root_id 存的就是这个业务编号，
    不是本表自增主键 root_id ——这个约定跟 receipt_id / receipt_no 的关系完全一致，
    见 certificate_service.py 里的注释。

    current_root_hash / previous_root_hash 构成 Root 链，口径见 9.2 节：
    current_root_hash = SHA256(batch_id + merkle_root + previous_root_hash + created_at)
    """

    __tablename__ = "credential_roots"
    __table_args__ = (
        UniqueConstraint("batch_id", name="uq_credential_roots_batch_id"),
    )

    root_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    root_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("certificate_batches.batch_id"))
    merkle_root: Mapped[str] = mapped_column(String(64))
    previous_root_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_root_hash: Mapped[str] = mapped_column(String(64))
    leaf_order_rule: Mapped[str] = mapped_column(
        String(32),
        default="CERTIFICATE_NO_ASC",
    )
    # 固定值 DUPLICATE_LAST（9.1节奇数叶处理规则），先存成字段，为以后可能出现
    # 别的规则留口子，目前只有这一种取值。
    odd_leaf_rule: Mapped[str] = mapped_column(String(32), default="DUPLICATE_LAST")
    leaf_count: Mapped[int] = mapped_column(Integer)
    # 测试链接入用（P2加分项，见chain_service.py）：写链成功才有值，没配置/失败时
    # 保持None，不影响本地这条记录本身的完整性——Root在本地已经算好、已经能验证，
    # 上链只是给它多附加一份"链上回执"。
    tx_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
