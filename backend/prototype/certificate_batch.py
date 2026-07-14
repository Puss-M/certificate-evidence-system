"""
批量证书生成 —— 7.14原型脚本（扩展，对应任务清单 3.1）

在 certificate_prototype.py 单张生成逻辑基础上，支持一批学生数据一次性生成证书。
每张证书仍然各自走一遍完整流程：编号 -> 二维码 -> PDF -> 哈希 -> 本地哈希链回执，
本地哈希链是全局递增的（block_height 跨证书连续），这是"链"本身的要求——
每一条回执都要接上前一条的哈希，不能因为是"同一批"就跳过链式关联。

不包含：批次级 Merkle Root（P2 加分项，方案已经写在
docs/协作管理/数据库设计.md 第9节 / FISCO_BCOS与存证降级策略.md 第8节，这里先不实现）。

注意：证书编号里的序号目前是脚本里手写的，真实实现应该由数据库按
batch_id 查询"今天已经发到第几号"，而不是像这里一样手动指定 seq，
这一点在 PR 描述里会标注成待确认项，等4号的数据库骨架出来后再对接。
"""

import json
import os
from datetime import datetime

from certificate_prototype import (
    OUTPUT_DIR,
    PROJECT_ROOT,
    generate_certificate_no,
    generate_certificate_record,
)

# 模拟批次学生数据（不使用真实学生信息），序号从2开始，
# 避开 certificate_prototype.py 单张示例已经占用的 CERT-20260714-0001
BATCH_STUDENTS = [
    {"student_id": 1002, "student_no": "2023002", "student_name": "李四"},
    {"student_id": 1003, "student_no": "2023003", "student_name": "王五"},
    {"student_id": 1004, "student_no": "2023004", "student_name": "赵六"},
]

TEMPLATE = {
    "template_id": 1,
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}


def generate_batch(students: list, template: dict, issue_date: datetime,
                    batch_id: str, start_seq: int = 2) -> list:
    """依次为批次内每个学生生成一张证书，返回每张证书的完整记录列表。"""
    records = []
    for offset, stu in enumerate(students):
        certificate_no = generate_certificate_no(issue_date, seq=start_seq + offset)
        record = generate_certificate_record(certificate_no, stu, template, issue_date, OUTPUT_DIR)
        record["batch_id"] = batch_id
        records.append(record)
    return records


def main():
    batch_id = "BATCH-20260714-0001"
    issue_date = datetime(2026, 7, 14)

    records = generate_batch(BATCH_STUDENTS, TEMPLATE, issue_date, batch_id)

    batch_summary = {
        "batch_id": batch_id,
        "issue_date": issue_date.strftime("%Y-%m-%d"),
        "certificate_count": len(records),
        "certificates": records,
    }

    batch_json_path = os.path.join(OUTPUT_DIR, f"{batch_id}.json")
    with open(batch_json_path, "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, ensure_ascii=False, indent=2)

    print(f"批量生成完成，共 {len(records)} 张证书")
    for r in records:
        print(f"  {r['certificate_no']}  {r['student_name']:<4} certificate_hash={r['certificate_hash'][:16]}...")
    print(f"批次汇总: {os.path.relpath(batch_json_path, start=PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
