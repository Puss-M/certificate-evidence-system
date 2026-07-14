"""
证书生成与本地哈希链存证 —— 7.14原型脚本

今日范围（对应任务清单 1-6项）：
1. 证书编号规则
2. 生成中文 PDF 证书样例（模拟数据）
3. 生成二维码，内容指向 verify_url
4. 对最终 PDF 计算 SHA-256
5. 生成本地哈希链回执
6. 输出样例 JSON，供 3 号（验真页）和 4 号（后端）对接字段

不包含：智能合约、FISCO BCOS、Merkle Root —— 按团队约定，这些今天只预留，不进入主实现。
后续会把这里跑通的逻辑整理进 backend/app/services/ 正式结构，今天先验证流程。
"""

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
import qrcode

# ---------------------------------------------------------------------------
# 基础配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs", "samples")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# reportlab 内置中文字体，不需要额外提供 ttf 字体文件，避免中文乱码
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

VERIFY_BASE_URL = "https://cert-evidence-system.local/verify"  # 演示用占位域名，部署时替换

# ---------------------------------------------------------------------------
# 模拟数据（不使用真实学生信息）
# ---------------------------------------------------------------------------
student = {
    "student_id": 1001,
    "student_no": "2023001",
    "student_name": "张三",
}
template = {
    "template_id": 1,
    "institution_name": "示范学院",
    "project_name": "软件开发暑期实训",
    "grade_level": "优秀",
}
batch_date = datetime(2026, 7, 14)


# ---------------------------------------------------------------------------
# 1. 证书编号规则：CERT-YYYYMMDD-序号
# ---------------------------------------------------------------------------
def generate_certificate_no(issue_date: datetime, seq: int) -> str:
    return f"CERT-{issue_date.strftime('%Y%m%d')}-{seq:04d}"


# ---------------------------------------------------------------------------
# 2. 生成二维码，内容为 verify_url
#    注意：必须先生成二维码，再生成 PDF，因为二维码图片要被画进 PDF 里，
#    不能等 PDF 生成完再回头补，顺序反了会导致 PDF 里没有二维码图案。
# ---------------------------------------------------------------------------
def generate_qrcode(certificate_no: str, output_dir: str) -> tuple:
    verify_url = f"{VERIFY_BASE_URL}/{certificate_no}"
    qr_path = os.path.join(output_dir, f"{certificate_no}_qrcode.png")
    img = qrcode.make(verify_url)
    img.save(qr_path)
    return qr_path, verify_url


