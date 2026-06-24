from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.crypto import decrypt_secret, encrypt_secret, secret_fingerprint, token_hint
from app.models import (
    FollowEvent,
    JoinEvent,
    MonitorTask,
    SignApiKey,
    Streamer,
    TelegramBot,
    TelegramGroup,
    User,
)


def normalize_unique_id(value: str) -> str:
    return value.strip().lstrip("@")


def tiktok_profile_url(unique_id: str) -> str:
    return f"https://www.tiktok.com/@{normalize_unique_id(unique_id)}"


def normalize_sign_api_key(value: str) -> str:
    return value.strip()


def sign_api_key_fingerprint(value: str) -> str:
    return secret_fingerprint(normalize_sign_api_key(value))


def assert_sign_api_key_unique_globally(
    db: Session,
    sign_api_key: str,
    *,
    exclude_key_id: Optional[int] = None,
) -> None:
    """每个 API Key 全局只能入库一次。"""
    fp = sign_api_key_fingerprint(sign_api_key)
    query = select(SignApiKey.id).where(SignApiKey.sign_api_key_hash == fp)
    if exclude_key_id is not None:
        query = query.where(SignApiKey.id != exclude_key_id)
    existing_id = db.scalar(query.limit(1))
    if existing_id is not None:
        raise ValueError("该 API Key 已存在于系统中（跨账户也不可重复）")


def get_owned_sign_api_key(db: Session, user_id: int, key_id: int) -> Optional[SignApiKey]:
    return db.scalar(
        select(SignApiKey).where(SignApiKey.id == key_id, SignApiKey.user_id == user_id)
    )


def decrypt_sign_api_key_row(row: SignApiKey) -> str:
    return decrypt_secret(row.sign_api_key_encrypted)


def create_sign_api_key(
    db: Session,
    user: User,
    sign_api_key: str,
    *,
    label: Optional[str] = None,
) -> SignApiKey:
    normalized = normalize_sign_api_key(sign_api_key)
    if len(normalized) < 20:
        raise ValueError("监控 API Key 格式无效")
    assert_sign_api_key_unique_globally(db, normalized)
    row = SignApiKey(
        user_id=user.id,
        label=(label or "").strip() or None,
        sign_api_key_encrypted=encrypt_secret(normalized),
        sign_api_key_hash=sign_api_key_fingerprint(normalized),
    )
    db.add(row)
    db.flush()
    return row


def assert_sign_api_key_available(
    db: Session,
    key_id: int,
    *,
    user_id: int,
    exclude_task_id: Optional[int] = None,
) -> SignApiKey:
    row = get_owned_sign_api_key(db, user_id, key_id)
    if row is None:
        raise ValueError("API Key 不存在或不属于当前用户")
    bound_task_id = db.scalar(
        select(MonitorTask.id).where(MonitorTask.sign_api_key_id == key_id).limit(1)
    )
    if bound_task_id is not None and bound_task_id != exclude_task_id:
        raise ValueError("该 API Key 已被监控任务占用")
    return row


def bind_task_sign_api_key(
    db: Session,
    task: MonitorTask,
    user: User,
    *,
    sign_api_key_id: Optional[int] = None,
    sign_api_key: Optional[str] = None,
) -> SignApiKey:
    if sign_api_key_id is not None and sign_api_key:
        raise ValueError("请选择已有 API Key 或输入新 Key，不能同时填写")
    if sign_api_key_id is None and not sign_api_key:
        raise ValueError("请选择或输入 API Key")

    if sign_api_key_id is not None:
        row = assert_sign_api_key_available(
            db, sign_api_key_id, user_id=user.id, exclude_task_id=task.id
        )
    else:
        row = create_sign_api_key(db, user, sign_api_key or "")

    task.sign_api_key_id = row.id
    normalized = decrypt_sign_api_key_row(row)
    task.sign_api_key_encrypted = row.sign_api_key_encrypted
    task.sign_api_key_hash = row.sign_api_key_hash
    task.sign_api_key_hint = token_hint(normalized)
    return row


