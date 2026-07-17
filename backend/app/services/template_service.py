import ast
import json
from typing import Any

from app.models.certificate_template import CertificateTemplate


DEFAULT_INSTITUTION_NAME = "示范学院"
DEFAULT_PROJECT_NAME = "软件开发实训"
DEFAULT_GRADE_LEVEL = "合格"


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


def to_generation_template(
    template: CertificateTemplate,
    *,
    project_name: str | None = None,
) -> dict[str, Any]:
    config = parse_content_config(template.content)
    return {
        "template_id": template.template_id,
        "template_code": template.template_code,
        "institution_name": template.institution_name or DEFAULT_INSTITUTION_NAME,
        "project_name": project_name
        or config.get("project_name")
        or template.template_name
        or DEFAULT_PROJECT_NAME,
        "grade_level": config.get("grade_level") or DEFAULT_GRADE_LEVEL,
    }
