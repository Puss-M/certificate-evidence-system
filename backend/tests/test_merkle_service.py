"""
Merkle Root服务测试。覆盖：偶数/奇数叶子建树、Root链式关联（previous/current）、
Proof生成与验证（含篡改检测）、撤销与Root的解耦（9.4节）、以及批次生成Root的路由。
"""
import asyncio
import hashlib
from datetime import datetime

import httpx
import pytest

from app.main import app
from app.models.certificate import Certificate
from app.models.credential_root import CredentialRoot
from app.models.student import Student
from app.services import certificate_service, merkle_service


TEMPLATE = {
    "template_code": "TPL-001",
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}


def _pair(left: str, right: str) -> str:
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


def _make_batch_certificates(db_session, count: int, offset: int = 0) -> list[Certificate]:
    certificates = []
    for i in range(count):
        student_no = f"9{offset:02d}{i:02d}"
        student = Student(student_no=student_no, student_name=f"merkle学生{student_no}", class_name="1班")
        db_session.add(student)
        db_session.commit()
        certificate = certificate_service.generate_certificate(
            db_session,
            student_id=student.student_id,
            template=TEMPLATE,
            issue_date=datetime(2026, 7, 15),
            batch_id=1,
        )
        certificates.append(certificate)
    return certificates


def test_build_merkle_levels_even_leaves() -> None:
    leaves = ["a" * 64, "b" * 64, "c" * 64, "d" * 64]
    levels = merkle_service.build_merkle_levels(leaves)

    assert levels[0] == leaves
    expected_level1 = [_pair(leaves[0], leaves[1]), _pair(leaves[2], leaves[3])]
    assert levels[1] == expected_level1
    expected_root = _pair(expected_level1[0], expected_level1[1])
    assert levels[-1] == [expected_root]


def test_build_merkle_levels_odd_leaves_duplicates_last() -> None:
    leaves = ["a" * 64, "b" * 64, "c" * 64]
    levels = merkle_service.build_merkle_levels(leaves)

    # 奇数个叶子：最后一个节点被复制当右节点
    expected_level1 = [_pair(leaves[0], leaves[1]), _pair(leaves[2], leaves[2])]
    assert levels[1] == expected_level1


def test_build_merkle_levels_empty_raises() -> None:
    with pytest.raises(ValueError):
        merkle_service.build_merkle_levels([])


def test_compute_batch_root_requires_certificates(db_session) -> None:
    from app.models.certificate_batch import CertificateBatch

    batch = CertificateBatch(batch_no="BATCH-EMPTY", batch_name="空批次", status="DRAFT")
    db_session.add(batch)
    db_session.commit()

    with pytest.raises(ValueError, match="没有任何证书"):
        merkle_service.compute_batch_root(db_session, batch.batch_id)


def test_compute_batch_root_writes_nodes_and_updates_certificates(db_session) -> None:
    from app.models.certificate_batch import CertificateBatch
    from app.models.merkle_tree_node import MerkleTreeNode

    batch = CertificateBatch(batch_no="BATCH-001", batch_name="测试批次", status="DRAFT")
    db_session.add(batch)
    db_session.commit()

    certificates = _make_batch_certificates(db_session, 3)
    for certificate in certificates:
        certificate.batch_id = batch.batch_id
    db_session.commit()

    root_record = merkle_service.compute_batch_root(db_session, batch.batch_id)

    assert root_record.leaf_count == 3
    assert root_record.previous_root_hash == "0" * 64
    assert root_record.odd_leaf_rule == "DUPLICATE_LAST"

    nodes = db_session.query(MerkleTreeNode).filter(MerkleTreeNode.root_id == root_record.root_id).all()
    leaf_nodes = [n for n in nodes if n.level == 0]
    assert len(leaf_nodes) == 3
    assert {n.certificate_no for n in leaf_nodes} == {c.certificate_no for c in certificates}

    for certificate in certificates:
        db_session.refresh(certificate)
        assert certificate.root_id == root_record.root_no


