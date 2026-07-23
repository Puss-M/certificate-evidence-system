"""
证书生成服务（对应任务清单 3.1 / 3.4）

这是 backend/prototype/certificate_prototype.py、certificate_batch.py 里已经跑通验证过的
证书生成 + 本地哈希链存证逻辑，正式迁移进 app/services/，改成直接读写数据库：

- 证书编号的序号不再由调用方手写，而是查 certificates 表里当天已有的最大编号
- 哈希链的 previous_hash / block_height 不再依赖本地 .local_chain_state.json 文件，
  改成查 evidence_receipts 表里 block_height 最大的一条记录（全局递增，不分批次）
- 每次生成都会往 certificates 表插入一行证书记录、往 evidence_receipts 表插入一行回执记录，
  两者通过 certificate_id（外键）关联，Certificate.receipt_id 存的是回执的业务编号
  （evidence_receipts.receipt_no），不是回执表的自增主键，这一点容易搞混，多留意。
- 证书编号、回执的 block_height 都是"先查最大值再+1"，并发下两个请求可能读到同一个
  最大值、算出同一个编号——这种情况数据库的唯一约束会挡住其中一个，报 IntegrityError，
  不会导致编号重复或哈希链错乱。generate_certificate() 会在这种冲突下自动重试。

不包含：Merkle Root（P2 加分项，另有方案文档，这里先不接）。
"""

import hashlib
import io
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from PIL import Image
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import qrcode

from app.models.certificate import Certificate, CertificateStatus
from app.models.evidence_receipt import EvidenceReceipt
from app.models.student import Student
from app.core.config import settings
from app.services.template_service import DEFAULT_FIELDS


# ---------------------------------------------------------------------------
# 基础配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "certificates"

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
_FONT = "STSong-Light"

VERIFY_BASE_URL = "https://cert-evidence-system.local/verify"  # 演示用占位域名，部署时替换

# 证书编号 / 回执 block_height 是"查最大值+1"，并发冲突时靠重试解决，这是重试上限
MAX_GENERATE_ATTEMPTS = 5

# 导师签章图片固定长宽比（宽:高），上传的图片比例不符就居中裁剪成这个比例，
# 见 load_and_crop_signature()。
MENTOR_SIGNATURE_RATIO = 4.0

# 证书视觉设计的配色（对应 frontend/src/styles/global.css 里 .certificate-border
# 等类目前的"证书模板预览"效果图——这是目前唯一的设计基准，PDF生成要往这个
# 效果对齐，而不是各画各的）。
_GOLD = Color(182 / 255, 139 / 255, 63 / 255)
_TITLE_COLOR = Color(114 / 255, 83 / 255, 31 / 255)
_META_COLOR = Color(96 / 255, 87 / 255, 71 / 255)
_SEAL_COLOR = Color(199 / 255, 72 / 255, 58 / 255)
_YEAR_COLOR = Color(162 / 255, 124 / 255, 58 / 255)
_TEXT_COLOR = Color(0.06, 0.09, 0.16)

# 证书页面比例——对应"证书模板预览"CSS里 .certificate-border 实际渲染出来的
# 比例（抽屉宽680px、内容区约600px、min-height 470px，约 600:470 ≈ 1.28:1），
# 不是信纸/A4那种更细长（约1.41:1）的比例，之前用 landscape(A4) 是错的。
_PAGE_WIDTH = 740.0
_PAGE_HEIGHT = 578.0


def _build_verify_url(certificate_no: str) -> str:
    return f"{settings.public_verify_base_url.rstrip('/')}/{certificate_no}"


# ---------------------------------------------------------------------------
# 证书编号：查数据库里今天已有的最大编号，取下一个序号
# ---------------------------------------------------------------------------
def _next_certificate_no(db: Session, issue_date: datetime) -> str:
    date_str = issue_date.strftime("%Y%m%d")
    prefix = f"CERT-{date_str}-"

    max_no = db.query(func.max(Certificate.certificate_no)).filter(
        Certificate.certificate_no.like(f"{prefix}%")
    ).scalar()

    if max_no is None:
        next_seq = 1
    else:
        next_seq = int(max_no.split("-")[-1]) + 1

    return f"{prefix}{next_seq:04d}"


