"""
Merkle Root 计算服务（P2 加分项，任务清单 4.1）。

对应方案文档 docs/协作管理/FISCO_BCOS与存证降级策略.md 第8节、
docs/协作管理/数据库设计.md 第9节。这是本地哈希链（certificate_service.py 里
每张证书各自的 evidence_receipts 记录）之上叠加的一层，不替代本地哈希链，
目的是让"批量上测试链"只需要一笔交易（一个批次一个 Root），单张证书仍然可以
通过 Merkle Proof 单独验证，不需要暴露批次内其他证书的数据。

这里只做到"算出 Root、能生成/验证 Proof"为止，真正把 Root 写上 Hardhat/Ganache
测试链是下一步，不在这个文件的范围内（避免耦合，测试链失败要能直接降级回这一层，
不影响 Root 本身已经算好、已经能验证的事实）。
"""

import hashlib
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.models.certificate_batch import CertificateBatch
from app.models.credential_root import CredentialRoot
from app.models.merkle_tree_node import MerkleTreeNode


class MerkleBatchNotFoundError(ValueError):
    pass


class MerkleRootAlreadyExistsError(ValueError):
    pass


class MerkleRootConflictError(ValueError):
    pass


def _pair_hash(left: str, right: str) -> str:
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


def build_merkle_levels(leaf_hashes: list[str]) -> list[list[str]]:
    """按9.1节规则从叶子层逐层往上建树，返回每一层的节点哈希列表（level0是叶子）。

    奇数个节点时，复制该层最后一个节点当右节点参与父节点计算（DUPLICATE_LAST），
    对应文档里"某一层节点数为奇数时，复制该层最后一个节点作为右节点"。
    """
    if not leaf_hashes:
        raise ValueError("叶子节点不能为空，批次内至少要有一张已生成哈希的证书")

    levels: list[list[str]] = [list(leaf_hashes)]
    current = levels[0]
    while len(current) > 1:
        next_level: list[str] = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else current[i]
            next_level.append(_pair_hash(left, right))
        levels.append(next_level)
        current = next_level
    return levels


def _next_root_no(db: Session, created_at: datetime) -> str:
    date_str = created_at.strftime("%Y%m%d")
    prefix = f"ROOT-{date_str}-"

    max_no = db.query(func.max(CredentialRoot.root_no)).filter(
        CredentialRoot.root_no.like(f"{prefix}%")
    ).scalar()

    next_seq = 1 if max_no is None else int(max_no.split("-")[-1]) + 1
    return f"{prefix}{next_seq:04d}"


def compute_batch_root(db: Session, batch_id: int) -> CredentialRoot:
    """给一个批次算一次 Merkle Root，落库 credential_roots + merkle_tree_nodes，
    并把每张证书的 root_id 字段（存 root_no 业务编号，跟 receipt_id 存 receipt_no
    是同一个约定）填上。

    触发时机按9.1节"该批次存证动作完成、批次内所有证书都已生成哈希之后统一计算
    一次"——这里不检查批次的 status 字段本身（避免和4号那边 evidence_batch 的状态
    流转逻辑耦合），改成直接检查落地的结果：批次下有没有证书、每张证书是否都已经
    有 certificate_hash、每张证书是否都已经有 receipt_id（存证回执），三个条件
    有一个不满足就报错，不会算出一个不完整的 Root。
    """
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise MerkleBatchNotFoundError(f"批次不存在：batch_id={batch_id}")

    existing_root = (
        db.query(CredentialRoot)
        .filter(CredentialRoot.batch_id == batch_id)
        .one_or_none()
    )
    if existing_root is not None:
        raise MerkleRootAlreadyExistsError(
            f"批次batch_id={batch_id}已经生成Merkle Root：{existing_root.root_no}"
        )

    certificates = (
        db.query(Certificate)
        .filter(Certificate.batch_id == batch_id)
        .order_by(Certificate.certificate_no.asc())
        .all()
    )
    if not certificates:
        raise ValueError(f"批次batch_id={batch_id}下还没有任何证书，无法计算Merkle Root")

    missing_hash = [c.certificate_no for c in certificates if not c.certificate_hash]
    if missing_hash:
        raise ValueError(f"以下证书还没有哈希，无法计算Merkle Root：{missing_hash}")

    # 9.1节触发时机原文是"该批次'存证'动作完成、批次内所有证书都已生成哈希之后"——
    # 除了哈希本身，也顺带查一下receipt_id（对应本地哈希链的存证回执）是否都已写入，
    # 更贴合"存证动作完成"这个措辞。在当前实现里两者其实总是一起产生的
    # （generate_certificate()内部hash算完紧接着就建回执），这一步理论上不会命中，
    # 是个防御性检查，不是多余的。
    missing_receipt = [c.certificate_no for c in certificates if not c.receipt_id]
    if missing_receipt:
        raise ValueError(f"以下证书还没有存证回执，无法计算Merkle Root：{missing_receipt}")

    leaf_hashes = [c.certificate_hash for c in certificates]
    levels = build_merkle_levels(leaf_hashes)
    merkle_root = levels[-1][0]

    last_root = db.query(CredentialRoot).order_by(CredentialRoot.root_id.desc()).first()
    previous_root_hash = last_root.current_root_hash if last_root else "0" * 64

    created_at = datetime.utcnow()
    created_at_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
    raw = f"{batch_id}{merkle_root}{previous_root_hash}{created_at_str}"
    current_root_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    root_record = CredentialRoot(
        root_no=_next_root_no(db, created_at),
        batch_id=batch_id,
        merkle_root=merkle_root,
        previous_root_hash=previous_root_hash,
        current_root_hash=current_root_hash,
        leaf_order_rule="CERTIFICATE_NO_ASC",
        odd_leaf_rule="DUPLICATE_LAST",
        leaf_count=len(leaf_hashes),
        created_at=created_at,
    )
    db.add(root_record)
    db.flush()  # 拿到 root_record.root_id，供节点表外键关联

    for level_index, level_hashes in enumerate(levels):
        for position, node_hash in enumerate(level_hashes):
            certificate_no = certificates[position].certificate_no if level_index == 0 else None
            db.add(
                MerkleTreeNode(
                    root_id=root_record.root_id,
                    level=level_index,
                    position_in_level=position,
                    node_hash=node_hash,
                    certificate_no=certificate_no,
                )
            )

    for certificate in certificates:
        certificate.root_id = root_record.root_no

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MerkleRootConflictError(
            f"批次batch_id={batch_id}的Merkle Root生成发生并发冲突，请查询现有Root"
        ) from exc
    db.refresh(root_record)
    return root_record