def test_compute_batch_root_rejects_duplicate_batch(db_session) -> None:
    from app.models.certificate_batch import CertificateBatch

    batch = CertificateBatch(batch_no="BATCH-DUP", batch_name="重复Root批次", status="DRAFT")
    db_session.add(batch)
    db_session.commit()

    certificates = _make_batch_certificates(db_session, 2, offset=8)
    for certificate in certificates:
        certificate.batch_id = batch.batch_id
    db_session.commit()

    merkle_service.compute_batch_root(db_session, batch.batch_id)
    with pytest.raises(merkle_service.MerkleRootAlreadyExistsError):
        merkle_service.compute_batch_root(db_session, batch.batch_id)


def test_second_batch_root_chains_to_first(db_session) -> None:
    from app.models.certificate_batch import CertificateBatch

    batch1 = CertificateBatch(batch_no="BATCH-A", batch_name="批次A", status="DRAFT")
    batch2 = CertificateBatch(batch_no="BATCH-B", batch_name="批次B", status="DRAFT")
    db_session.add_all([batch1, batch2])
    db_session.commit()

    certs1 = _make_batch_certificates(db_session, 2, offset=1)
    for c in certs1:
        c.batch_id = batch1.batch_id
    db_session.commit()
    root1 = merkle_service.compute_batch_root(db_session, batch1.batch_id)

    certs2 = _make_batch_certificates(db_session, 2, offset=2)
    for c in certs2:
        c.batch_id = batch2.batch_id
    db_session.commit()
    root2 = merkle_service.compute_batch_root(db_session, batch2.batch_id)

    assert root2.previous_root_hash == root1.current_root_hash
    assert root2.current_root_hash != root1.current_root_hash


def test_get_and_verify_merkle_proof_roundtrip(db_session) -> None:
    from app.models.certificate_batch import CertificateBatch

    batch = CertificateBatch(batch_no="BATCH-PROOF", batch_name="Proof测试批次", status="DRAFT")
    db_session.add(batch)
    db_session.commit()

    certificates = _make_batch_certificates(db_session, 5)  # 奇数，触发DUPLICATE_LAST路径
    for c in certificates:
        c.batch_id = batch.batch_id
    db_session.commit()

    root_record = merkle_service.compute_batch_root(db_session, batch.batch_id)

    for certificate in certificates:
        proof_data = merkle_service.get_merkle_proof(db_session, certificate.certificate_no)
        assert proof_data["merkle_root"] == root_record.merkle_root
        verified = merkle_service.verify_merkle_proof(
            proof_data["certificate_hash"], proof_data["proof"], proof_data["merkle_root"]
        )
        assert verified is True


def test_verify_merkle_proof_fails_on_tampered_hash(db_session) -> None:
    from app.models.certificate_batch import CertificateBatch

    batch = CertificateBatch(batch_no="BATCH-TAMPER", batch_name="篡改测试批次", status="DRAFT")
    db_session.add(batch)
    db_session.commit()

    certificates = _make_batch_certificates(db_session, 4)
    for c in certificates:
        c.batch_id = batch.batch_id
    db_session.commit()

    merkle_service.compute_batch_root(db_session, batch.batch_id)
    proof_data = merkle_service.get_merkle_proof(db_session, certificates[0].certificate_no)

    tampered_hash = "f" * 64
    verified = merkle_service.verify_merkle_proof(
        tampered_hash, proof_data["proof"], proof_data["merkle_root"]
    )
    assert verified is False


def test_revocation_does_not_touch_root(db_session) -> None:
    """9.4节：撤销只改certificates.status，不能改credential_roots/merkle_tree_nodes。"""
    from app.models.certificate_batch import CertificateBatch

    batch = CertificateBatch(batch_no="BATCH-REVOKE", batch_name="撤销测试批次", status="DRAFT")
    db_session.add(batch)
    db_session.commit()

    certificates = _make_batch_certificates(db_session, 2)
    for c in certificates:
        c.batch_id = batch.batch_id
    db_session.commit()

    root_record = merkle_service.compute_batch_root(db_session, batch.batch_id)
    root_hash_before = root_record.current_root_hash

    # 模拟撤销：只改status，不动Root
    certificates[0].status = "REVOKED"
    db_session.commit()

    proof_data = merkle_service.get_merkle_proof(db_session, certificates[0].certificate_no)
    verified = merkle_service.verify_merkle_proof(
        proof_data["certificate_hash"], proof_data["proof"], proof_data["merkle_root"]
    )
    # 内容完整性验证依然通过（证书文件没被篡改），跟"已撤销"是两件事
    assert verified is True

    refreshed_root = db_session.get(CredentialRoot, root_record.root_id)
    assert refreshed_root.current_root_hash == root_hash_before


