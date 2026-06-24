# TikTok 直播间关注监听

多用户 Web 管理平台：监听 TikTok 直播间的新关注事件，并通过 Telegram 机器人推送到指定群组。支持用户自助配置监控任务，管理员统一管理账号与资源。

---

## 功能概览

### 用户端（`/`，Vue 3）

| 模块 | 说明 |
|------|------|
| **概览** | 今日/累计关注与进房数据、实时刷新 |
| **监控任务** | 创建/编辑/启停任务，绑定主播、API Key、推送 Bot 与群组 |
| **事件流水** | 新关注、新进直播间历史记录 |
| **API Key 池** | 管理 Euler 签名 Key，查看配额，批量导入 |
| **机器人** | 添加 Telegram Bot，预览连通性 |
| **群组** | 从 Bot 发现群组、批量导入、刷新群名 |

### 管理后台（`/admin/`，Vue 3）

| 模块 | 说明 |
|------|------|
| **用户管理** | 创建/编辑用户、配额、明文密码查看 |
| **主播库** | 全局 TikTok 主播 `unique_id` 管理 |
| **API Key / Bot / 群组** | 跨用户资源查看与维护 |
| **数据统计** | 全平台事件汇总 |

### 监听引擎（内置后端）

- 单进程同时提供 **REST API** 与 **TikTok 监听 Worker**
- 每个启用的监控任务独立线程，绑定独立 Sign API Key
- 连接前/连接后双重校验主播是否**真正在播**
- 仅在确认开播时推送 Telegram「开播通知」
- 实时更新任务状态（连接中 / 直播中 / 未开播 / 限流 / 重试中 / 异常 / 已停用）

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                     浏览器                                   │
│   用户端 (Vue)          管理端 (Vue)                         │
└────────────┬──────────────────────┬─────────────────────────┘
             │  /api/*              │  /admin/api/*
             ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI (app/main.py)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ user_routes  │  │ admin_routes │  │ MonitorManager   │ │
│  └──────────────┘  └──────────────┘  └────────┬─────────┘ │
└────────────────────────────────────────────────│────────────┘
                                                 │ 每任务 1 线程
                                                 ▼
                                    ┌────────────────────────┐
                                    │ TaskWorker (TikTokLive) │
                                    │  → Telegram 推送        │
                                    └────────────────────────┘
             │                              │
             ▼                              ▼
      MySQL / SQLite                   TikTok LIVE
      (用户/任务/事件)                  + Telegram API
```

### 目录结构

```
关注监听/
├── app/                    # Python 后端
│   ├── main.py             # FastAPI 入口
│   ├── api/                # 用户端 / 管理端路由
│   ├── monitor/            # 监听管理器、Worker、状态机
│   ├── models.py           # SQLAlchemy 模型
│   └── settings.py         # 环境变量
├── frontend-user/          # 用户端 Vue 3 + Vite + Naive UI
├── frontend-admin/         # 管理端 Vue 3 + Vite + Naive UI
├── web-shared/             # 共享主题样式
├── scripts/                # 构建、迁移、导出脚本
├── release/                # 发布文档与配置模板（产物本身不入 Git）
│   ├── DEPLOY-BAOTA.md     # 宝塔可视化部署指南
│   └── env.production.example
├── data/                   # 运行时数据（本地 SQLite、缓存、日志，不入 Git）
├── join_rate_limiter.py    # 进房推送限流
├── room_cache.py           # room_id 本地缓存
├── telegram_notifier.py    # Telegram 消息模板与发送
├── run_server.py           # PyInstaller 打包入口
├── follow_monitor.spec     # PyInstaller 配置
├── Dockerfile.build        # Linux 二进制 Docker 构建
├── start.sh                # 本地开发：启动后端
├── start-all.sh            # 本地开发：后端 + 双前端
└── requirements.txt
```

---

## 监控任务状态

| 状态 | 界面显示 | 含义 |
|------|----------|------|
| `idle` | 已停用 / 空闲 | 任务关闭或未运行 |
| `connecting` | 连接中 | 正在连接 TikTok |
| `live` | 直播中 | 已确认主播在播 |
| `offline` | 未开播 | 主播未开播或已下播 |
| `rate_limited` | 限流 | Sign API 频率超限 |
| `retrying` | 重试中 | 等待下次重连 |
| `error` | 异常 | 其他错误（悬停可看详情） |

任务列表每 **3 秒**自动刷新状态。

---

## 开播通知规则

1. **连接前预检**：调用 `fetch_is_live(unique_id=...)`，未开播则不连接、不推送
2. **连接后复检**：Connect 事件再次确认，未开播则断开连接
3. **推送时机**：仅在**确认开播**后发送一次 Telegram 通知
4. **下播重置**：收到下播事件后重置标记，再次开播会重新推送
5. **重新启用任务**：关闭后再打开，会重新检测；若在播则推送，未开播则不推送

---

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | **3.10+**（TikTokLive 依赖） |
| Node.js | 18+（前端开发/构建） |
| Docker | 可选，Mac 上打包 Linux 二进制时需要 |
| MySQL | 可选，生产推荐；本地可用 SQLite |

---

## 快速开始（本地开发）

### 1. 克隆与配置

```bash
git clone <仓库地址>
cd 关注监听
cp .env.example .env
# 编辑 .env，至少修改 JWT_SECRET
```

### 2. 初始化数据库

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/init_db.py --email admin@admin.com --password Admin888*
```

### 3. 启动服务

**方式 A：一键启动全部**

```bash
chmod +x start-all.sh start-frontends.sh start.sh
./start-all.sh
```

**方式 B：分别启动**

```bash
./start.sh                          # 终端 1：后端 API
./start-frontends.sh                # 终端 2：双前端 dev server
```

### 4. 访问地址

| 页面 | 地址 |
|------|------|
| 用户端 | http://127.0.0.1:5173/ |
| 管理端 | http://127.0.0.1:5174/admin/ |
| API 健康检查 | http://127.0.0.1:8000/api/health |

### 5. 典型使用流程

1. **管理员**登录管理后台 → 创建普通用户（设置监控/Bot/群组配额）
2. **用户**登录用户端 → 添加 Telegram Bot → 导入群组
3. 在 **API Key 池** 添加 Euler Sign API Key（[Euler Stream 定价](https://www.eulerstream.com/pricing)）
4. **监控任务** → 新建任务：填写主播 ID、选择 Key、绑定 Bot 与群组 → 启用
5. 主播开播后，群组收到「已经开播，开始监听新关注」；有新关注时持续推送

---

## 生产部署

### 一键打包（Mac → Linux amd64）

```bash
chmod +x scripts/*.sh
./scripts/build_release.sh
```

产物：

- `release/follow-monitor/` — 可上传目录
- `release/follow-monitor-linux-amd64.tar.gz` — 压缩包（约 47MB）

打包内容：Linux 可执行文件 + 前后端静态资源 + `start.sh`，**服务器无需安装 Python / Node**。

### 宝塔面板部署

详见 **[release/DEPLOY-BAOTA.md](release/DEPLOY-BAOTA.md)**（全程可视化操作：上传、解压、MySQL 导入、Supervisor、Nginx 反代）。

生产 `.env` 模板：**[release/env.production.example](release/env.production.example)**

### 更新程序

```bash
# 本地重新打包
./scripts/build_release.sh

# 服务器：上传 tar.gz 解压覆盖（保留 .env 和 data/），Supervisor 重启
```

---

## 环境变量

完整示例见 [.env.example](.env.example)。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_HOST` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | MySQL 连接（生产推荐） | — |
| `DATABASE_URL` | 完整连接串（与 MYSQL_* 二选一） | 本地 `data/app.db` |
| `JWT_SECRET` | 登录 Token 密钥 | **生产必改** |
| `TOKEN_ENCRYPT_KEY` | Bot Token 加密密钥 | 留空则用 JWT_SECRET |
| `JWT_EXPIRE_HOURS` | Token 有效期（小时） | 72 |
| `RECONNECT_DELAY_SECONDS` | 未开播/断线后重试间隔 | 30 |
| `FETCH_LIVE_CHECK` | TikTokLive 内置开播检测（Worker 已强制预检） | false |
| `HTTPS_PROXY` | 访问 TikTok 的代理 | — |
| `DEFAULT_MAX_MONITORS` | 新用户默认监控任务上限 | 10 |
| `DEFAULT_MAX_BOTS` | 新用户默认 Bot 上限 | 10 |
| `DEFAULT_MAX_GROUPS` | 新用户默认群组上限 | 10 |
| `HOST` / `PORT` | 服务监听地址 | 0.0.0.0:8000 |
| `SERVE_STATIC` | 由后端托管前端静态文件 | false（发布包 true） |
| `CORS_ORIGINS` | 前端跨域来源（逗号分隔） | localhost:5173/5174 |

---

## 常用脚本

| 脚本 | 用途 |
|------|------|
| `scripts/init_db.py` | 初始化数据库并创建管理员 |
| `scripts/build_release.sh` | 编译前端 + Docker 打包 Linux 后端 |
| `scripts/build_frontends.sh` | 仅编译两个前端 |
| `scripts/migrate_sqlite_to_mysql.py` | SQLite → MySQL 数据迁移 |
| `scripts/export_mysql.sh` | 导出 MySQL 备份 SQL |
| `scripts/bootstrap_local_mysql.sh` | 本地内置 MySQL 初始化（开发用） |

---

## 数据库

- **开发**：默认 SQLite（`data/app.db`），零配置
- **生产**：推荐 MySQL 8.0 / 5.7，表结构含中文 COMMENT
- 表：`users`、`monitor_tasks`、`streamers`、`sign_api_keys`、`telegram_bots`、`telegram_groups`、`follow_events`、`join_events`、`audit_logs`

---

## 注意事项

1. **Sign API Key**：每个监控任务需独立 Key，全局不可重复绑定
2. **Bot 推送占用**：同一 Bot 同时只能被一个**启用**的监控任务用于新关注推送
3. **服务器网络**：需能访问 TikTok 与 Telegram；国内服务器通常需配置 `HTTPS_PROXY`
4. **密钥安全**：`.env`、数据库密码、Bot Token 切勿提交到 Git
5. **Python 版本**：低于 3.10 时 TikTokLive 无法加载，监听功能不可用

---

## 许可证

私有项目，未经授权请勿分发。
123456