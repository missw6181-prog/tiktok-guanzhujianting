from typing import List, Literal, Optional

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import create_access_token
from app.event_export import (
    build_follow_filters,
    build_join_filters,
    count_rows,
    export_content,
    export_max_rows,
    fetch_follow_rows,
    fetch_join_rows,
)
from app.crypto import decrypt_secret, encrypt_secret, hash_password, token_hint, verify_password
from app.database import get_db
from app.deps import get_current_user
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
from app.monitor.manager import get_monitor_manager
from app.schemas import (
    BotCreate,
    BotPreviewRequest,
    BotPreviewResponse,
    BotResponse,
    DiscoveredGroupResponse,
    EventStatsResponse,
    FollowEventResponse,
    GroupBatchImportRequest,
    GroupBatchImportResponse,
    GroupCreate,
    GroupRefreshNamesResponse,
    GroupResponse,
    JoinEventResponse,
    LoginRequest,
    StreamerCreate,
    StreamerResponse,
    PaginatedFollowEventsResponse,
    PaginatedJoinEventsResponse,
    SignApiKeyCreate,
    SignApiKeyBatchCreate,
    SignApiKeyBatchFailure,
    SignApiKeyBatchResponse,
    SignApiKeyResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TokenResponse,
    UserDashboardStatsResponse,
    UserMeResponse,
)
from app.settings import get_settings
from app.euler_client import fetch_sign_api_rate_limits, rate_limits_to_json
from app.telegram_client import fetch_bot_chats, fetch_bot_info, fetch_chat_title
from app.services import (
    assert_quota,
    assert_streamer_available_for_monitor,
    assert_streamer_unique_globally,
    bind_task_sign_api_key,
    count_user_bots,
    count_user_groups,
    count_user_tasks,
    create_sign_api_key,
    get_owned_bot,
    get_owned_sign_api_key,
    get_owned_streamer,
    get_owned_task,
    normalize_unique_id,
    sign_api_key_to_dict,
    task_to_dict,
    user_dashboard_stats,
    user_has_chat_id,
    user_me_payload,
    validate_task_bindings,
    group_to_dict,
    decrypt_sign_api_key_row,
)

router = APIRouter(prefix="/api", tags=["user"])

_LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def _normalize_streamer_filter(streamer_unique_id: Optional[str]) -> Optional[str]:
    if not streamer_unique_id:
        return None
    value = streamer_unique_id.strip().lstrip("@")
    return value or None


def _today_start_utc() -> datetime:
    now_local = datetime.now(_LOCAL_TZ)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc)


def _bot_response(bot: TelegramBot) -> BotResponse:
    return BotResponse(
        id=bot.id,
        name=bot.name,
        bot_telegram_id=bot.bot_telegram_id,
        username=bot.username,
        bot_token=decrypt_secret(bot.bot_token_encrypted),
        is_active=bot.is_active,
        created_at=bot.created_at,
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, role=user.role, email=user.email)


