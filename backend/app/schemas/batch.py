from pydantic import BaseModel


# 按接口规范.md第4.3节"创建证书批次"，创建批次时就要传这批证书发给哪些学生
class BatchCreate(BaseModel):
    batch_name: str
    project_name: str | None = None
    template_id: int | None = None
    student_ids: list[int] = []


class BatchDetail(BaseModel):
    batch_id: int
    batch_no: str
    batch_name: str
    project_name: str | None = None
    template_id: int | None = None
    student_count: int
    # generated / evidenced 不是数据库里存的字段，是查询certificates表实时算出来的，
    # 好处是不会跟真实证书数量脱节（不用担心计数字段和实际数据不同步）
    generated: int
    evidenced: int
    status: str


class GenerateFailure(BaseModel):
    student_id: int | None = None
    reason: str


# 响应字段跟接口规范.md第4.4节"批量生成证书"完全对齐：batch_id/generated_count/failed_count。
# failures是额外加的，方便管理员看到具体哪个学生失败、什么原因，规范文档里没有这个字段，
# 但多返回不会影响前端按文档里定义的字段解析。
class GenerateResult(BaseModel):
    batch_id: int
    generated_count: int
    failed_count: int
    failures: list[GenerateFailure] = []