# ---------------------------------------------------------------------------
# 二维码 + PDF 生成。这两个函数现在只管"往指定路径写文件"，具体用什么文件名
# 由调用方（generate_certificate）决定——生成阶段用临时文件名，落库成功后
# 才改名成正式的 {certificate_no} 文件名，原因见 generate_certificate 里的注释。
# ---------------------------------------------------------------------------
def _generate_qrcode(verify_url: str, qr_path: Path) -> None:
    img = qrcode.make(verify_url)
    img.save(qr_path)


def load_and_crop_signature(file_bytes: bytes, *, target_ratio: float = MENTOR_SIGNATURE_RATIO) -> Image.Image:
    """
    导师签章图片固定宽:高=4:1（MENTOR_SIGNATURE_RATIO）。上传的图片比例不符，
    居中裁剪成这个比例（不是缩放拉伸变形，也不是加白边）——裁多余的边，保留
    图片中间部分。这张图只在当次批量生成里用，不落库、不关联模板，见
    certificate_batches.generate_batch_with_signature()。
    """
    image = Image.open(io.BytesIO(file_bytes))
    image = image.convert("RGBA")
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("签章图片尺寸无效")

    current_ratio = width / height
    if current_ratio > target_ratio:
        new_width = max(1, round(height * target_ratio))
        left = (width - new_width) // 2
        image = image.crop((left, 0, left + new_width, height))
    elif current_ratio < target_ratio:
        new_height = max(1, round(width / target_ratio))
        top = (height - new_height) // 2
        image = image.crop((0, top, width, top + new_height))
    return image


def _draw_spaced_centered(c: canvas.Canvas, text: str, center_x: float, y: float,
                           font_size: float, extra_space: float, color: Color) -> None:
    """带字间距的居中文字——参考设计里标题、'年份·CERTIFICATE'这类大字都是
    letter-spacing拉开的，reportlab没有现成的letter-spacing参数，手动按字符
    宽度累加着画。"""
    if not text:
        return
    c.setFont(_FONT, font_size)
    c.setFillColor(color)
    widths = [pdfmetrics.stringWidth(ch, _FONT, font_size) for ch in text]
    total = sum(widths) + extra_space * max(len(text) - 1, 0)
    x = center_x - total / 2
    for ch, w in zip(text, widths):
        c.drawString(x, y, ch)
        x += w + extra_space