def apply_task_sign_api_key(task: MonitorTask, sign_api_key: str) -> None:
    normalized = normalize_sign_api_key(sign_api_key)
    if len(normalized) < 20:
        raise ValueError("监控 API Key 格式无效")
    task.sign_api_key_encrypted = encrypt_secret(normalized)
    task.sign_api_key_hash = sign_api_key_fingerprint(normalized)
    task.sign_api_key_hint = token_hint(normalized)


def sign_api_key_usage(db: Session, key_id: int) -> Optional[dict[str, Any]]:
    task = db.scalar(
        select(MonitorTask)
        .options(joinedload(MonitorTask.streamer))
        .where(MonitorTask.sign_api_key_id == key_id)
        .limit(1)
    )
    if task is None:
        return None
    return {
        "task_id": task.id,
        "streamer_unique_id": task.streamer.unique_id,
    }


def parse_rate_limit_snapshot(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        import json

        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("daily_remaining") is None and data.get("raw"):
        from app.euler_client import summarize_rate_limits

        return summarize_rate_limits(data)
    return data


def sign_api_key_to_dict(db: Session, row: SignApiKey) -> dict[str, Any]:
    usage = sign_api_key_usage(db, row.id)
    limits = parse_rate_limit_snapshot(row.rate_limit_snapshot)
    return {
        "id": row.id,
        "label": row.label,
        "sign_api_key": decrypt_sign_api_key_row(row),
        "in_use": usage is not None,
        "usage": usage,
        "rate_limits": limits,
        "rate_limit_checked_at": row.rate_limit_checked_at,
        "created_at": row.created_at,
    }


def task_sign_api_key_value(task: MonitorTask) -> Optional[str]:
    if task.sign_api_key is not None:
        try:
            return decrypt_sign_api_key_row(task.sign_api_key)
        except ValueError:
            pass
    if task.sign_api_key_encrypted:
        try:
            return decrypt_secret(task.sign_api_key_encrypted)
        except ValueError:
            return None
    return None


def task_to_dict(task: MonitorTask) -> dict:
    return {
        "id": task.id,
        "enabled": task.enabled,
        "status": task.status,
        "last_error": task.last_error,
        "join_rate_limit_per_minute": task.join_rate_limit_per_minute,
        "follow_bot_id": task.follow_bot_id,
        "follow_group_id": task.follow_group_id,
        "join_bot_id": task.join_bot_id,
        "join_group_id": task.join_group_id,
        "sign_api_key_id": task.sign_api_key_id,
        "sign_api_key": task_sign_api_key_value(task),
        "sign_api_key_hint": task.sign_api_key_hint,
        "created_at": task.created_at,
        "streamer": {
            "id": task.streamer.id,
            "unique_id": task.streamer.unique_id,
            "display_name": task.streamer.display_name,
            "created_at": task.streamer.created_at,
        },
    }


def assert_streamer_unique_globally(
    db: Session,
    unique_id: str,
    *,
    user_id: int,
) -> None:
    """主播 ID 全局唯一：任一账号已占用则其他账号不可再添加。"""
    uid = normalize_unique_id(unique_id)
    existing = db.scalar(select(Streamer).where(Streamer.unique_id == uid))
    if existing is None:
        return
    if existing.user_id == user_id:
        raise ValueError("该主播已存在")
    raise ValueError(f"主播 @{uid} 已被其他账号监控")


def assert_streamer_available_for_monitor(
    db: Session,
    unique_id: str,
    *,
    user_id: int,
) -> None:
    """同一主播 ID 全局只能有一个监控任务。"""
    uid = normalize_unique_id(unique_id)
    other_task = db.scalar(
        select(MonitorTask.id)
        .join(Streamer, Streamer.id == MonitorTask.streamer_id)
        .where(Streamer.unique_id == uid, MonitorTask.user_id != user_id)
        .limit(1)
    )
    if other_task is not None:
        raise ValueError(f"主播 @{uid} 已被其他账号监控")

    own_task = db.scalar(
        select(MonitorTask.id)
        .join(Streamer, Streamer.id == MonitorTask.streamer_id)
        .where(Streamer.unique_id == uid, MonitorTask.user_id == user_id)
        .limit(1)
    )
    if own_task is not None:
        raise ValueError("您已在监控该主播")


def count_user_bots(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(TelegramBot).where(TelegramBot.user_id == user_id)
    ) or 0


def count_user_groups(db: Session, user_id: int) -> int:
    """按唯一 chat_id 计数（同一 Telegram 群绑多个 Bot 只占 1 个配额）。"""
    return (
        db.scalar(
            select(func.count(func.distinct(TelegramGroup.chat_id))).where(
                TelegramGroup.user_id == user_id
            )
        )
        or 0
    )


def count_user_group_bindings(db: Session, user_id: int) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(TelegramGroup).where(
                TelegramGroup.user_id == user_id
            )
        )
        or 0
    )


