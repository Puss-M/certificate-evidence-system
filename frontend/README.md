# 可信证书管理平台（Vue 3 管理员端）

本项目是“基于区块链的实训证书与学业证明存证系统”的管理员端，基于 Vue 3、TypeScript、Vite、Pinia、Vue Router、Axios 和 Element Plus。

## 功能

- 实训项目、学生、证书模板和证书批次管理
- Excel学生名单导入
- 批量证书签发及失败原因展示
- 证书查询、单证存证、撤销和补发
- 批次批量存证
- 本地哈希链及FISCO BCOS回执展示
- 回执刷新和本地哈希链完整性校验
- 操作日志和首页统计
- ADMIN、TEACHER、AUDITOR动态菜单与路由权限

## 安装与运行

```bash
npm install
npm run dev
```

如果本机使用pnpm：

```bash
pnpm install
pnpm dev
```

开发地址默认是 `http://localhost:5173`。

## Mock账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| admin | 123456 | ADMIN |
| teacher | 123456 | TEACHER |
| auditor | 123456 | AUDITOR |

## 切换 FastAPI 后端

修改 `.env.development`：

```env
VITE_API_BASE_URL=/api
VITE_USE_MOCK=false
```

Vite会把 `/api` 代理到 `http://127.0.0.1:8000`。页面不直接保存接口URL；所有接口均封装在 `src/api`，后端契约变化时只修改API层。

## 统一响应

```json
{
  "code": 0,
  "message": "操作成功",
  "data": {}
}
```

分页数据：

```json
{
  "records": [],
  "total": 0,
  "current": 1,
  "size": 10
}
```

冻结业务字段在 API、Mock、类型和页面中统一使用 snake_case，不转换为 camelCase。

## 权限

- `ADMIN`：全部页面及操作。
- `TEACHER`：项目、学生、模板、批次、证书和存证。
- `AUDITOR`：存证回执和操作日志，只读。

## 构建

```bash
npm run build
```

构建产物位于 `dist`。
## 基础页面设计

页面路由、组件拆分、Mock 示例与 FastAPI 接口清单见 [`../docs/协作管理/管理员前端/管理员前端基础页面设计.md`](../docs/协作管理/管理员前端/管理员前端基础页面设计.md)。
