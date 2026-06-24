# 宝塔可视化面板部署指南（无需终端）

本指南全程使用宝塔 **文件、数据库、网站、Supervisor** 等可视化界面操作。

---

## 一、需要上传的文件

在本地 `release/` 目录，上传以下 **2 个文件** 到服务器：

| 文件 | 说明 |
|------|------|
| `follow-monitor-linux-amd64.tar.gz` | 程序包（后端 + 前端，约 46MB） |
| `follow_monitor.sql` | 数据库备份（含管理员、用户、历史事件，约 6.6MB） |

另备：`env.production.example`（配置模板，一并上传方便编辑）

---

## 二、安装宝塔插件（首次）

1. 登录宝塔面板
2. 左侧 **软件商店**
3. 搜索并安装：
   - **MySQL**（5.7 或 8.0，若未安装）
   - **Nginx**
   - **Supervisor管理器**（进程守护，必装）

---

## 三、创建网站目录并解压程序

1. 左侧 **文件**
2. 进入 `/www/wwwroot/`
3. 点击 **新建目录**，名称：`follow-monitor`
4. 进入 `follow-monitor` 目录
5. 点击 **上传**，上传 `follow-monitor-linux-amd64.tar.gz`
6. 上传完成后，勾选该文件 → 点击 **解压**
7. 解压后应出现子目录 `follow-monitor/`，结构如下：

```
/www/wwwroot/follow-monitor/follow-monitor/
├── follow-monitor/follow-monitor   ← Linux 可执行文件
├── frontend-user/dist/
├── frontend-admin/dist/
├── start.sh
├── .env.example
└── data/
```

8. 若解压多了一层目录，确保 `start.sh` 路径为：  
   `/www/wwwroot/follow-monitor/follow-monitor/start.sh`

9. 右键 `start.sh` → **权限** → 勾选 **执行**，设为 `755`  
   同样给 `follow-monitor/follow-monitor` 可执行文件设 `755`

---

## 四、创建 MySQL 数据库并导入

1. 左侧 **数据库** → **添加数据库**
   - 数据库名：`follow_monitor`
   - 用户名：`follow_monitor`（或自定义）
   - 密码：自行设置（**记下来，后面写进 .env**）
   - 访问权限：本地服务器

2. 在数据库列表找到 `follow_monitor` → 点击 **管理**（进入 phpMyAdmin）

3. phpMyAdmin 中：
   - 左侧选中 `follow_monitor` 库
   - 顶部 **导入**
   - **选择文件** → 上传本地的 `follow_monitor.sql`
   - 点击 **执行**
   - 提示成功即可（含 users、follow_events、join_events 等表）

---

## 五、配置 .env

1. 宝塔 **文件** → 进入  
   `/www/wwwroot/follow-monitor/follow-monitor/`

2. 上传 `env.production.example`，或复制 `.env.example` 为 `.env`

3. 双击 `.env` → **编辑**，至少修改：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=follow_monitor
MYSQL_PASSWORD=你在第四步设置的密码
MYSQL_DATABASE=follow_monitor

JWT_SECRET=改成随机长字符串

HOST=0.0.0.0
PORT=8000
SERVE_STATIC=true

CORS_ORIGINS=https://你的域名.com
```

4. 保存

> 数据库已通过 SQL 导入，**无需**再执行 init-db。

---

## 六、Supervisor 守护进程（可视化）

1. 左侧 **软件商店** → 已安装 → **Supervisor管理器** → **设置**

2. 点击 **添加守护进程**：

| 配置项 | 填写内容 |
|--------|----------|
| 名称 | `follow-monitor` |
| 启动用户 | `root` 或 `www` |
| 运行目录 | `/www/wwwroot/follow-monitor/follow-monitor` |
| 启动命令 | `/www/wwwroot/follow-monitor/follow-monitor/start.sh` |
| 进程数量 | `1` |

3. 保存后点击 **启动**

4. 状态显示 **RUNNING** 即成功

5. 若失败，点 **日志** 查看原因（常见：`.env` 数据库密码错误、端口被占用）

---

## 七、添加网站 + 反向代理

### 方式 A：域名反代到 8000 端口（推荐）

1. 左侧 **网站** → **添加站点**
   - 域名：填你的域名（如 `monitor.example.com`）
   - PHP 版本：**纯静态** 或 **不创建 PHP**
   - 根目录可随意（静态由后端程序提供）

2. 站点列表 → 该域名 → **设置**

3. **反向代理** → **添加反向代理**
   - 代理名称：`follow-monitor`
   - 目标 URL：`http://127.0.0.1:8000`
   - 发送域名：`$host`
   - 开启 **缓存** 可关闭

4. **配置文件** 中确认存在：

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

5. **SSL** → **Let's Encrypt** 申请 HTTPS（可选但推荐）

6. 保存

### 访问地址

| 页面 | 地址 |
|------|------|
| 用户端 | `https://你的域名/` |
| 管理端 | `https://你的域名/admin/` |
| 健康检查 | `https://你的域名/api/health` |

---

## 八、防火墙与安全组

1. 宝塔 **安全** → 放行 `80`、`443`（HTTP/HTTPS）
2. **不要** 对公网放行 `8000`（仅本机 Nginx 反代访问）
3. 云服务器控制台安全组同样放行 80、443

---

## 九、验证部署

1. 浏览器打开 `https://你的域名/api/health`  
   应返回：`{"status":"ok",...}`

2. 管理端 `https://你的域名/admin/`  
   - 账号：`admin@admin.com`  
   - 密码：`Admin888*`

3. 用户端 `https://你的域名/`  
   - 账号：`xiaoman@qq.com`  
   - 密码：该账号在库中的密码

---

## 十、常见问题

### 502 Bad Gateway
- Supervisor 中进程未 RUNNING → 查看日志
- `.env` 数据库连接错误 → 检查 MySQL 账号密码

### 页面空白 / 404
- 确认 `SERVE_STATIC=true`
- 确认 `frontend-user/dist` 和 `frontend-admin/dist` 存在

### TikTok 监控连不上
- 服务器需能访问 TikTok，在 `.env` 配置 `HTTPS_PROXY`
- 每个监控任务需配置独立 Sign API Key

### 更新程序
1. 本地重新 `./scripts/build_release.sh`
2. 上传新 `tar.gz` 到服务器解压覆盖（保留 `.env` 和 `data/`）
3. Supervisor 中 **重启** `follow-monitor`

### 更新数据库
1. 本地 `./scripts/export_mysql.sh`
2. phpMyAdmin 导入新 SQL（或仅导入变更表）

---

## 本地账号（当前 SQL 备份内）

| 账号 | 角色 | 密码 |
|------|------|------|
| admin@admin.com | 管理员 | Admin888* |
| xiaoman@qq.com | 普通用户 | 以数据库中为准 |

上线后建议在管理后台修改密码。
