"""
证书验真原型 —— 7.14原型脚本（扩展，对应任务清单 3.3）

重点解决之前讨论过的关键缺口：仅凭证书编号查询（扫码/输入编号）只能证明
"系统里存在这个编号"，不能证明"手上这份PDF文件没被改过"——必须现场对
上传的文件重新计算哈希，和存证时记录的 certificate_hash 比对，这才是
真正防篡改的一步。

本原型用 outputs/samples/ 下已生成的证书JSON文件模拟"数据库"，
真实实现里这里应该改成查 certificates 表 + 存证回执表（4号的数据库骨架）。

验真结果覆盖 docs/协作管理/接口规范.md 第8节定义的六种状态：
PASS / REVOKED / HASH_MISMATCH / NOT_FOUND / NO_RECEIPT / SYSTEM_ERROR
"""

import glob
import json
import os

from certificate_prototype import OUTPUT_DIR, PROJECT_ROOT, compute_sha256


def _load_all_records() -> dict:
    """把 outputs/samples/ 下所有单张证书JSON当成模拟数据库读进来，按 certificate_no 建索引。"""
    records = {}
    for path in glob.glob(os.path.join(OUTPUT_DIR, "CERT-*.json")):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        records[record["certificate_no"]] = record
    return records


def verify_by_certificate_no(certificate_no: str) -> dict:
    """弱验证：仅按编号查询（扫码/输入编号场景），不校验文件本身是否被篡改。"""
    try:
        record = _load_all_records().get(certificate_no)
        if record is None:
            return {"certificate_no": certificate_no, "verify_result": "NOT_FOUND"}
        if record.get("status") == "REVOKED":
            return {"certificate_no": certificate_no, "verify_result": "REVOKED", "status": "REVOKED"}
        if not record.get("chain_receipt"):
            return {"certificate_no": certificate_no, "verify_result": "NO_RECEIPT"}
        return {
            "certificate_no": certificate_no,
            "verify_result": "PASS",
            "status": record["status"],
            "certificate_hash": record["certificate_hash"],
            "receipt_id": record["receipt_id"],
        }
    except Exception as exc:
        # 演示用途：真实实现里要记录日志，而不是简单吞掉异常
        return {"certificate_no": certificate_no, "verify_result": "SYSTEM_ERROR", "error": str(exc)}


def verify_by_file(certificate_no: str, uploaded_file_path: str) -> dict:
    """强验证：上传PDF复验，现场计算哈希、和存证的 certificate_hash 比对。"""
    try:
        record = _load_all_records().get(certificate_no)
        if record is None:
            return {"certificate_no": certificate_no, "verify_result": "NOT_FOUND"}
        if record.get("status") == "REVOKED":
            return {"certificate_no": certificate_no, "verify_result": "REVOKED", "status": "REVOKED"}
        if not record.get("chain_receipt"):
            return {"certificate_no": certificate_no, "verify_result": "NO_RECEIPT"}

        uploaded_hash = compute_sha256(uploaded_file_path)
        stored_hash = record["certificate_hash"]
        hash_match = uploaded_hash == stored_hash

        return {
            "certificate_no": certificate_no,
            "verify_result": "PASS" if hash_match else "HASH_MISMATCH",
            "hash_match": hash_match,
            "uploaded_hash": uploaded_hash,
            "stored_hash": stored_hash,
            "receipt_id": record["receipt_id"],
        }
    except Exception as exc:
        return {"certificate_no": certificate_no, "verify_result": "SYSTEM_ERROR", "error": str(exc)}


def _try_remove(path: str) -> None:
    """清理演示/临时文件；某些沙箱环境对特定挂载目录会拒绝删除权限，
    这不影响验真逻辑本身，失败时只提示一下，不让整个演示脚本崩掉。"""
    try:
        os.remove(path)
    except OSError as exc:
        print(f"（提示：清理临时文件 {os.path.basename(path)} 失败，可忽略：{exc}）")


def _make_tampered_copy(original_path: str) -> str:
    """演示/测试用：复制一份PDF并翻转最后一个字节，模拟被篡改过的文件。"""
    tampered_path = original_path.replace(".pdf", "_tampered.pdf")
    with open(original_path, "rb") as f:
        data = bytearray(f.read())
    data[-1] ^= 0xFF
    with open(tampered_path, "wb") as f:
        f.write(data)
    return tampered_path


def _demo_revoked_scenario(sample_record: dict) -> None:
    """撤销接口（任务清单3.5）今天还没做，这里手动构造一条 REVOKED 记录，
    单独验证 REVOKED 这一分支的判断逻辑是对的，跑完立刻清理，不污染样例数据。"""
    revoked_no = "CERT-20260714-8888"
    revoked_record = dict(sample_record)
    revoked_record["certificate_no"] = revoked_no
    revoked_record["status"] = "REVOKED"
    revoked_path = os.path.join(OUTPUT_DIR, f"{revoked_no}.json")
    with open(revoked_path, "w", encoding="utf-8") as f:
        json.dump(revoked_record, f, ensure_ascii=False, indent=2)

    print("\n5) 模拟撤销场景 verify_by_certificate_no（应为 REVOKED）：")
    print(json.dumps(verify_by_certificate_no(revoked_no), ensure_ascii=False, indent=2))

    _try_remove(revoked_path)


def main():
    records = _load_all_records()
    if not records:
        print("outputs/samples/ 下没有找到证书JSON，请先运行 certificate_prototype.py 生成样例数据。")
        return

    sample_no = next(iter(records))
    sample_record = records[sample_no]
    sample_pdf = os.path.abspath(os.path.join(PROJECT_ROOT, sample_record["pdf_path"]))

    print(f"用样例证书 {sample_no} 演示验真的几种场景：")

    print("\n1) 编号验真 verify_by_certificate_no（弱验证，应为 PASS）：")
    print(json.dumps(verify_by_certificate_no(sample_no), ensure_ascii=False, indent=2))

    print("\n2) 上传原始PDF复验 verify_by_file（应为 PASS，hash_match=true）：")
    print(json.dumps(verify_by_file(sample_no, sample_pdf), ensure_ascii=False, indent=2))

    print("\n3) 上传被篡改PDF复验 verify_by_file（应为 HASH_MISMATCH）：")
    tampered_path = _make_tampered_copy(sample_pdf)
    print(json.dumps(verify_by_file(sample_no, tampered_path), ensure_ascii=False, indent=2))
    _try_remove(tampered_path)  # 演示文件，用完清理

    print("\n4) 查询不存在的编号（应为 NOT_FOUND）：")
    print(json.dumps(verify_by_certificate_no("CERT-20260714-9999"), ensure_ascii=False, indent=2))

    _demo_revoked_scenario(sample_record)


if __name__ == "__main__":
    main()