# ---------------------------------------------------------------------------
# 3. 生成中文 PDF 证书，并把二维码图片实际画到 PDF 上
#    二维码同时也保留独立的 PNG 文件（qr_code_path），供系统单独展示/分享使用，
#    两者都要，不是二选一：PDF 里的二维码用于"拿到证书本身就能扫码"，
#    独立 PNG 用于系统里"只分享二维码、不分享整份 PDF"的场景。
# ---------------------------------------------------------------------------
def generate_pdf(certificate_no: str, student: dict, template: dict, issue_date: datetime,
                  qr_code_path: str, output_dir: str) -> str:
    pdf_path = os.path.join(output_dir, f"{certificate_no}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    c.setFont("STSong-Light", 26)
    c.drawCentredString(width / 2, height - 130, "结 业 证 书")

    c.setFont("STSong-Light", 13)
    lines = [
        f"姓名：{student['student_name']}　　学号：{student['student_no']}",
        "",
        f"经考核，已完成「{template['project_name']}」全部课程内容，",
        f"成绩等级：{template['grade_level']}，特发此证。",
        "",
        f"颁发机构：{template['institution_name']}",
        f"证书编号：{certificate_no}",
        f"颁发日期：{issue_date.strftime('%Y年%m月%d日')}",
    ]
    y = height - 210
    for line in lines:
        c.drawCentredString(width / 2, y, line)
        y -= 28

    # 把二维码图片画到证书右下角，尺寸约 2.2cm x 2.2cm
    qr_size = 62  # 单位：pt
    c.drawImage(
        qr_code_path,
        width - qr_size - 60,
        50,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.setFont("STSong-Light", 8)
    c.drawCentredString(width - qr_size / 2 - 60, 40, "扫码验真")

    c.setFont("STSong-Light", 8)
    c.drawString(60, 66, "本证书内容哈希已写入本地存证链。")
    c.drawString(60, 52, "（模拟数据，仅用于课程实训演示）")

    c.showPage()
    c.save()
    return pdf_path


# ---------------------------------------------------------------------------
# 4. 对最终 PDF 计算 SHA-256
# ---------------------------------------------------------------------------
def compute_sha256(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# 5. 本地哈希链回执
#    字段口径对齐 docs/协作管理/FISCO_BCOS与存证降级策略.md 第 3.1 / 3.2 节：
#    current_block_hash = SHA256(block_height + certificate_no + certificate_hash + previous_hash + evidence_time)
# ---------------------------------------------------------------------------
CHAIN_STATE_FILE = os.path.join(OUTPUT_DIR, ".local_chain_state.json")


def get_previous_hash() -> tuple:
    """读取本地哈希链当前状态：上一条记录哈希、当前链高度。"""
    if os.path.exists(CHAIN_STATE_FILE):
        with open(CHAIN_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state["current_block_hash"], state["block_height"]
    # 创世状态：链上还没有任何记录
    return "0" * 64, 0


def save_chain_state(current_block_hash: str, block_height: int) -> None:
    with open(CHAIN_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"current_block_hash": current_block_hash, "block_height": block_height}, f)


def generate_receipt(certificate_no: str, certificate_hash: str) -> dict:
    previous_hash, previous_height = get_previous_hash()
    block_height = previous_height + 1
    evidence_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    raw = f"{block_height}{certificate_no}{certificate_hash}{previous_hash}{evidence_time}"
    current_block_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    receipt_id = f"RCP-{datetime.now().strftime('%Y%m%d')}-{block_height:04d}"
    save_chain_state(current_block_hash, block_height)

    return {
        "receipt_id": receipt_id,
        "certificate_no": certificate_no,
        "certificate_hash": certificate_hash,
        "evidence_type": "LOCAL_HASH_CHAIN",
        "previous_hash": previous_hash,
        "current_block_hash": current_block_hash,
        "block_height": block_height,
        "evidence_time": evidence_time,
        "status": "CONFIRMED",
    }


# ---------------------------------------------------------------------------
# 单张证书生成的完整流程（编号由调用方生成），main() 和批量生成脚本
# （certificate_batch.py）共用同一份逻辑，避免两边各写一遍容易走样。
# ---------------------------------------------------------------------------
def generate_certificate_record(certificate_no: str, student: dict, template: dict,
                                 issue_date: datetime, output_dir: str) -> dict:
    # 顺序很重要：先出二维码，再把二维码画进PDF，最后对成品PDF算哈希
    qr_code_path, verify_url = generate_qrcode(certificate_no, output_dir)
    pdf_path = generate_pdf(certificate_no, student, template, issue_date, qr_code_path, output_dir)
    certificate_hash = compute_sha256(pdf_path)
    receipt = generate_receipt(certificate_no, certificate_hash)

    # 字段命名对齐 docs/协作管理/接口规范.md 的字段字典，方便 3 号/4 号直接对接
    return {
        "certificate_no": certificate_no,
        "student_id": student["student_id"],
        "student_name": student["student_name"],
        "pdf_path": os.path.relpath(pdf_path, start=PROJECT_ROOT),
        "qr_code_path": os.path.relpath(qr_code_path, start=PROJECT_ROOT),
        "verify_url": verify_url,
        "certificate_hash": certificate_hash,
        "receipt_id": receipt["receipt_id"],
        "status": "VALID",
        "credential_type": "CERTIFICATE",
        "chain_receipt": receipt,
    }


# ---------------------------------------------------------------------------
# 主流程：串联 1-6 步，输出样例 JSON（单张示例，学号1001张三）
# ---------------------------------------------------------------------------
def main():
    certificate_no = generate_certificate_no(batch_date, seq=1)
    sample_output = generate_certificate_record(certificate_no, student, template, batch_date, OUTPUT_DIR)

    json_path = os.path.join(OUTPUT_DIR, f"{certificate_no}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sample_output, f, ensure_ascii=False, indent=2)

    print("生成完成，产物路径：")
    print(f"  PDF     : {os.path.join(PROJECT_ROOT, sample_output['pdf_path'])}")
    print(f"  二维码  : {os.path.join(PROJECT_ROOT, sample_output['qr_code_path'])}")
    print(f"  样例JSON: {json_path}")
    print()
    print("样例JSON内容：")
    print(json.dumps(sample_output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