def _wrap_cjk_text(text: str, font_size: float, max_width: float) -> list[str]:
    """按字符宽度手动换行——中文不能按空格分词，用stringWidth逐字累加，
    超过可用宽度就换行。"""
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if current and pdfmetrics.stringWidth(trial, _FONT, font_size) > max_width:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _generate_pdf(
    certificate_no: str,
    student: Student,
    template: dict,
    issue_date: datetime,
    qr_code_path: Path | BinaryIO,
    pdf_path: Path | BinaryIO,
    *,
    mentor_signature_image: Image.Image | None = None,
) -> None:
    """
    证书视觉设计对齐"证书模板预览"效果图（frontend/src/styles/global.css的
    .certificate-border系列样式）：金色双线边框、纯白底、衬线大标题、称谓、
    正文、两栏信息、footer机构+日期+导师签章、印章盖在footer文字上（不再
    压二维码）、右下角二维码。

    template 固定接受这几项：template_name（不上版面，只做下载文件名用，见
    admin.download_certificate）、institution_name、course_name、project_name、
    certificate_title、issue_year、content——其中 content 允许为空，为空就跳过
    整段正文不画。template['fields'] 决定学生姓名/证书编号/成绩等级/导师签章/
    签发日期/验真二维码这6项要不要画：没在fields里，或者对应的值本身是空的，
    这一行/这个元素就整个跳过（不留占位空白，紧跟着后面的内容走）。
    """
    fields = template.get("fields") or DEFAULT_FIELDS

    def enabled(field_name: str) -> bool:
        return field_name in fields

    page_size = (_PAGE_WIDTH, _PAGE_HEIGHT)
    width, height = page_size
    dest = str(pdf_path) if isinstance(pdf_path, Path) else pdf_path
    c = canvas.Canvas(dest, pagesize=page_size)

    # ---- 金色双线边框（对应 CSS 的 border:8px double） ----
    outer_margin = 32
    border_gap = 6
    c.setStrokeColor(_GOLD)
    c.setLineWidth(1.3)
    c.rect(outer_margin, outer_margin, width - 2 * outer_margin, height - 2 * outer_margin, stroke=1, fill=0)
    inner_margin = outer_margin + border_gap
    c.rect(inner_margin, inner_margin, width - 2 * inner_margin, height - 2 * inner_margin, stroke=1, fill=0)
    # 内部背景固定纯白（不再是偏黄的米色），画布默认就是白底，这里不需要额外填色。

    content_left = inner_margin + 44
    content_right = width - inner_margin - 44
    content_width = content_right - content_left
    center_x = width / 2

    # ---- 字号/行距整体调大一档：之前整块内容缩在画面上方，字也偏小，
    # 下面留了一大截空白——用户反馈"看到太空了都能加大一下字号"。----
    CAPTION_FONT, CAPTION_GAP = 12, 42
    TITLE_FONT, TITLE_GAP = 34, 56
    SALUTATION_FONT, SALUTATION_GAP = 16, 36
    BODY_FONT, BODY_LINE_H, BODY_PARA_GAP = 14, 23, 10
    META_FONT, META_ROW_GAP, GAP_AFTER_META = 13, 25, 18
    FOOTER_NAME_FONT, FOOTER_META_FONT, FOOTER_GAP = 16, 13, 25

    # STSong-Light（Adobe-GB1 CID字体）不认U+00B7这个西文中点，字形会变成方框
    # 缺字符号——这里用日文假名的中点U+30FB代替，视觉上跟CSS设计里的"·"一致，
    # 而且这个字符在这个CID字体里确实有字形（已经用glyph_test.pdf验证过）。
    issue_year = template.get("issue_year") or str(issue_date.year)
    title = template.get("certificate_title") or "实训结业证书"
    show_salutation = enabled("student_name") and bool(student.student_name)

    content_text = (template.get("content") or "").strip()
    wrapped_lines: list[str] = []
    if content_text:
        for paragraph in content_text.split("\n"):
            wrapped_lines.extend(_wrap_cjk_text("　　" + paragraph, BODY_FONT, content_width))

    meta_columns = (content_left, center_x + 8)
    row1 = [(label, value) for label, value in (
        ("课程", template.get("course_name") or ""),
        ("项目", template.get("project_name") or ""),
    ) if value]
    row2 = [(label, value) for label, value in (
        ("成绩等级", template.get("grade_level") or "" if enabled("grade_level") else ""),
        ("证书编号", certificate_no if enabled("certificate_no") else ""),
    ) if value]

    institution_name = template.get("institution_name") or ""
    show_institution = bool(institution_name)
    show_issue_date = enabled("issue_date")
    show_mentor_sig = enabled("mentor_signature")

    def run_layout(start_y: float, draw: bool) -> tuple[float, float]:
        """走一遍从年份/标题到footer的完整版面流程。draw=False 时只挪
        y坐标、不真的落笔——用来预先量出整块内容的总高度，再据此把
        整块内容在画面里上下居中，而不是永远死贴着上边缘。返回
        (last_y, footer_top)：last_y 是最后一个实际画出的元素的y坐标
        （dry run时用来算总高度），footer_top 是机构名那一行的y坐标
        （画印章要用）。"""
        y = start_y
        last_y = y
        footer_top = y

        if draw:
            _draw_spaced_centered(c, f"{issue_year} ・ CERTIFICATE", center_x, y, CAPTION_FONT, 3, _YEAR_COLOR)
        last_y = y
        y -= CAPTION_GAP

        if draw:
            _draw_spaced_centered(c, title, center_x, y, TITLE_FONT, 10, _TITLE_COLOR)
        last_y = y
        y -= TITLE_GAP

        if show_salutation:
            if draw:
                c.setFont(_FONT, SALUTATION_FONT)
                c.setFillColor(_TEXT_COLOR)
                c.drawString(content_left, y, f"{student.student_name} 同学：")
            last_y = y
            y -= SALUTATION_GAP

        if wrapped_lines:
            if draw:
                c.setFont(_FONT, BODY_FONT)
                c.setFillColor(_TEXT_COLOR)
            for wline in wrapped_lines:
                if draw:
                    c.drawString(content_left, y, wline)
                last_y = y
                y -= BODY_LINE_H
            y -= BODY_PARA_GAP

        if row1:
            if draw:
                c.setFont(_FONT, META_FONT)
                c.setFillColor(_META_COLOR)
                for index, (label, value) in enumerate(row1):
                    x = meta_columns[index] if index < len(meta_columns) else meta_columns[-1]
                    c.drawString(x, y, f"{label}：{value}")
            last_y = y
            y -= META_ROW_GAP
        if row2:
            if draw:
                c.setFont(_FONT, META_FONT)
                c.setFillColor(_META_COLOR)
                for index, (label, value) in enumerate(row2):
                    x = meta_columns[index] if index < len(meta_columns) else meta_columns[-1]
                    c.drawString(x, y, f"{label}：{value}")
            last_y = y
            y -= META_ROW_GAP
        if row1 or row2:
            y -= GAP_AFTER_META

        footer_top = y

        if show_institution:
            if draw:
                c.setFont(_FONT, FOOTER_NAME_FONT)
                c.setFillColor(_TEXT_COLOR)
                c.drawString(content_left, y, institution_name)
            last_y = y
            y -= FOOTER_GAP

        if show_issue_date:
            if draw:
                c.setFont(_FONT, FOOTER_META_FONT)
                c.setFillColor(_META_COLOR)
                c.drawString(content_left, y, issue_date.strftime("%Y年%m月%d日"))
            last_y = y
            y -= FOOTER_GAP

        if show_mentor_sig:
            label = "导师签章："
            label_width = pdfmetrics.stringWidth(label, _FONT, FOOTER_META_FONT)
            line_start = content_left + label_width + 4
            line_end = content_left + 210
            if draw:
                c.setFont(_FONT, FOOTER_META_FONT)
                c.setFillColor(_META_COLOR)
                c.drawString(content_left, y, label)
                if mentor_signature_image is not None:
                    sig_height = 22
                    sig_width = sig_height * MENTOR_SIGNATURE_RATIO
                    c.drawImage(
                        ImageReader(mentor_signature_image),
                        line_start,
                        y - 3,
                        width=min(sig_width, line_end - line_start),
                        height=sig_height,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                c.setStrokeColor(_META_COLOR)
                c.setLineWidth(0.6)
                c.line(line_start, y - 3, line_end, y - 3)
            last_y = y

        return last_y, footer_top

    # ---- 先量一遍总高度，把整块内容（年份/标题到footer）在画面里上下
    # 居中——不然内容一少，就全堆在画面上方，下面空一大截。左右方向本来
    # 就是 content_left/content_right 对称留白，天然居中，不用再处理。----
    frame_top = height - inner_margin
    frame_bottom = inner_margin
    dry_last_y, _ = run_layout(0.0, draw=False)
    block_span = -dry_last_y  # 从起笔到最后一个元素之间的总高度
    start_y = (frame_top + frame_bottom + block_span) / 2
    start_y = min(start_y, frame_top - 34)  # 内容特别多时至少留34pt顶部呼吸空间

    last_y, footer_top = run_layout(start_y, draw=True)

    # 印章：机构名第一个字，双线圆环，半透明，盖在footer文字上（不再压二维码，
    # 挪到左下角，跟CSS里 position:absolute;right:42px;bottom:35px 的效果
    # 对应，只是位置换成左边）。
    if show_institution:
        seal_char = institution_name[0]
        seal_cx = content_left + 68
        seal_cy = footer_top - 6
        c.saveState()
        c.setStrokeColor(_SEAL_COLOR)
        c.setFillColor(_SEAL_COLOR)
        try:
            c.setStrokeAlpha(0.75)
            c.setFillAlpha(0.75)
        except AttributeError:
            pass  # 极少数老版本reportlab没有alpha支持，退化成不透明也能接受
        c.setLineWidth(1.8)
        c.circle(seal_cx, seal_cy, 32, stroke=1, fill=0)
        c.circle(seal_cx, seal_cy, 26, stroke=1, fill=0)
        c.setFont(_FONT, 26)
        c.drawCentredString(seal_cx, seal_cy - 9, seal_char)
        c.restoreState()

    if enabled("qr_code"):
        qr_size = 72
        qr_x = content_right - qr_size
        # 二维码跟footer最后一行基本齐平（而不是死死焊在画面绝对底部），
        # 这样footer整体上移变化时二维码始终跟它保持在同一视觉高度上。
        qr_y = max(inner_margin + 20, last_y - 6)
        c.drawImage(
            ImageReader(qr_code_path),
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )
        c.setFont(_FONT, 8.5)
        c.setFillColor(_META_COLOR)
        c.drawCentredString(qr_x + qr_size / 2, qr_y - 14, "扫码验真")

    c.showPage()
    c.save()


def _compute_sha256(file_path: str) -> str:
    last_error: PermissionError | None = None
    for _ in range(10):
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to compute SHA-256 for {file_path}")


# ---------------------------------------------------------------------------
# 本地哈希链回执：查数据库里 block_height 最大的一条记录作为"上一条"，
# 不再依赖本地文件。这样多个请求/多个部署实例并发生成证书时，
# 链的顺序由数据库保证，不会因为本地文件不同步而错乱。
# ---------------------------------------------------------------------------
def _create_evidence_receipt(db: Session, certificate_id: int, certificate_no: str,
                              certificate_hash: str) -> EvidenceReceipt:
    last_receipt = db.query(EvidenceReceipt).order_by(
        EvidenceReceipt.block_height.desc()
    ).first()

    if last_receipt is None:
        previous_hash = "0" * 64
        block_height = 1
    else:
        previous_hash = last_receipt.current_block_hash
        block_height = last_receipt.block_height + 1

    evidence_time = datetime.utcnow()
    evidence_time_str = evidence_time.strftime("%Y-%m-%d %H:%M:%S")

    raw = f"{block_height}{certificate_no}{certificate_hash}{previous_hash}{evidence_time_str}"
    current_block_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    receipt_no = f"RCP-{evidence_time.strftime('%Y%m%d')}-{block_height:04d}"

    receipt = EvidenceReceipt(
        receipt_no=receipt_no,
        certificate_id=certificate_id,
        certificate_hash=certificate_hash,
        previous_hash=previous_hash,
        current_block_hash=current_block_hash,
        block_height=block_height,
        evidence_time=evidence_time,
        chain_type="LOCAL_HASH_CHAIN",
    )
    db.add(receipt)
    db.flush()
    return receipt


# ---------------------------------------------------------------------------
# 单张证书生成的完整流程：编号 -> 二维码 -> PDF -> 哈希 -> 存证回执 -> 写入数据库
# ---------------------------------------------------------------------------
def _normalise_int_id(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _normalise_template_id(template: dict) -> int | None:
    return _normalise_int_id(template.get("template_id"))


def generate_certificate(
    db: Session,
    *,
    student_id: int,
    template: dict,
    issue_date: datetime,
    batch_id: int | str | None = None,
    output_dir: Path | None = None,
    previous_certificate_no: str | None = None,
    mentor_signature_image: Image.Image | None = None,
) -> Certificate:
    student = db.get(Student, student_id)
    if student is None:
        raise ValueError(f"student_id={student_id} 不存在，请先确认学生数据已导入")

    target_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(target_dir, exist_ok=True)

    last_error: IntegrityError | None = None

    for _ in range(MAX_GENERATE_ATTEMPTS):
        certificate_no = _next_certificate_no(db, issue_date)
        verify_url = _build_verify_url(certificate_no)

        # 先写到跟 certificate_no 无关的临时文件名，落库成功后才改名成正式的
        # {certificate_no} 文件名。这一点很关键：如果直接用 certificate_no 当
        # 文件名生成，一旦这次因为并发冲突要重试，这次生成的文件会和"已经赢了
        # 这个编号"的那次证书同名，重试时的 PDF 内容会把对方的文件覆盖掉，
        # 失败后再删除又会把对方刚生成好的文件一起删掉——用临时文件名可以完全
        # 避免这种"重试把别人的证书文件冲掉"的情况。
        temp_token = uuid.uuid4().hex[:8]
        temp_qr_path = target_dir / f".tmp-{temp_token}-qrcode.png"
        temp_pdf_path = target_dir / f".tmp-{temp_token}.pdf"

        _generate_qrcode(verify_url, temp_qr_path)
        _generate_pdf(
            certificate_no, student, template, issue_date, temp_qr_path, temp_pdf_path,
            mentor_signature_image=mentor_signature_image,
        )
        certificate_hash = _compute_sha256(str(temp_pdf_path))

        final_qr_path = target_dir / f"{certificate_no}_qrcode.png"
        final_pdf_path = target_dir / f"{certificate_no}.pdf"

        certificate = Certificate(
            certificate_no=certificate_no,
            student_id=student.student_id,
            student_name=student.student_name,
            batch_id=_normalise_int_id(batch_id),
            template_id=_normalise_template_id(template),
            project_name=template.get("project_name") or "软件开发实训",
            institution_name=template.get("institution_name"),
            issue_time=issue_date,
            pdf_path=os.path.relpath(final_pdf_path, start=PROJECT_ROOT),
            certificate_hash=certificate_hash,
            qr_code_path=os.path.relpath(final_qr_path, start=PROJECT_ROOT),
            verify_url=verify_url,
            status=CertificateStatus.VALID.value,
            credential_type="CERTIFICATE",
            previous_certificate_no=previous_certificate_no,
        )

        try:
            db.add(certificate)
            db.flush()  # 拿到 certificate.certificate_id，供回执表外键关联

            receipt = _create_evidence_receipt(db, certificate.certificate_id, certificate_no, certificate_hash)
            certificate.receipt_id = receipt.receipt_no  # 存的是回执业务编号，不是回执表自增主键

            db.commit()
            db.refresh(certificate)

            # 落库成功、编号确定不会再跟别人冲突之后，才把临时文件改名成正式文件名。
            # 这里用 replace 而不是 rename：测试或演示环境经常会清空数据库但保留
            # outputs/certificates 目录，导致同一个 certificate_no 的旧文件仍在磁盘上。
            # 数据库唯一约束已经保证当前编号归这次成功生成所有，因此可以安全覆盖这种
            # 没有数据库记录引用的陈旧产物。
            temp_pdf_path.replace(final_pdf_path)
            temp_qr_path.replace(final_qr_path)

            return certificate
        except IntegrityError as exc:
            # 并发下两个请求可能算出同一个 certificate_no 或同一个 block_height，
            # 数据库唯一约束会挡住其中一个——回滚、丢掉这次生成的临时文件，换个号重试。
            db.rollback()
            last_error = exc
            for stray_path in (temp_pdf_path, temp_qr_path):
                try:
                    stray_path.unlink(missing_ok=True)
                except OSError:
                    pass  # 清理失败不影响重试，最多留一份没被数据库引用的临时文件

    raise RuntimeError(
        f"生成证书失败：并发冲突重试 {MAX_GENERATE_ATTEMPTS} 次仍未成功"
    ) from last_error


# ---------------------------------------------------------------------------
# 批量生成：对一批 student_id 依次调用 generate_certificate，
# 每张证书仍然各自完整走一遍流程，哈希链在数据库层面保持全局递增、逐条相连。
# ---------------------------------------------------------------------------
def generate_certificate_batch(
    db: Session,
    *,
    student_ids: list[int],
    template: dict,
    issue_date: datetime,
    batch_id: int | str | None,
    output_dir: Path | None = None,
    mentor_signature_image: Image.Image | None = None,
) -> list[Certificate]:
    return [
        generate_certificate(
            db,
            student_id=student_id,
            template=template,
            issue_date=issue_date,
            batch_id=batch_id,
            output_dir=output_dir,
            mentor_signature_image=mentor_signature_image,
        )
        for student_id in student_ids
    ]


# ---------------------------------------------------------------------------
# 证书模板预览：给"证书模板管理"页面的预览抽屉用真实生成逻辑渲染一份示例PDF，
# 不再是前端写死假数据的CSS效果图。用固定的示例数据（张三同学、示例证书编号），
# 不落库、不占用真实的证书编号序列，也不消耗回执链的block_height。字段是否
# 显示完全走 template['fields']，跟真实生成时的规则一致——没勾选的字段这里
# 也不会出现，跟"不选择什么字段就会留空"的预期行为对齐。
# ---------------------------------------------------------------------------
class _PreviewStudent:
    """预览用的示例学生数据，故意不用真的 Student ORM 实例（不需要、也不应该
    往数据库里插一条假学生记录），_generate_pdf 只读 student_name 这一个属性。"""

    student_name = "张三"
    student_no = "S20260000"


def render_certificate_preview(template: dict) -> bytes:
    demo_certificate_no = "CERT-20260714-0001"
    demo_issue_date = datetime.utcnow()
    demo_template = {**template, "grade_level": template.get("grade_level") or "优秀"}

    qr_buffer = io.BytesIO()
    qrcode.make(f"preview-{demo_certificate_no}").save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf_buffer = io.BytesIO()
    _generate_pdf(
        demo_certificate_no,
        _PreviewStudent(),
        demo_template,
        demo_issue_date,
        qr_buffer,
        pdf_buffer,
        mentor_signature_image=None,
    )
    return pdf_buffer.getvalue()
