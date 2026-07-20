"""
证书批次相关接口：建批次、查批次列表、触发批量生成。

对应接口规范.md第4.3节"创建证书批次"、第4.4节"批量生成证书"。路径和请求/响应
字段都按文档来（之前2号前端实际代码用的是/admin/certificate-batches/{id}/issue，
和文档不一致，2号已经把前端改成follow文档了，这里跟着一起改回文档版本）。

批次和学生的关联方式：按文档，创建批次（POST /admin/batches）时就要传
student_ids，存在这张表的student_ids字段里；触发生成（POST /admin/batches/{id}/generate）
不需要再传一遍名单，直接用创建批次时存下来的这份。
"""
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.auth import require_admin_access
from app.core.responses import ApiResponse
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.certificate import Certificate
from app.models.certificate_batch import CertificateBatch
from app.models.certificate_template import CertificateTemplate
from app.models.credential_root import CredentialRoot
from app.models.project import Project
from app.schemas.batch import (
    BatchCreate,
    BatchDetail,
    BatchGeneratePayload,
    BatchUpdate,
    EvidenceBatchResult,
    GenerateFailure,
    GenerateResult,
    MerkleRootResult,
)
from app.services import certificate_service, chain_service, merkle_service, template_service

router = APIRouter(prefix="/admin/batches", dependencies=[Depends(require_admin_access)])
logger = logging.getLogger(__name__)


def _merkle_root_result(root_record: CredentialRoot) -> MerkleRootResult:
    return MerkleRootResult(
        batch_id=root_record.batch_id,
        root_id=root_record.root_no,
        root_no=root_record.root_no,
        merkle_root=root_record.merkle_root,
        leaf_order_rule=root_record.leaf_order_rule,
        odd_leaf_rule=root_record.odd_leaf_rule,
        previous_root_hash=root_record.previous_root_hash,
        current_root_hash=root_record.current_root_hash,
        leaf_count=root_record.leaf_count,
        tx_hash=root_record.tx_hash,
    )


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
    project_id: int | None = None,
    project_name: str | None = None,
    template_id: int | None = None,
    student_ids: list[int] | None = None,
) -> CertificateBatch:
    batch = CertificateBatch(
        batch_no=_next_batch_no(db),
        batch_name=batch_name,
        project_id=project_id,
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
    # certificates.batch_id 现在是真正的整数外键了（之前是字符串，2号/4号那边的
    # 合并已经把模型改过来了），这里跟着改成用int比较，不再用str()包一层。
    cert_query = db.query(Certificate).filter(Certificate.batch_id == batch.batch_id)
    generated = cert_query.count()
    evidenced = cert_query.filter(Certificate.receipt_id.isnot(None)).count()

    return BatchDetail(
        batch_id=batch.batch_id,
        batch_no=batch.batch_no,
        batch_name=batch.batch_name,
        project_id=batch.project_id,
        project_name=batch.project_name,
        template_id=batch.template_id,
        student_count=len(batch.student_ids or []),
        generated=generated,
        evidenced=evidenced,
        status=batch.status,
    )


def _parse_issue_date(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="issue_date must be YYYY-MM-DD") from exc


def _page_batch_records(
    records: list[dict],
    *,
    current: int | None,
    size: int | None,
    keyword: str | None,
    status: str | None,
) -> dict:
    page_no = max(int(current or 1), 1)
    page_size = max(int(size or 10), 1)
    keyword_text = (keyword or "").lower()
    status_text = status or ""

    def matches(record: dict) -> bool:
        if keyword_text and keyword_text not in str(record).lower():
            return False
        if status_text and record.get("status") != status_text:
            return False
        return True

    filtered = [record for record in records if matches(record)]
    start = (page_no - 1) * page_size
    return {
        "records": filtered[start:start + page_size],
        "total": len(filtered),
        "current": page_no,
        "size": page_size,
    }


@router.post("", response_model=ApiResponse[BatchDetail])
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)) -> ApiResponse[BatchDetail]:
    project_name = payload.project_name
    if payload.project_id is not None:
        project = db.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"project_id={payload.project_id} not found")
        project_name = project.project_name
    batch = create_batch_record(
        db,
        batch_name=payload.batch_name,
        project_id=payload.project_id,
        project_name=project_name,
        template_id=payload.template_id,
        student_ids=payload.student_ids,
    )
    return ApiResponse.success(_to_batch_detail(db, batch))


