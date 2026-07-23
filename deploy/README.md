# 服务器部署说明

本目录用于将 Vue、FastAPI 和 MySQL 作为一套隔离服务部署到自有服务器。

## 部署结构

```text
Caddy :80/:443
  -> 127.0.0.1:18080
     -> Nginx /              Vue 静态文件
     -> Nginx /api/          FastAPI:8000
        -> MySQL:3306
```

宿主机只需要公开 `80/443`。应用端口 `18080` 只绑定回环地址，FastAPI 和 MySQL 不映射到公网。

## 首次部署

在服务器项目目录执行：

```bash
./deploy/init-server.sh /opt/certificate-evidence/releases/<release>
cd /opt/certificate-evidence/releases/<release>/deploy
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:18080/__health
curl --fail http://127.0.0.1:18080/api/health
curl --fail http://127.0.0.1:18080/api/health/db
```

`.env` 中必须使用随机数据库密码和随机 `JWT_SECRET`，并把 `PUBLIC_VERIFY_BASE_URL` 设置为最终 HTTPS 验真地址。不要提交 `.env`。

## Caddy

`Caddyfile.example` 使用正式公共验真域名 `verify.lotusrain.net`。将其作为独立站点文件导入服务器现有 Caddy 配置。修改前先执行：

```bash
caddy validate --config /etc/caddy/Caddyfile
```

修改后执行：

```bash
systemctl reload caddy
```

`Caddyfile.example` 默认只公开公共验真页面、静态资源和公共验真 API，其他路径返回 `404`。认证版本完成服务器验收后，才可按“项目组协作后台”中的约束启用受限管理入口。当前还包含项目负责人明确批准的临时学生演示入口；它只服务模拟数据联调，不能被表述为正式学生认证。

## 项目组协作后台

认证版本发布后，后台优先使用独立的 `admin.verify.lotusrain.net`。启用前必须先在 DNS 创建该子域的
A/AAAA 记录并指向本服务器，然后将 `Caddyfile.example` 的两个站点块导入 Caddy。DNS 未就绪时，只能
使用下面定义的同域受限回退。默认不得放行文档、健康检查或任何未受后端 JWT 与角色鉴权保护的接口；本版本额外放行 `/student/*` 以及当前证书查询接口 `/api/student/certificates` 和其子路径作为临时学号查询演示，限制见下一段。

认证迁移只新增 `users`、`invitations` 和 `auth_sessions` 表。首次部署后，在服务器交互式创建
首个管理员，命令会安全读取密码，不要通过命令参数、环境变量、聊天记录或仓库传递密码：

```bash
cd /opt/certificate-evidence/current/deploy
docker compose exec backend python -m scripts.create_admin
```

管理员登录管理后台后可创建一次性教师邀请链接。邀请码原文只会在创建时展示一次，应通过可信
渠道发送；禁用账号会撤销该账号所有有效登录。上线前必须先备份数据库、输出目录和 Caddy 配置，
并完成未登录 `401`、越权 `403`、邀请码重复使用失败、禁用账号令牌失效和教师签发证书的验收。

若 `admin.verify.lotusrain.net` 的 DNS 尚未就绪，示例 Caddyfile 提供同域受限回退入口：仅放行
`/login`、`/register`、指定管理页面、`/api/auth/*` 和 `/api/admin/*`。该回退依赖本版本的 JWT
和后端角色鉴权。经项目负责人批准，另放行 `/student/*` 以及当前证书查询接口 `/api/student/certificates` 和其子路径，以演示 `student_no` 查询、下载和二维码；这不是登录机制，且只能使用模拟学生数据。`/docs`、健康检查和其他 API 仍返回 `404`。完成演示后应移除此学生白名单，或先实现学生账号绑定与 JWT 再长期开放。

公共验真 API 默认按来源 IP 限制为每分钟 30 个请求、允许 10 个突发请求，并将上传文件限制为 8 MB。公网运行时仍需定期检查审计日志增长情况。

## 备份与恢复

创建数据库和输出文件备份：

```bash
/opt/certificate-evidence/current/deploy/backup-server.sh
```

脚本会输出备份目录，并在其中生成 `database.sql`、`outputs.tar.gz` 和 `SHA256SUMS`。恢复会覆盖当前数据库表，必须显式确认：

```bash
CONFIRM_RESTORE=certificate-evidence \
  /opt/certificate-evidence/current/deploy/restore-server.sh \
  /opt/certificate-evidence/backups/<timestamp>
```

恢复脚本会先自动创建一份恢复前备份，校验目标备份哈希，停止 Web 与后端，恢复 MySQL 和输出文件，再重新启动并检查数据库健康状态。

## 更新与回滚

更新前保留当前镜像和数据库备份，然后执行：

```bash
ln -sfn /opt/certificate-evidence/releases/<rollback-release> /opt/certificate-evidence/current
cd /opt/certificate-evidence/current/deploy
docker compose build
docker compose up -d
```

镜像当前使用本地 `latest` 标签，因此回滚时不能只切换软链接，必须在目标旧 release 中重新构建镜像。

数据库数据保存在 Docker volume `certificate-evidence_mysql_data`，生成的 PDF 和二维码保存在 `deploy/data/outputs`。
初始化脚本会将输出目录授权给后端镜像中的非 root 运行用户；不要把该目录改回仅 `root` 可写。

切换 `PUBLIC_VERIFY_BASE_URL` 后，旧二维码不会自动改变。需要重新生成固定演示证书、PDF、二维码、哈希和回执。