async def _post_json(path: str, payload: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            path,
            json=payload,
            headers={"Authorization": "Bearer demo-admin-token"},
        )


async def _get_json(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers={"Authorization": "Bearer demo-admin-token"})


def test_merkle_root_route_end_to_end(db_session) -> None:
    student1 = Student(student_no="9100", student_name="路由测试甲", class_name="1班")
    student2 = Student(student_no="9101", student_name="路由测试乙", class_name="1班")
    db_session.add_all([student1, student2])
    db_session.commit()

    batch_id = asyncio.run(
        _post_json(
            "/api/admin/batches",
            {"batch_name": "Merkle路由测试批次", "student_ids": [student1.student_id, student2.student_id]},
        )
    ).json()["data"]["batch_id"]

    generate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/generate"))
    assert generate_resp.json()["data"]["generated_count"] == 2

    missing_root_resp = asyncio.run(_get_json(f"/api/admin/batches/{batch_id}/merkle-root"))
    assert missing_root_resp.status_code == 404

    root_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/merkle-root"))
    assert root_resp.status_code == 200
    root_data = root_resp.json()["data"]
    assert root_data["batch_id"] == batch_id
    assert root_data["leaf_count"] == 2
    assert root_data["root_id"] == root_data["root_no"]
    assert root_data["leaf_order_rule"] == "CERTIFICATE_NO_ASC"
    assert root_data["odd_leaf_rule"] == "DUPLICATE_LAST"

    query_resp = asyncio.run(_get_json(f"/api/admin/batches/{batch_id}/merkle-root"))
    assert query_resp.status_code == 200
    assert query_resp.json()["data"] == root_data

    duplicate_resp = asyncio.run(_post_json(f"/api/admin/batches/{batch_id}/merkle-root"))
    assert duplicate_resp.status_code == 409

    certificate = db_session.query(Certificate).filter(Certificate.batch_id == batch_id).first()
    for path in (
        f"/api/verification/{certificate.certificate_no}/merkle-proof",
        f"/api/public/verify/{certificate.certificate_no}/merkle-proof",
    ):
        proof_resp = asyncio.run(_get_json(path))
        assert proof_resp.status_code == 200
        proof_data = proof_resp.json()["data"]
        assert proof_data["verified"] is True
        assert proof_data["proof_valid"] is True
        assert proof_data["merkle_root"] == root_data["merkle_root"]
        assert proof_data["root_id"] == root_data["root_id"]
        assert proof_data["leaf_count"] == root_data["leaf_count"]
        assert proof_data["current_root_hash"] == root_data["current_root_hash"]
        assert proof_data["previous_root_hash"] == root_data["previous_root_hash"]
        assert proof_data["tx_hash"] == root_data["tx_hash"]
        assert proof_data["merkle_proof"] == proof_data["proof"]


def test_merkle_root_route_404_for_unknown_batch(db_session) -> None:
    resp = asyncio.run(_post_json("/api/admin/batches/999999/merkle-root"))
    assert resp.status_code == 404


def test_merkle_proof_route_404_before_root_computed(db_session) -> None:
    student = Student(student_no="9200", student_name="无Root测试", class_name="1班")
    db_session.add(student)
    db_session.commit()
    certificate = certificate_service.generate_certificate(
        db_session, student_id=student.student_id, template=TEMPLATE, issue_date=datetime(2026, 7, 15)
    )

    resp = asyncio.run(_get_json(f"/api/verification/{certificate.certificate_no}/merkle-proof"))
    assert resp.status_code == 404