@router.get("/me", response_model=UserMeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserMeResponse:
    return UserMeResponse(**user_me_payload(db, user))


@router.get("/dashboard/stats", response_model=UserDashboardStatsResponse)
def dashboard_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDashboardStatsResponse:
    return UserDashboardStatsResponse(**user_dashboard_stats(db, user.id))


@router.get("/bots", response_model=list[BotResponse])
def list_bots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bots = db.scalars(
        select(TelegramBot).where(TelegramBot.user_id == user.id).order_by(TelegramBot.id)
    ).all()
    return [_bot_response(b) for b in bots]


@router.post("/bots/preview", response_model=BotPreviewResponse)
def preview_bot(
    body: BotPreviewRequest,
    user: User = Depends(get_current_user),
):
    _ = user
    settings = get_settings()
    try:
        info = fetch_bot_info(body.bot_token, settings.proxy_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BotPreviewResponse(
        bot_telegram_id=info.bot_telegram_id,
        username=info.username,
        display_name=info.display_name,
    )


@router.post("/bots", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
def create_bot(
    body: BotCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        assert_quota(count_user_bots(db, user.id), user.max_bots, "机器人")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    settings = get_settings()
    try:
        info = fetch_bot_info(body.bot_token, settings.proxy_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    duplicate = db.scalar(
        select(TelegramBot).where(
            TelegramBot.user_id == user.id,
            TelegramBot.bot_telegram_id == info.bot_telegram_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该机器人已添加")

    display_name = body.name.strip() if body.name and body.name.strip() else info.display_name
    bot = TelegramBot(
        user_id=user.id,
        name=display_name,
        bot_telegram_id=info.bot_telegram_id,
        username=info.username or None,
        bot_token_encrypted=encrypt_secret(body.bot_token.strip()),
        token_hint=token_hint(body.bot_token),
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return _bot_response(bot)


@router.delete("/bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(TelegramBot).where(TelegramBot.id == bot_id, TelegramBot.user_id == user.id)
    )
    if bot is None:
        raise HTTPException(status_code=404, detail="机器人不存在")
    db.delete(bot)
    db.commit()
    get_monitor_manager().request_sync()


@router.get("/bots/{bot_id}/discover-groups", response_model=list[DiscoveredGroupResponse])
def discover_bot_groups(
    bot_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = get_owned_bot(db, user.id, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="机器人不存在")

    settings = get_settings()
    try:
        token = decrypt_secret(bot.bot_token_encrypted)
        chats = fetch_bot_chats(token, settings.proxy_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing_ids = {
        row
        for row in db.scalars(
            select(TelegramGroup.chat_id).where(
                TelegramGroup.user_id == user.id,
                TelegramGroup.bot_id == bot_id,
            )
        ).all()
    }

    return [
        DiscoveredGroupResponse(
            chat_id=chat.chat_id,
            name=chat.name,
            chat_type=chat.chat_type,
        )
        for chat in chats
        if chat.chat_id not in existing_ids
    ]


@router.get("/groups", response_model=list[GroupResponse])
def list_groups(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    bot_id: Optional[int] = Query(default=None),
):
    stmt = select(TelegramGroup).where(TelegramGroup.user_id == user.id)
    if bot_id is not None:
        if not get_owned_bot(db, user.id, bot_id):
            raise HTTPException(status_code=404, detail="机器人不存在")
        stmt = stmt.where(TelegramGroup.bot_id == bot_id)
    groups = db.scalars(stmt.order_by(TelegramGroup.id)).all()
    return [GroupResponse(**group_to_dict(g)) for g in groups]


@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat_id = body.chat_id.strip()
    if not user_has_chat_id(db, user.id, chat_id):
        try:
            assert_quota(count_user_groups(db, user.id), user.max_groups, "群组")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    group = TelegramGroup(
        user_id=user.id,
        name=body.name.strip(),
        chat_id=body.chat_id.strip(),
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return GroupResponse(
        id=group.id,
        name=group.name,
        chat_id=group.chat_id,
        is_active=group.is_active,
        created_at=group.created_at,
    )


@router.post("/groups/batch-import", response_model=GroupBatchImportResponse)
def batch_import_groups(
    body: GroupBatchImportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not get_owned_bot(db, user.id, body.bot_id):
        raise HTTPException(status_code=404, detail="机器人不存在")

    imported_groups: List[GroupResponse] = []
    skipped = 0
    unique_used = count_user_groups(db, user.id)

    for item in body.items:
        chat_id = item.chat_id.strip()
        exists = db.scalar(
            select(TelegramGroup.id).where(
                TelegramGroup.user_id == user.id,
                TelegramGroup.chat_id == chat_id,
                TelegramGroup.bot_id == body.bot_id,
            )
        )
        if exists:
            skipped += 1
            continue

        is_new_chat = not user_has_chat_id(db, user.id, chat_id)
        if is_new_chat and unique_used >= user.max_groups:
            skipped += 1
            continue

        group = TelegramGroup(
            user_id=user.id,
            bot_id=body.bot_id,
            name=item.name.strip(),
            chat_id=chat_id,
        )
        db.add(group)
        db.flush()
        imported_groups.append(GroupResponse(**group_to_dict(group)))
        if is_new_chat:
            unique_used += 1

    db.commit()
    return GroupBatchImportResponse(
        imported=len(imported_groups),
        skipped=skipped,
        groups=imported_groups,
    )


@router.post("/groups/refresh-names", response_model=GroupRefreshNamesResponse)
def refresh_group_names(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    groups = list(
        db.scalars(select(TelegramGroup).where(TelegramGroup.user_id == user.id)).all()
    )

    title_by_chat: dict[str, str] = {}
    error_by_chat: dict[str, str] = {}

    for chat_id in {g.chat_id for g in groups}:
        sample = next((g for g in groups if g.chat_id == chat_id and g.bot_id), None)
        if sample is None:
            error_by_chat[chat_id] = "未绑定机器人，无法刷新"
            continue

        bot = get_owned_bot(db, user.id, sample.bot_id)
        if bot is None:
            error_by_chat[chat_id] = "机器人不存在或已删除"
            continue

        try:
            token = decrypt_secret(bot.bot_token_encrypted)
            title_by_chat[chat_id] = fetch_chat_title(
                token, chat_id, settings.proxy_url
            )
        except ValueError as exc:
            error_by_chat[chat_id] = str(exc)

    updated = 0
    unchanged = 0
    failed: list = []

    for group in groups:
        if group.chat_id in error_by_chat:
            failed.append(
                {
                    "group_id": group.id,
                    "chat_id": group.chat_id,
                    "reason": error_by_chat[group.chat_id],
                }
            )
            continue

        new_name = title_by_chat[group.chat_id]
        if group.name != new_name:
            group.name = new_name
            updated += 1
        else:
            unchanged += 1

    db.commit()
    return GroupRefreshNamesResponse(
        updated=updated,
        unchanged=unchanged,
        failed=failed,
    )


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = db.scalar(
        select(TelegramGroup).where(
            TelegramGroup.id == group_id,
            TelegramGroup.user_id == user.id,
        )
    )
    if group is None:
        raise HTTPException(status_code=404, detail="群组不存在")
    db.delete(group)
    db.commit()
    get_monitor_manager().request_sync()


@router.get("/streamers", response_model=list[StreamerResponse])
def list_streamers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Streamer).where(Streamer.user_id == user.id).order_by(Streamer.id)
    ).all()
    return [
        StreamerResponse(
            id=s.id,
            unique_id=s.unique_id,
            display_name=s.display_name,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.post("/streamers", response_model=StreamerResponse, status_code=status.HTTP_201_CREATED)
def create_streamer(
    body: StreamerCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unique_id = normalize_unique_id(body.unique_id)
    try:
        assert_streamer_unique_globally(db, unique_id, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    streamer = Streamer(
        user_id=user.id,
        unique_id=unique_id,
        display_name=body.display_name,
    )
    db.add(streamer)
    db.commit()
    db.refresh(streamer)
    return StreamerResponse(
        id=streamer.id,
        unique_id=streamer.unique_id,
        display_name=streamer.display_name,
        created_at=streamer.created_at,
    )


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.scalars(
        select(MonitorTask)
        .options(joinedload(MonitorTask.streamer), joinedload(MonitorTask.sign_api_key))
        .where(MonitorTask.user_id == user.id)
        .order_by(MonitorTask.id)
    ).all()
    return [TaskResponse(**task_to_dict(task)) for task in tasks]


@router.get("/sign-keys", response_model=list[SignApiKeyResponse])
def list_sign_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SignApiKey).where(SignApiKey.user_id == user.id).order_by(SignApiKey.id)
    ).all()
    return [SignApiKeyResponse(**sign_api_key_to_dict(db, row)) for row in rows]


@router.get("/sign-keys/available", response_model=list[SignApiKeyResponse])
def list_available_sign_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    used_ids = select(MonitorTask.sign_api_key_id).where(MonitorTask.sign_api_key_id.is_not(None))
    rows = db.scalars(
        select(SignApiKey)
        .where(SignApiKey.user_id == user.id, SignApiKey.id.not_in(used_ids))
        .order_by(SignApiKey.id)
    ).all()
    return [SignApiKeyResponse(**sign_api_key_to_dict(db, row)) for row in rows]


@router.post("/sign-keys", response_model=SignApiKeyResponse, status_code=status.HTTP_201_CREATED)
def create_sign_key(
    body: SignApiKeyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = create_sign_api_key(db, user, body.sign_api_key, label=body.label)
        db.commit()
        db.refresh(row)
        return SignApiKeyResponse(**sign_api_key_to_dict(db, row))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sign-keys/batch", response_model=SignApiKeyBatchResponse)
def batch_create_sign_keys(
    body: SignApiKeyBatchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    imported_keys: List[SignApiKeyResponse] = []
    failed: List[SignApiKeyBatchFailure] = []
    seen: set[str] = set()

    for raw in body.sign_api_keys:
        key = raw.strip()
        if not key:
            continue
        if key in seen:
            failed.append(SignApiKeyBatchFailure(sign_api_key=key, reason="本批次内重复"))
            continue
        seen.add(key)
        try:
            row = create_sign_api_key(db, user, key, label=body.label)
            db.flush()
            imported_keys.append(SignApiKeyResponse(**sign_api_key_to_dict(db, row)))
        except ValueError as exc:
            failed.append(SignApiKeyBatchFailure(sign_api_key=key, reason=str(exc)))

    if imported_keys:
        db.commit()
    else:
        db.rollback()

    return SignApiKeyBatchResponse(
        imported=len(imported_keys),
        failed=failed,
        keys=imported_keys,
    )


@router.post("/sign-keys/{key_id}/refresh-limits", response_model=SignApiKeyResponse)
def refresh_sign_key_limits(
    key_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_owned_sign_api_key(db, user.id, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    settings = get_settings()
    try:
        raw = fetch_sign_api_rate_limits(
            decrypt_sign_api_key_row(row),
            proxy_url=settings.proxy_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    from datetime import datetime, timezone

    row.rate_limit_snapshot = rate_limits_to_json(raw)
    row.rate_limit_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return SignApiKeyResponse(**sign_api_key_to_dict(db, row))


@router.delete("/sign-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sign_key(
    key_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = get_owned_sign_api_key(db, user.id, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    in_use = db.scalar(
        select(MonitorTask.id).where(MonitorTask.sign_api_key_id == key_id).limit(1)
    )
    if in_use is not None:
        raise HTTPException(status_code=400, detail="该 API Key 正被监控任务使用，无法删除")
    db.delete(row)
    db.commit()


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        assert_quota(count_user_tasks(db, user.id), user.max_monitors, "监控任务")
        validate_task_bindings(
            db,
            user,
            follow_bot_id=body.follow_bot_id,
            follow_group_id=body.follow_group_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    streamer = get_owned_streamer(db, user.id, body.streamer_id)
    if streamer is None:
        raise HTTPException(status_code=404, detail="主播不存在")

    try:
        assert_streamer_available_for_monitor(db, streamer.unique_id, user_id=user.id)
        if not body.sign_api_key_id and not body.sign_api_key:
            raise ValueError("请选择或输入 API Key")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task = MonitorTask(
        user_id=user.id,
        streamer_id=streamer.id,
        follow_bot_id=body.follow_bot_id,
        follow_group_id=body.follow_group_id,
        join_bot_id=None,
        join_group_id=None,
        join_rate_limit_per_minute=body.join_rate_limit_per_minute,
        enabled=body.enabled,
        status="connecting" if body.enabled else "idle",
    )
    db.add(task)
    db.flush()
    try:
        bind_task_sign_api_key(
            db,
            task,
            user,
            sign_api_key_id=body.sign_api_key_id,
            sign_api_key=body.sign_api_key,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(task)
    task = db.scalar(
        select(MonitorTask)
        .options(joinedload(MonitorTask.streamer), joinedload(MonitorTask.sign_api_key))
        .where(MonitorTask.id == task.id)
    )
    get_monitor_manager().request_sync()
    return TaskResponse(**task_to_dict(task))


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    body: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(
        select(MonitorTask)
        .options(joinedload(MonitorTask.streamer), joinedload(MonitorTask.sign_api_key))
        .where(MonitorTask.id == task_id, MonitorTask.user_id == user.id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="监控任务不存在")

    if body.follow_bot_id is not None:
        task.follow_bot_id = body.follow_bot_id
    if body.follow_group_id is not None:
        task.follow_group_id = body.follow_group_id
    if body.join_rate_limit_per_minute is not None:
        task.join_rate_limit_per_minute = body.join_rate_limit_per_minute
    if body.enabled is not None:
        task.enabled = body.enabled
        if body.enabled:
            if task.sign_api_key_id or task.sign_api_key_encrypted:
                task.status = "connecting"
                task.last_error = None
        else:
            task.status = "idle"
            task.last_error = None
    task.join_bot_id = None
    task.join_group_id = None

    try:
        if body.sign_api_key_id is not None or body.sign_api_key:
            key_changed = body.sign_api_key is not None or (
                body.sign_api_key_id is not None
                and body.sign_api_key_id != task.sign_api_key_id
            )
            if key_changed:
                bind_task_sign_api_key(
                    db,
                    task,
                    user,
                    sign_api_key_id=body.sign_api_key_id,
                    sign_api_key=body.sign_api_key,
                )
        if task.enabled and not task.sign_api_key_id and not task.sign_api_key_encrypted:
            raise ValueError("启用监控前必须配置 API Key")
        validate_task_bindings(
            db,
            user,
            follow_bot_id=task.follow_bot_id,
            follow_group_id=task.follow_group_id,
            exclude_task_id=task.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(task)
    task = db.scalar(
        select(MonitorTask)
        .options(joinedload(MonitorTask.streamer), joinedload(MonitorTask.sign_api_key))
        .where(MonitorTask.id == task.id)
    )
    get_monitor_manager().request_sync()
    return TaskResponse(**task_to_dict(task))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = get_owned_task(db, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="监控任务不存在")
    db.delete(task)
    db.commit()
    get_monitor_manager().request_sync()


@router.get("/events/stats", response_model=EventStatsResponse)
def event_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    streamer_unique_id: Optional[str] = Query(default=None),
) -> EventStatsResponse:
    streamer = _normalize_streamer_filter(streamer_unique_id)
    today = _today_start_utc()
    follow_filters = [
        FollowEvent.user_id == user.id,
        FollowEvent.detected_at >= today,
    ]
    join_filters = [
        JoinEvent.user_id == user.id,
        JoinEvent.detected_at >= today,
    ]
    if streamer:
        follow_filters.append(FollowEvent.streamer_unique_id == streamer)
        join_filters.append(JoinEvent.streamer_unique_id == streamer)
    follow_today = db.scalar(select(func.count()).select_from(FollowEvent).where(*follow_filters)) or 0
    join_today = db.scalar(select(func.count()).select_from(JoinEvent).where(*join_filters)) or 0
    return EventStatsResponse(
        follow_today=follow_today,
        join_today=join_today,
        streamer_unique_id=streamer,
    )


@router.get("/events/follows", response_model=PaginatedFollowEventsResponse)
def list_follows(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    streamer_unique_id: Optional[str] = Query(default=None),
    today_only: bool = Query(default=False),
):
    streamer = _normalize_streamer_filter(streamer_unique_id)
    filters = build_follow_filters(user.id, streamer, today_only, _today_start_utc())
    total = count_rows(db, FollowEvent, filters)
    offset = (page - 1) * page_size
    rows = fetch_follow_rows(db, filters, offset=offset, limit=page_size)
    return PaginatedFollowEventsResponse(
        items=[
            FollowEventResponse(
                id=r.id,
                streamer_unique_id=r.streamer_unique_id,
                follower_unique_id=r.follower_unique_id,
                follower_nickname=r.follower_nickname,
                detected_at=r.detected_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/events/joins", response_model=PaginatedJoinEventsResponse)
def list_joins(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    streamer_unique_id: Optional[str] = Query(default=None),
    today_only: bool = Query(default=False),
):
    streamer = _normalize_streamer_filter(streamer_unique_id)
    filters = build_join_filters(user.id, streamer, today_only, _today_start_utc())
    total = count_rows(db, JoinEvent, filters)
    offset = (page - 1) * page_size
    rows = fetch_join_rows(db, filters, offset=offset, limit=page_size)
    return PaginatedJoinEventsResponse(
        items=[
            JoinEventResponse(
                id=r.id,
                streamer_unique_id=r.streamer_unique_id,
                guest_unique_id=r.guest_unique_id,
                guest_nickname=r.guest_nickname,
                detected_at=r.detected_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _export_filename(kind: str, fmt: str) -> str:
    stamp = datetime.now(_LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
    label = "follows" if kind == "follows" else "joins"
    ext = "csv" if fmt == "csv" else "txt"
    return f"events_{label}_{stamp}.{ext}"


def _attachment_headers(filename: str) -> dict[str, str]:
    fallback = filename.encode("ascii", "ignore").decode() or "export.dat"
    encoded = quote(filename)
    return {
        "Content-Disposition": f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"
    }


@router.get("/events/follows/export")
def export_follows(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    streamer_unique_id: Optional[str] = Query(default=None),
    today_only: bool = Query(default=False),
    format: Literal["txt", "csv"] = Query(default="csv", alias="format"),
):
    streamer = _normalize_streamer_filter(streamer_unique_id)
    filters = build_follow_filters(user.id, streamer, today_only, _today_start_utc())
    total = count_rows(db, FollowEvent, filters)
    if total > export_max_rows():
        raise HTTPException(
            status_code=400,
            detail=f"导出数据过多（{total} 条），请缩小筛选范围（上限 {export_max_rows()} 条）",
        )
    rows = fetch_follow_rows(db, filters, offset=0, limit=export_max_rows())
    content, media_type, _ext = export_content("follows", format, rows)
    body = ("\ufeff" + content) if format == "csv" else content
    filename = _export_filename("follows", format)
    return Response(
        content=body.encode("utf-8"),
        media_type=media_type,
        headers=_attachment_headers(filename),
    )


@router.get("/events/joins/export")
def export_joins(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    streamer_unique_id: Optional[str] = Query(default=None),
    today_only: bool = Query(default=False),
    format: Literal["txt", "csv"] = Query(default="csv", alias="format"),
):
    streamer = _normalize_streamer_filter(streamer_unique_id)
    filters = build_join_filters(user.id, streamer, today_only, _today_start_utc())
    total = count_rows(db, JoinEvent, filters)
    if total > export_max_rows():
        raise HTTPException(
            status_code=400,
            detail=f"导出数据过多（{total} 条），请缩小筛选范围（上限 {export_max_rows()} 条）",
        )
    rows = fetch_join_rows(db, filters, offset=0, limit=export_max_rows())
    content, media_type, _ext = export_content("joins", format, rows)
    body = ("\ufeff" + content) if format == "csv" else content
    filename = _export_filename("joins", format)
    return Response(
        content=body.encode("utf-8"),
        media_type=media_type,
        headers=_attachment_headers(filename),
    )