@router.get("", response_model=ApiResponse[dict[str, Any]])
def list_batches(
    current: int = 1,
    size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """
    前端frontend/src/types/index.ts里getBatches()要的是分页格式PageResult
    （{records,total,current,size}），不是纯列表——之前这里直接返回列表，
    格式跟前端期望的不一致，是我们自己的bug，已经修掉。始终返回分页格式
    （不像_page_batch_records那样"没传分页参数就退化成纯列表"），因为
    PageQuery里current/size是必填字段，前端调用这个接口时永远会带上，
    保持行为单一、可预期。
    """
    batches = db.query(CertificateBatch).order_by(CertificateBatch.created_at.desc()).all()
    records = [_to_batch_detail(db, batch).model_dump() for batch in batches]
    return ApiResponse.success(
        _page_batch_records(records, current=current, size=size, keyword=keyword, status=status)
    )


@router.put("/{batch_id}", response_model=ApiResponse[BatchDetail])
def update_batch(
    batch_id: int,
    payload: BatchUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[BatchDetail]:
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"batch_id={batch_id} not found")
    if payload.batch_name is not None:
        batch.batch_name = payload.batch_name
    if payload.project_id is not None:
        project = db.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"project_id={payload.project_id} not found")
        batch.project_id = project.project_id
        batch.project_name = project.project_name
    if payload.project_name is not None and payload.project_id is None:
        batch.project_name = payload.project_name
    if payload.template_id is not None:
        batch.template_id = payload.template_id
    if payload.student_ids is not None:
        batch.student_ids = payload.student_ids
    if payload.status is not None:
        batch.status = payload.status
    db.commit()
    db.refresh(batch)
    return ApiResponse.success(_to_batch_detail(db, batch))


@router.delete("/{batch_id}")
def delete_batch(batch_id: int, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"batch_id={batch_id} not found")
    certificate_count = db.query(Certificate).filter(Certificate.batch_id == batch_id).count()
    if certificate_count:
        raise HTTPException(status_code=409, detail="该批次已有证书记录，不能删除")
    db.delete(batch)
    db.commit()
    return ApiResponse.success({"deleted": True})


def _load_template_dict(db: Session, template_id: int | None) -> dict:
    if template_id is None:
        return DEFAULT_TEMPLATE

    template = db.get(CertificateTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"template_id={template_id} not found")

    return template_service.to_generation_template(template)


@router.post("/{batch_id}/generate", response_model=ApiResponse[GenerateResult])
def generate_batch(
    batch_id: int,
    payload: BatchGeneratePayload | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[GenerateResult]:
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

    student_ids = payload.student_ids if payload and payload.student_ids else batch.student_ids or []
    template_id = payload.template_id if payload and payload.template_id is not None else batch.template_id
    template = _load_template_dict(db, template_id)
    issue_date = _parse_issue_date(payload.issue_date if payload else None)

    project_id = payload.project_id if payload and payload.project_id is not None else batch.project_id
    project_name = batch.project_name
    if project_id is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"project_id={project_id} not found")
        project_name = project.project_name
    if project_name:
        template = {**template, "project_name": project_name}

    batch.project_id = project_id
    batch.project_name = project_name
    batch.template_id = template_id
    batch.student_ids = student_ids
    db.commit()

    failures: list[GenerateFailure] = []
    generated_count = 0

    for student_id in student_ids:
        try:
            certificate = certificate_service.generate_certificate(
                db,
                student_id=student_id,
                template=template,
                issue_date=issue_date,
                batch_id=batch_id,
            )
            # 审计日志埋点：字段风格跟4号在admin.py里写撤销/补发日志时保持一致
            # （action中文短句、target_type固定"证书管理"、target_id用certificate_no、
            # operator暂时写死"admin"，还没接登录鉴权）。每张证书单独记一条，方便
            # 以后按certificate_no查"这张证书是什么时候生成的"。
            db.add(
                AuditLog(
                    action="证书生成",
                    target_type="证书管理",
                    target_id=certificate.certificate_no[:64],
                    operator="admin",
                    detail=f"批次batch_id={batch_id}生成",
                )
            )
            db.commit()
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


