"""
证书批次相关接口：建批次、查批次列表、触发批量生成。

对应接口规范.md第4.3节"创建证书批次"、第4.4节"批量生成证书"。路径和请求/响应
字段都按文档来（之前2号前端实际代码用的是/admin/certificate-batches/{id}/issue，
和文档不一致，2号已经把前端改成follow文档了，这里跟着一起改回文档版本）。

批次和学生的关联方式：按文档，创建批次（POST /admin/batches）时就要传
student_ids，存在这张表的student_ids字段里；触发生成（POST /admin/batches/{id}/generate）
不需要再传一遍名单，直接用创建批次时存下来的这份。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.certificate import Certificate
from app.models.certificate_batch import CertificateBatch
from app.models.certificate_template import CertificateTemplate
from app.schemas.batch import (
    BatchCreate,
    BatchDetail,
    GenerateFailure,
    GenerateResult,
)
from app.services import certificate_service

router = APIRouter(prefix="/admin/batches")


# 模板管理功能还没做出来之前，生成证书用的模板内容暂时用这个默认值兜底
# （字段结构和 backend/tests/test_certificate_service.py 里测试用的模板一致）。
# 等2号/4号做出真实的模板存储和查询接口后，这里要改成真的从 certificate_templates
# 表查完整内容，而不是只拿 template_name 凑合当 project_name 用——这一点
# 在 outputs/接下来要做的事.md 里已经记了一笔，不是这次漏掉了。
DEFAULT_TEMPLATE = {
    "template_code": "TPL-DEFAULT",
    "institution_name": "示范学院",
    "project_name": "暑期实训",
    "grade_level": "合格",
}


def _next_batch_no(db: Session) -> str:
    date_str = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"BATCH-{date_str}-"

    max_no = db.query(func.max(CertificateBatch.batch_no)).filter(
        CertificateBatch.batch_no.like(f"{prefix}%")
    ).scalar()

    next_seq = 1 if max_no is None else int(max_no.split("-")[-1]) + 1
    return f"{prefix}{next_seq:02d}"


def create_batch_record(
    db: Session,
    *,
    batch_name: str,
    project_name: str | None = None,
    template_id: int | None = None,
    student_ids: list[int] | None = None,
) -> CertificateBatch:
    batch = CertificateBatch(
        batch_no=_next_batch_no(db),
        batch_name=batch_name,
        project_name=project_name,
        template_id=template_id,
        student_ids=student_ids or [],
        status="DRAFT",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _to_batch_detail(db: Session, batch: CertificateBatch) -> BatchDetail:
    cert_query = db.query(Certificate).filter(Certificate.batch_id == str(batch.batch_id))
    generated = cert_query.count()
    evidenced = cert_query.filter(Certificate.receipt_id.isnot(None)).count()

    return BatchDetail(
        batch_id=batch.batch_id,
        batch_no=batch.batch_no,
        batch_name=batch.batch_name,
        project_name=batch.project_name,
        template_id=batch.template_id,
        student_count=len(batch.student_ids or []),
        generated=generated,
        evidenced=evidenced,
        status=batch.status,
    )


@router.post("", response_model=ApiResponse[BatchDetail])
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)) -> ApiResponse[BatchDetail]:
    batch = create_batch_record(
        db,
        batch_name=payload.batch_name,
        project_name=payload.project_name,
        template_id=payload.template_id,
        student_ids=payload.student_ids,
    )
    return ApiResponse.success(_to_batch_detail(db, batch))


@router.get("", response_model=ApiResponse[list[BatchDetail]])
def list_batches(db: Session = Depends(get_db)) -> ApiResponse[list[BatchDetail]]:
    batches = db.query(CertificateBatch).order_by(CertificateBatch.created_at.desc()).all()
    return ApiResponse.success([_to_batch_detail(db, batch) for batch in batches])


def _load_template_dict(db: Session, template_id: int | None) -> dict:
    if template_id is None:
        return DEFAULT_TEMPLATE

    template = db.get(CertificateTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"模板不存在：template_id={template_id}")

    return {
        "template_code": template.template_code,
        "project_name": template.template_name,
        "institution_name": DEFAULT_TEMPLATE["institution_name"],
        "grade_level": DEFAULT_TEMPLATE["grade_level"],
    }


@router.post("/{batch_id}/generate", response_model=ApiResponse[GenerateResult])
def generate_batch(batch_id: int, db: Session = Depends(get_db)) -> ApiResponse[GenerateResult]:
    """
    批量触发证书生成——接口规范.md第4.4节。不需要请求体，处理的对象是创建这个
    批次时（POST /admin/batches）就存下来的student_ids名单。

    真正的生成逻辑在certificate_service.generate_certificate()里，早就写好并
    测试过了，这里只做三件事：查批次存不存在、把template_id换成生成函数需要的
    模板字典、对批次里的每个student_id分别调用生成函数——单个学生失败（比如
    student_id不存在）不会影响其他人，失败原因收集起来一起返回。
    """
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"批次不存在：batch_id={batch_id}")

    template = _load_template_dict(db, batch.template_id)
    issue_date = datetime.utcnow()

    failures: list[GenerateFailure] = []
    generated_count = 0

    for student_id in batch.student_ids or []:
        try:
            certificate_service.generate_certificate(
                db,
                student_id=student_id,
                template=template,
                issue_date=issue_date,
                batch_id=str(batch_id),
            )
            generated_count += 1
        except (ValueError, RuntimeError) as exc:
            db.rollback()
            failures.append(GenerateFailure(student_id=student_id, reason=str(exc)))

    if batch.status == "DRAFT" and generated_count > 0:
        batch.status = "GENERATED"
        db.commit()

    return ApiResponse.success(
        GenerateResult(
            batch_id=batch_id,
            generated_count=generated_count,
            failed_count=len(failures),
            failures=failures,
        )
    )
