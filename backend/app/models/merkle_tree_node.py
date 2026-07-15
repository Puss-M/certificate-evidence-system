from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerkleTreeNode(Base):
    """Merkle 树节点（数据库设计.md 第9.3节）。

    一棵树的所有节点（叶子 + 内部节点）都存在这张表里，通过 root_id + level +
    position_in_level 唯一定位一个节点。level=0 是叶子层，叶子节点额外填
    certificate_no；内部节点 certificate_no 为空。生成某张证书的 Merkle Proof
    时就是从叶子节点出发，逐层找兄弟节点。
    """

    __tablename__ = "merkle_tree_nodes"

    node_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    root_id: Mapped[int] = mapped_column(ForeignKey("credential_roots.root_id"))
    level: Mapped[int] = mapped_column(Integer)
    position_in_level: Mapped[int] = mapped_column(Integer)
    node_hash: Mapped[str] = mapped_column(String(64))
    certificate_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