def get_merkle_proof(db: Session, certificate_no: str) -> dict:
    """给一张证书生成 Merkle Proof（9.3节）。返回值里的 proof 是从叶子到根逐层的
    兄弟节点列表，每一项是 {sibling_hash, direction}，direction 的含义跟文档一致：
    LEFT 表示兄弟节点在当前累计哈希左侧（重算用 SHA256(sibling+current)），
    RIGHT 表示兄弟节点在右侧（重算用 SHA256(current+sibling)）。
    """
    certificate = (
        db.query(Certificate).filter(Certificate.certificate_no == certificate_no).first()
    )
    if certificate is None:
        raise ValueError(f"证书不存在：{certificate_no}")
    if not certificate.root_id:
        raise ValueError(f"证书{certificate_no}所在批次还没有计算Merkle Root")

    root_record = (
        db.query(CredentialRoot).filter(CredentialRoot.root_no == certificate.root_id).first()
    )
    if root_record is None:
        raise ValueError(f"找不到证书{certificate_no}对应的Root记录：{certificate.root_id}")

    leaf_node = (
        db.query(MerkleTreeNode)
        .filter(
            MerkleTreeNode.root_id == root_record.root_id,
            MerkleTreeNode.certificate_no == certificate_no,
        )
        .first()
    )
    if leaf_node is None:
        raise ValueError(f"找不到证书{certificate_no}对应的叶子节点")

    max_level = db.query(func.max(MerkleTreeNode.level)).filter(
        MerkleTreeNode.root_id == root_record.root_id
    ).scalar()

    proof: list[dict] = []
    level = leaf_node.level
    position = leaf_node.position_in_level

    while level < max_level:
        level_nodes = {
            node.position_in_level: node.node_hash
            for node in db.query(MerkleTreeNode).filter(
                MerkleTreeNode.root_id == root_record.root_id,
                MerkleTreeNode.level == level,
            )
        }
        is_right = position % 2 == 1
        sibling_position = position - 1 if is_right else position + 1
        # 找不到兄弟节点，说明这一层是奇数个、当前节点是被复制的最后一个
        # （DUPLICATE_LAST），兄弟就是自己。
        sibling_hash = level_nodes.get(sibling_position, level_nodes[position])
        direction = "LEFT" if is_right else "RIGHT"
        proof.append({"sibling_hash": sibling_hash, "direction": direction})

        position //= 2
        level += 1

    return {
        "certificate_no": certificate_no,
        "certificate_hash": certificate.certificate_hash,
        "leaf_index": leaf_node.position_in_level,
        "leaf_order_rule": root_record.leaf_order_rule,
        "odd_leaf_rule": root_record.odd_leaf_rule,
        "root_id": root_record.root_no,
        "root_no": root_record.root_no,
        "merkle_root": root_record.merkle_root,
        "merkle_proof": proof,
        "proof": proof,
    }


def verify_merkle_proof(certificate_hash: str, proof: list[dict], expected_root: str) -> bool:
    """拿证书自身哈希 + Proof，逐层重算，最终结果跟 merkle_root 比对。"""
    current_hash = certificate_hash
    for step in proof:
        sibling_hash = step["sibling_hash"]
        direction = step["direction"]
        if direction == "LEFT":
            current_hash = _pair_hash(sibling_hash, current_hash)
        elif direction == "RIGHT":
            current_hash = _pair_hash(current_hash, sibling_hash)
        else:
            raise ValueError(f"未知的direction取值：{direction}")
    return current_hash == expected_root
