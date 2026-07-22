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

当前项目仍使用演示账号和演示令牌。`Caddyfile.example` 默认只公开公共验真页面、静态资源和公共验真 API，其他路径返回 `404`。管理端应通过 SSH 隧道访问；若以后需要公网开放管理端，必须先完成正式鉴权或接入独立访问网关。

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
