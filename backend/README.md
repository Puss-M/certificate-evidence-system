# FastAPI 后端

本目录是证书存证系统的 FastAPI 后端工程，负责基础业务接口、MySQL 连接、统一返回格式、公共验真、证书生成、本地哈希链存证，以及管理员前端接口对接。

## 已完成内容

- FastAPI 项目骨架
- MySQL 连接配置
- `.env.example` 示例配置
- 统一返回格式
- CORS 配置
- 全局异常处理初版
- 核心表结构草案
- 学生列表接口
- 证书列表接口
- 公共验真接口
- 证书生成与本地哈希链回执
- 批次 Merkle Root 与单证书 Merkle Proof（本地 P2）
- 管理员前端联调接口
- 撤销、补发接口骨架
- 接口自动化测试

## 本地启动方式

以下命令都在 `backend` 目录执行。

先启动 MySQL。下面是命令格式，`<MYSQL_HOME>` 和 `<MYSQL_DATA_DIR>` 按本机实际路径替换，不要把真实路径和密码提交到仓库：

```powershell
"<MYSQL_HOME>\bin\mysqld.exe" --defaults-file="<MYSQL_DATA_DIR>\my.ini" --console
```

再启动 FastAPI：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

二维码默认指向本机公共验真接口。若需要用手机在同一局域网扫码，可仅在本机 `.env`
设置 `PUBLIC_VERIFY_BASE_URL=http://<局域网IP>:8000/api/verification`，重启 FastAPI 后
重新生成演示证书；不要把局域网地址或 `.env` 提交到仓库。

Swagger 接口文档地址：

```text
http://127.0.0.1:8000/docs
```

## 数据库表

本机数据库表已经创建。其他成员首次运行时，可在 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.create_tables
```

如果本机以前已经创建过旧表，需要补齐业务表新增字段和 Merkle 表，可执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.upgrade_certificate_schema
```

该脚本只补缺失列并按需创建 `credential_roots`、`merkle_tree_nodes`，不删除表、不清空数据。若旧 Merkle 表已有重复批次 Root 或重复节点位置，脚本会保留原数据并明确中止，需先人工核对历史记录后重跑，避免静默删除存证事实。

当前表结构草案：

- `students`
- `certificates`
- `certificate_templates`
- `certificate_batches`
- `evidence_receipts`
- `revocation_records`
- `audit_logs`
- `credential_roots`
- `merkle_tree_nodes`

## 当前接口

- `GET /api/health`
- `GET /api/health/db`
- `GET /api/students`
- `GET /api/certificates`
- `GET /api/verification/{certificate_no}`
- `POST /api/verification/{certificate_no}/file`
- `POST /api/auth/login`
- `GET /api/admin/dashboard/statistics`
- `GET /api/admin/students`
- `GET /api/admin/templates`
- `GET/POST/PUT/DELETE /api/admin/batches`
- `POST /api/admin/batches/{batch_id}/generate`
- `POST /api/admin/batches/{batch_id}/evidence`
- `POST /api/admin/batches/{batch_id}/merkle-root`
- `GET /api/admin/certificate-batches`（兼容旧调用）
- `GET /api/admin/certificates`
- `POST /api/admin/certificates/{certificate_id}/evidence`
- `POST /api/admin/certificates/{certificate_identifier}/revoke`
- `POST /api/admin/certificates/{certificate_id}/reissue`
- `GET /api/admin/evidence/receipts`
- `GET /api/admin/evidence/integrity`
- `GET /api/admin/audit-logs`
- `GET /api/public/verify/{certificate_no}/merkle-proof`
- `GET /api/verification/{certificate_no}/merkle-proof`（兼容路径）

公共验真说明：

- 编号验真：查询证书是否存在、状态是否有效、是否有存证回执。
- 上传 PDF 复验：现场计算上传文件 SHA-256，并和数据库保存的 `certificate_hash` 比对。
- Merkle Proof：验证证书哈希属于本地批次 Root；不等同证书当前有效，也不代表 Root 已上测试链。
- 结果状态包括：`PASS`、`REVOKED`、`REISSUED`、`HASH_MISMATCH`、`NOT_FOUND`、`NO_RECEIPT`、`SYSTEM_ERROR`。

## 测试

在 `backend` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前测试结果：

```text
55 passed
```

## 前后端关键字段

| 字段 | 含义 | 联调说明 |
| --- | --- | --- |
| `certificate_hash` | 最终 PDF 的 SHA-256 | 上传 PDF 复验时与现场计算值比对。 |
| `receipt_id` | 存证回执业务编号 | 对应 `evidence_receipts.receipt_no`，不是表自增主键。 |
| `status` | 证书生命周期状态 | 常用值：`DRAFT`、`VALID`、`REVOKED`、`REISSUED`。 |
| `evidence_status` | 管理端展示的存证状态 | 有回执时为 `CONFIRMED`，无回执时为 `PENDING`。 |

`GET /api/verification/{certificate_no}` 用于编号或扫码验真；
`POST /api/verification/{certificate_no}/file` 用于上传 PDF 的 SHA-256 强校验。

## 安全说明

不要提交以下内容：

- `.env`
- 数据库真实密码
- JWT 密钥
- API key
- 私钥、助记词
- 真实学生数据

只能提交 `.env.example`。当前 mock 数据使用测试学生和测试证书编号，不包含真实个人信息。

`admin / 123456` 仅用于本地演示登录和前端路由联调，不是生产账号方案。正式账号系统需要接入 `users` 表、密码哈希和 JWT 鉴权。