@router.post("/{batch_id}/evidence", response_model=ApiResponse[EvidenceBatchResult])
def evidence_batch(
    batch_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[EvidenceBatchResult]:
    batch = db.get(CertificateBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail=f"batch_id={batch_id} not found")

    certificates = db.query(Certificate).filter(Certificate.batch_id == batch_id).all()
    evidenced_count = 0
    for certificate in certificates:
        if certificate.certificate_hash and not certificate.receipt_id:
            receipt = certificate_service._create_evidence_receipt(
                db,
                certificate.certificate_id,
                certificate.certificate_no,
                certificate.certificate_hash,
            )
            certificate.receipt_id = receipt.receipt_no
            evidenced_count += 1

    if certificates and all(certificate.receipt_id for certificate in certificates):
        batch.status = "EVIDENCED"
    db.commit()
    receipt_ids = [
        certificate.receipt_id
        for certificate in certificates
        if certificate.receipt_id is not None
    ]
    return ApiResponse.success(
        EvidenceBatchResult(
            batch_id=batch_id,
            success_count=len(receipt_ids),
            receipt_ids=receipt_ids,
            evidenced=len(receipt_ids),
            newly_evidenced=evidenced_count,
        )
    )


@router.get("/{batch_id}/merkle-root", response_model=ApiResponse[MerkleRootResult])
def get_merkle_root(
    batch_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[MerkleRootResult]:
    root_record = (
        db.query(CredentialRoot)
        .filter(CredentialRoot.batch_id == batch_id)
        .first()
    )
    if root_record is None:
        raise HTTPException(
            status_code=404,
            detail=f"批次batch_id={batch_id}尚未生成Merkle Root",
        )
    return ApiResponse.success(_merkle_root_result(root_record))


@router.post("/{batch_id}/merkle-root", response_model=ApiResponse[MerkleRootResult])
def compute_merkle_root(batch_id: int, db: Session = Depends(get_db)) -> ApiResponse[MerkleRootResult]:
    """
    Merkle Root（P2加分项，FISCO_BCOS与存证降级策略.md第8节 / 数据库设计.md第9节）：
    本地哈希链之上叠加的一层，把批次内所有证书哈希汇总成一个Root，为以后接测试链
    做准备（如果接了测试链，一个批次只需要写一笔交易，不是逐张证书上链）。

    单独开一个路由、不塞进上面的evidence_batch()里，是为了不改动4号那边已经跑通
    的存证主流程——这一步失败（比如批次里还有证书没生成完）不会影响evidence_batch
    已经做完的事，符合降级策略里"Root是可选叠加层，不能阻塞P0主线"的要求。
    """
    try:
        root_record = merkle_service.compute_batch_root(db, batch_id)
    except merkle_service.MerkleBatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except merkle_service.MerkleRootAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except merkle_service.MerkleRootConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        db.add(
            AuditLog(
                action="批次Merkle Root生成",
                target_type="证书管理",
                target_id=root_record.root_no,
                operator="admin",
                detail=f"批次batch_id={batch_id}生成Root，包含{root_record.leaf_count}张证书",
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("failed to write Merkle Root audit log")

    # 测试链接入（P2加分项）：本地Root已经算好、已经落库，这一步是在这之上
    # "顺便"写一笔链上交易。chain_service内部保证了没配置/连不上/写入失败都只
    # 返回None、不抛异常，所以这里不需要try/except——即使这一步完全没跑，
    # 上面的Root计算结果也已经完整、可用，不受影响。
    tx_hash = chain_service.record_root_on_chain(
        root_no=root_record.root_no,
        batch_id=batch_id,
        merkle_root=root_record.merkle_root,
        previous_root_hash=root_record.previous_root_hash,
        current_root_hash=root_record.current_root_hash,
    )
    if tx_hash:
        try:
            root_record.tx_hash = tx_hash
            db.add(
                AuditLog(
                    action="批次Root上链",
                    target_type="证书管理",
                    target_id=root_record.root_no,
                    operator="admin",
                    detail=f"交易哈希：{tx_hash}",
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            tx_hash = None
            logger.exception("failed to persist chain transaction receipt")

    return ApiResponse.success(_merkle_root_result(root_record))