def user_has_chat_id(db: Session, user_id: int, chat_id: str) -> bool:
    row = db.scalar(
        select(TelegramGroup.id).where(
            TelegramGroup.user_id == user_id,
            TelegramGroup.chat_id == chat_id,
        ).limit(1)
    )
    return row is not None


def count_user_tasks(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(MonitorTask).where(MonitorTask.user_id == user_id)
    ) or 0


def assert_quota(current: int, limit: int, label: str) -> None:
    if current >= limit:
        raise ValueError(f"{label}已达上限（{limit}）")


def get_owned_bot(db: Session, user_id: int, bot_id: int) -> Optional[TelegramBot]:
    return db.scalar(
        select(TelegramBot).where(
            TelegramBot.id == bot_id,
            TelegramBot.user_id == user_id,
            TelegramBot.is_active.is_(True),
        )
    )


def get_owned_group(db: Session, user_id: int, group_id: int) -> Optional[TelegramGroup]:
    return db.scalar(
        select(TelegramGroup).where(
            TelegramGroup.id == group_id,
            TelegramGroup.user_id == user_id,
            TelegramGroup.is_active.is_(True),
        )
    )


def get_owned_streamer(db: Session, user_id: int, streamer_id: int) -> Optional[Streamer]:
    return db.scalar(
        select(Streamer).where(
            Streamer.id == streamer_id,
            Streamer.user_id == user_id,
        )
    )


def get_owned_task(db: Session, user_id: int, task_id: int) -> Optional[MonitorTask]:
    return db.scalar(
        select(MonitorTask).where(
            MonitorTask.id == task_id,
            MonitorTask.user_id == user_id,
        )
    )


def assert_follow_bot_available_for_push(
    db: Session,
    user_id: int,
    follow_bot_id: int,
    *,
    exclude_task_id: Optional[int] = None,
) -> None:
    stmt = select(MonitorTask.id).where(
        MonitorTask.user_id == user_id,
        MonitorTask.enabled.is_(True),
        MonitorTask.follow_bot_id == follow_bot_id,
    )
    if exclude_task_id is not None:
        stmt = stmt.where(MonitorTask.id != exclude_task_id)
    if db.scalar(stmt.limit(1)) is not None:
        raise ValueError("该机器人正被其他启用的监控任务用于推送，请选择其他机器人")


def validate_task_bindings(
    db: Session,
    user: User,
    *,
    follow_bot_id: Optional[int],
    follow_group_id: Optional[int],
    join_bot_id: Optional[int] = None,
    join_group_id: Optional[int] = None,
    exclude_task_id: Optional[int] = None,
) -> None:
    if not follow_bot_id or not follow_group_id:
        raise ValueError("请选择机器人和群组")

    if not get_owned_bot(db, user.id, follow_bot_id):
        raise ValueError("机器人不存在或不属于当前用户")

    assert_follow_bot_available_for_push(
        db, user.id, follow_bot_id, exclude_task_id=exclude_task_id
    )

    group = get_owned_group(db, user.id, follow_group_id)
    if not group:
        raise ValueError("群组不存在或不属于当前用户")
    if group.bot_id != follow_bot_id:
        raise ValueError("群组不属于所选机器人，请从该机器人导入群组")

    if join_bot_id or join_group_id:
        raise ValueError("暂不支持新进直播间推送")


