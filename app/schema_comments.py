"""数据库表/字段中文注释（单一数据源）。"""

from __future__ import annotations

from typing import Optional

# 表名 -> 表级中文说明
TABLE_COMMENTS: dict[str, str] = {
    "users": "系统用户账号表",
    "telegram_bots": "Telegram 机器人配置表",
    "telegram_groups": "Telegram 群组配置表",
    "streamers": "TikTok 主播表（unique_id 全局唯一）",
    "sign_api_keys": "Euler 签名 API Key 池（每个 Key 全局唯一）",
    "monitor_tasks": "直播间监控任务表",
    "follow_events": "新关注事件流水表",
    "join_events": "新进直播间事件流水表",
    "audit_logs": "管理端操作审计日志表",
    "db_schema_comments": "数据库表/字段中文注释字典（元数据）",
    # CLI 单主播脚本库 data/follows.db
    "follows": "CLI 版新关注去重记录表",
    "joins": "CLI 版新进直播间去重记录表",
}

# (表名, 字段名) -> 字段中文说明；字段名为空字符串表示表级注释占位（与 TABLE_COMMENTS 同步）
COLUMN_COMMENTS: dict[tuple[str, str], str] = {
    # users
    ("users", "id"): "主键 ID",
    ("users", "email"): "登录邮箱",
    ("users", "password_hash"): "登录密码（明文存储）",
    ("users", "password_plain"): "密码明文副本（与 password_hash 同步）",
    ("users", "role"): "角色：user / admin",
    ("users", "status"): "账号状态：active / disabled",
    ("users", "max_monitors"): "该用户可创建的监控任务上限",
    ("users", "max_bots"): "该用户可添加的 Telegram Bot 上限",
    ("users", "max_groups"): "该用户可添加的 Telegram 群组上限",
    ("users", "created_at"): "创建时间（UTC）",
    ("users", "updated_at"): "最后更新时间（UTC）",
    # telegram_bots
    ("telegram_bots", "id"): "主键 ID",
    ("telegram_bots", "user_id"): "所属用户 ID",
    ("telegram_bots", "name"): "Bot 备注名称",
    ("telegram_bots", "bot_telegram_id"): "Telegram Bot 数字 ID（getMe 回填）",
    ("telegram_bots", "username"): "Bot 用户名（不含 @）",
    ("telegram_bots", "bot_token_encrypted"): "Bot Token 加密存储",
    ("telegram_bots", "token_hint"): "Token 脱敏提示（首尾各几位）",
    ("telegram_bots", "is_active"): "是否启用",
    ("telegram_bots", "created_at"): "创建时间（UTC）",
    # telegram_groups
    ("telegram_groups", "id"): "主键 ID",
    ("telegram_groups", "user_id"): "所属用户 ID",
    ("telegram_groups", "bot_id"): "关联 Bot ID（推送时使用）",
    ("telegram_groups", "name"): "群组备注名称",
    ("telegram_groups", "chat_id"): "Telegram 群组 chat_id",
    ("telegram_groups", "is_active"): "是否启用",
    ("telegram_groups", "created_at"): "创建时间（UTC）",
    # streamers
    ("streamers", "id"): "主键 ID",
    ("streamers", "user_id"): "添加该主播的用户 ID",
    ("streamers", "unique_id"): "TikTok 主播 unique_id（全局唯一）",
    ("streamers", "display_name"): "展示昵称（可选）",
    ("streamers", "created_at"): "创建时间（UTC）",
    # sign_api_keys
    ("sign_api_keys", "id"): "主键 ID",
    ("sign_api_keys", "user_id"): "所属用户 ID",
    ("sign_api_keys", "label"): "Key 备注名称",
    ("sign_api_keys", "sign_api_key_encrypted"): "Euler API Key 加密存储",
    ("sign_api_keys", "sign_api_key_hash"): "Key 指纹哈希（全局唯一，用于去重）",
    ("sign_api_keys", "rate_limit_snapshot"): "最近一次配额查询结果（JSON）",
    ("sign_api_keys", "rate_limit_checked_at"): "最近一次配额查询时间（UTC）",
    ("sign_api_keys", "created_at"): "创建时间（UTC）",
    # monitor_tasks
    ("monitor_tasks", "id"): "主键 ID",
    ("monitor_tasks", "user_id"): "所属用户 ID",
    ("monitor_tasks", "streamer_id"): "监控的主播 ID",
    ("monitor_tasks", "follow_bot_id"): "新关注推送使用的 Bot ID",
    ("monitor_tasks", "follow_group_id"): "新关注推送目标群组 ID",
    ("monitor_tasks", "join_bot_id"): "新进直播间推送使用的 Bot ID",
    ("monitor_tasks", "join_group_id"): "新进直播间推送目标群组 ID",
    ("monitor_tasks", "enabled"): "是否启用监控",
    ("monitor_tasks", "status"): "运行状态：idle / connecting / live / offline / rate_limited / retrying / error",
    ("monitor_tasks", "last_error"): "最近一次错误信息",
    ("monitor_tasks", "join_rate_limit_per_minute"): "进场推送每分钟上限",
    ("monitor_tasks", "sign_api_key_id"): "绑定的 API Key 池记录 ID（一对一）",
    ("monitor_tasks", "sign_api_key_encrypted"): "遗留字段：任务内嵌 Key 加密值（已迁移至 Key 池）",
    ("monitor_tasks", "sign_api_key_hash"): "遗留字段：任务内嵌 Key 哈希",
    ("monitor_tasks", "sign_api_key_hint"): "遗留字段：任务内嵌 Key 脱敏提示",
    ("monitor_tasks", "created_at"): "创建时间（UTC）",
    ("monitor_tasks", "updated_at"): "最后更新时间（UTC）",
    # follow_events
    ("follow_events", "id"): "主键 ID",
    ("follow_events", "user_id"): "所属用户 ID",
    ("follow_events", "task_id"): "来源监控任务 ID",
    ("follow_events", "streamer_unique_id"): "被关注的主播 unique_id",
    ("follow_events", "follower_unique_id"): "关注者的 TikTok unique_id",
    ("follow_events", "follower_nickname"): "关注者昵称",
    ("follow_events", "detected_at"): "检测到关注的时间（UTC）",
    # join_events
    ("join_events", "id"): "主键 ID",
    ("join_events", "user_id"): "所属用户 ID",
    ("join_events", "task_id"): "来源监控任务 ID",
    ("join_events", "streamer_unique_id"): "直播间主播 unique_id",
    ("join_events", "guest_unique_id"): "进入直播间的用户 unique_id",
    ("join_events", "guest_nickname"): "进入直播间的用户昵称",
    ("join_events", "detected_at"): "检测到进场的时间（UTC）",
    # audit_logs
    ("audit_logs", "id"): "主键 ID",
    ("audit_logs", "admin_id"): "执行操作的管理员用户 ID",
    ("audit_logs", "action"): "操作类型标识",
    ("audit_logs", "target_user_id"): "被操作的目标用户 ID",
    ("audit_logs", "detail"): "操作详情（JSON 或文本）",
    ("audit_logs", "created_at"): "操作时间（UTC）",
    # db_schema_comments
    ("db_schema_comments", "table_name"): "表名",
    ("db_schema_comments", "column_name"): "字段名（空字符串表示表级注释）",
    ("db_schema_comments", "comment_zh"): "中文说明",
    # CLI follows
    ("follows", "id"): "主键 ID",
    ("follows", "follower_unique_id"): "关注者 TikTok unique_id",
    ("follows", "follower_nickname"): "关注者昵称",
    ("follows", "streamer_unique_id"): "被关注主播 unique_id",
    ("follows", "detected_at"): "检测到关注的时间（ISO 文本）",
    # CLI joins
    ("joins", "id"): "主键 ID",
    ("joins", "user_unique_id"): "进入直播间的用户 unique_id",
    ("joins", "nickname"): "用户昵称",
    ("joins", "streamer_unique_id"): "直播间主播 unique_id",
    ("joins", "detected_at"): "检测到进场的时间（ISO 文本）",
}


def table_comment(table_name: str) -> Optional[str]:
    return TABLE_COMMENTS.get(table_name)


def column_comment(table_name: str, column_name: str) -> Optional[str]:
    return COLUMN_COMMENTS.get((table_name, column_name))


def iter_comment_rows() -> list[tuple[str, str, str]]:
    """生成写入 db_schema_comments 的行：(table_name, column_name, comment_zh)。"""
    rows: list[tuple[str, str, str]] = []
    seen_tables: set[str] = set()
    for table_name, comment in TABLE_COMMENTS.items():
        rows.append((table_name, "", comment))
        seen_tables.add(table_name)
    for (table_name, column_name), comment in COLUMN_COMMENTS.items():
        if table_name in seen_tables or table_name in TABLE_COMMENTS:
            rows.append((table_name, column_name, comment))
    return rows
