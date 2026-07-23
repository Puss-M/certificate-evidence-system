import ast
import json
from typing import Any

from app.models.certificate_template import CertificateTemplate


DEFAULT_INSTITUTION_NAME = "示范学院"
DEFAULT_PROJECT_NAME = "软件开发实训"
DEFAULT_GRADE_LEVEL = "合格"
DEFAULT_CERTIFICATE_TITLE = "实训结业证书"
# 跟前端 TemplatesView.vue 里 emptyTemplate() 的默认勾选一致，模板从没配置过
# fields（比如老数据、或者content解析失败退回空dict）时兜底用这个。
DEFAULT_FIELDS = ["student_name", "certificate_no", "issue_date", "qr_code"]


def parse_content_config(raw_content: str | None) -> dict[str, Any]:
    if not raw_content:
        return {}

    try:
        value = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        try:
            value = ast.literal_eval(raw_content)
        except (SyntaxError, ValueError):
            return {"content": raw_content}
    return value if isinstance(value, dict) else {}


def serialize_content_config(config: dict[str, Any]) -> str:
    return json.dumps(config, ensure_ascii=False, separators=(",", ":"))


def sanitize_download_filename(name: str) -> str:
    """模板名称是管理员自己填的自由文本，用来当下载文件名之前先过滤一遍——
    去掉路径分隔符和控制字符，避免变成一个奇怪的/危险的文件名。"""
    cleaned = "".join(ch for ch in name if ch not in '/\\:*?"<>|' and ch.isprintable())
    return cleaned.strip()


def to_generation_template(
    template: CertificateTemplate,
    *,
    project_name: str | None = None,
) -> dict[str, Any]:
    """
    之前这里只摘了 institution_name / project_name / grade_level 三个key，模板里配置的
    证书标题、正文、课程名称、签发年度、动态字段勾选(fields)全部被静默丢弃——管理端
    "证书模板"页面看起来能编辑这些，但从来没有真的影响过生成出来的PDF。这里把
    content_config里存的这些字段原样透传下去，交给 certificate_service._generate_pdf()
    按 fields 列表决定画不画、留不留空。

    template_name 不在证书正文里显示（预览设计里也没有它的位置），只作为下载PDF时
    建议的文件名使用，见 admin.py 的 download_certificate()。
    """
    config = parse_content_config(template.content)
    fields = config.get("fields")
    if not isinstance(fields, list) or not fields:
        fields = list(DEFAULT_FIELDS)

    return {
        "template_id": template.template_id,
        "template_code": template.template_code,
        "template_name": template.template_name or "",
        "institution_name": template.institution_name or DEFAULT_INSTITUTION_NAME,
        "project_name": project_name
        or config.get("project_name")
        or template.template_name
        or DEFAULT_PROJECT_NAME,
        "course_name": config.get("course_name") or "",
        "certificate_title": config.get("certificate_title") or DEFAULT_CERTIFICATE_TITLE,
        "content": config.get("content") or "",
        "issue_year": config.get("issue_year") or "",
        "grade_level": config.get("grade_level") or DEFAULT_GRADE_LEVEL,
        "fields": fields,
    }