def user_me_payload(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "max_monitors": user.max_monitors,
        "max_bots": user.max_bots,
        "max_groups": user.max_groups,
        "monitor_count": count_user_tasks(db, user.id),
        "bot_count": count_user_bots(db, user.id),
        "group_count": count_user_groups(db, user.id),
        "group_binding_count": count_user_group_bindings(db, user.id),
    }


def user_dashboard_stats(db: Session, user_id: int) -> dict[str, int]:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    local_tz = ZoneInfo("Asia/Shanghai")
    now_local = datetime.now(local_tz)
    today = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    total_task_count = count_user_tasks(db, user_id)
    active_task_count = (
        db.scalar(
            select(func.count())
            .select_from(MonitorTask)
            .where(MonitorTask.user_id == user_id, MonitorTask.enabled.is_(True))
        )
        or 0
    )
    inactive_task_count = total_task_count - active_task_count

    sign_key_total = (
        db.scalar(
            select(func.count()).select_from(SignApiKey).where(SignApiKey.user_id == user_id)
        )
        or 0
    )
    sign_key_in_use = (
        db.scalar(
            select(func.count())
            .select_from(SignApiKey)
            .where(
                SignApiKey.user_id == user_id,
                SignApiKey.id.in_(
                    select(MonitorTask.sign_api_key_id).where(
                        MonitorTask.user_id == user_id,
                        MonitorTask.sign_api_key_id.is_not(None),
                    )
                ),
            )
        )
        or 0
    )
    sign_key_idle = sign_key_total - sign_key_in_use

    bot_total = count_user_bots(db, user_id)
    group_total = count_user_groups(db, user_id)
    group_pushing = (
        db.scalar(
            select(func.count(func.distinct(TelegramGroup.chat_id)))
            .select_from(TelegramGroup)
            .join(
                MonitorTask,
                or_(
                    MonitorTask.follow_group_id == TelegramGroup.id,
                    MonitorTask.join_group_id == TelegramGroup.id,
                ),
            )
            .where(
                MonitorTask.user_id == user_id,
                MonitorTask.enabled.is_(True),
                TelegramGroup.user_id == user_id,
            )
        )
        or 0
    )
    group_idle = max(group_total - group_pushing, 0)

    pushing_bot_ids: set[int] = set()
    enabled_tasks = db.scalars(
        select(MonitorTask).where(MonitorTask.user_id == user_id, MonitorTask.enabled.is_(True))
    ).all()
    for task in enabled_tasks:
        if task.follow_bot_id:
            pushing_bot_ids.add(task.follow_bot_id)
        if task.join_bot_id:
            pushing_bot_ids.add(task.join_bot_id)

    bot_pushing = len(pushing_bot_ids)
    bot_idle = max(bot_total - bot_pushing, 0)

    follow_total = (
        db.scalar(
            select(func.count()).select_from(FollowEvent).where(FollowEvent.user_id == user_id)
        )
        or 0
    )
    follow_today = (
        db.scalar(
            select(func.count())
            .select_from(FollowEvent)
            .where(FollowEvent.user_id == user_id, FollowEvent.detected_at >= today)
        )
        or 0
    )
    join_total = (
        db.scalar(
            select(func.count()).select_from(JoinEvent).where(JoinEvent.user_id == user_id)
        )
        or 0
    )
    join_today = (
        db.scalar(
            select(func.count())
            .select_from(JoinEvent)
            .where(JoinEvent.user_id == user_id, JoinEvent.detected_at >= today)
        )
        or 0
    )

    return {
        "active_task_count": active_task_count,
        "inactive_task_count": inactive_task_count,
        "total_task_count": total_task_count,
        "sign_key_in_use": sign_key_in_use,
        "sign_key_idle": sign_key_idle,
        "sign_key_total": sign_key_total,
        "bot_pushing": bot_pushing,
        "bot_idle": bot_idle,
        "bot_total": bot_total,
        "group_pushing": group_pushing,
        "group_idle": group_idle,
        "group_total": group_total,
        "follow_today": follow_today,
        "follow_total": follow_total,
        "join_today": join_today,
        "join_total": join_total,
    }


def group_to_dict(group: TelegramGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "chat_id": group.chat_id,
        "bot_id": group.bot_id,
        "is_active": group.is_active,
        "created_at": group.created_at,
    }
