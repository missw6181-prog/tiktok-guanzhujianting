from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.crypto import decrypt_secret, encrypt_secret, token_hint
from app.database import get_db
from app.deps import require_admin
from app.euler_client import fetch_sign_api_rate_limits, rate_limits_to_json
from app.models import MonitorTask, SignApiKey, Streamer, TelegramBot, TelegramGroup, User
from app.monitor.manager import get_monitor_manager
from app.schemas import (
    AdminBotCreate,
    AdminBotResponse,
    AdminBotUpdate,
    AdminGroupCreate,
    AdminGroupResponse,
    AdminGroupUpdate,
    AdminSignKeyCreate,
    AdminSignKeyResponse,
    AdminSignKeyUpdate,
    AdminSignKeyUsage,
    AdminStreamerCreate,
    AdminStreamerResponse,
    AdminStreamerUpdate,
    AdminUserOption,
)
from app.services import (
    assert_streamer_unique_globally,
    create_sign_api_key,
    decrypt_sign_api_key_row,
    get_owned_bot,
    normalize_unique_id,
    sign_api_key_to_dict,
)
from app.settings import get_settings
from app.telegram_client import fetch_bot_info

router = APIRouter(tags=["admin-manage"])


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _streamer_to_admin(db: Session, streamer: Streamer) -> AdminStreamerResponse:
    task_count = db.scalar(
        select(func.count()).select_from(MonitorTask).where(MonitorTask.streamer_id == streamer.id)
    ) or 0
    enabled_task_count = db.scalar(
        select(func.count())
        .select_from(MonitorTask)
        .where(MonitorTask.streamer_id == streamer.id, MonitorTask.enabled.is_(True))
    ) or 0
    return AdminStreamerResponse(
        id=streamer.id,
        user_id=streamer.user_id,
        user_email=streamer.user.email,
        unique_id=streamer.unique_id,
        display_name=streamer.display_name,
        task_count=task_count,
        enabled_task_count=enabled_task_count,
        created_at=streamer.created_at,
    )


def _sign_key_to_admin(db: Session, row: SignApiKey) -> AdminSignKeyResponse:
    data = sign_api_key_to_dict(db, row)
    usage = data.get("usage")
    return AdminSignKeyResponse(
        id=row.id,
        user_id=row.user_id,
        user_email=row.user.email,
        label=data["label"],
        sign_api_key=data["sign_api_key"],
        in_use=data["in_use"],
        usage=AdminSignKeyUsage(**usage) if usage else None,
        rate_limits=data["rate_limits"],
        rate_limit_checked_at=data["rate_limit_checked_at"],
        created_at=row.created_at,
    )


def _bot_to_admin(bot: TelegramBot) -> AdminBotResponse:
    return AdminBotResponse(
        id=bot.id,
        user_id=bot.user_id,
        user_email=bot.user.email,
        name=bot.name,
        bot_telegram_id=bot.bot_telegram_id,
        username=bot.username,
        bot_token=decrypt_secret(bot.bot_token_encrypted),
        is_active=bot.is_active,
        created_at=bot.created_at,
    )


def _group_to_admin(group: TelegramGroup) -> AdminGroupResponse:
    bot_name = group.bot.name if group.bot else None
    return AdminGroupResponse(
        id=group.id,
        user_id=group.user_id,
        user_email=group.user.email,
        bot_id=group.bot_id,
        bot_name=bot_name,
        name=group.name,
        chat_id=group.chat_id,
        is_active=group.is_active,
        created_at=group.created_at,
    )


def _validate_group_bot(db: Session, user_id: int, bot_id: Optional[int]) -> None:
    if bot_id is None:
        return
    if get_owned_bot(db, user_id, bot_id) is None:
        raise HTTPException(status_code=400, detail="机器人不存在或不属于该用户")


def _assert_group_unique(
    db: Session,
    *,
    user_id: int,
    chat_id: str,
    bot_id: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    stmt = select(TelegramGroup.id).where(
        TelegramGroup.user_id == user_id,
        TelegramGroup.chat_id == chat_id,
        TelegramGroup.bot_id == bot_id,
    )
    if exclude_id is not None:
        stmt = stmt.where(TelegramGroup.id != exclude_id)
    if db.scalar(stmt.limit(1)) is not None:
        raise HTTPException(status_code=400, detail="该用户下已存在相同 chat_id 与 Bot 的群组")


@router.get("/user-options", response_model=list[AdminUserOption])
def list_user_options(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    return [
        AdminUserOption(id=u.id, email=u.email, role=u.role, status=u.status)
        for u in users
    ]


@router.get("/streamers", response_model=list[AdminStreamerResponse])
def list_streamers(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Streamer).options(joinedload(Streamer.user)).order_by(Streamer.id)
    ).all()
    return [_streamer_to_admin(db, row) for row in rows]


@router.post("/streamers", response_model=AdminStreamerResponse, status_code=status.HTTP_201_CREATED)
def create_streamer(
    body: AdminStreamerCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_user_or_404(db, body.user_id)
    unique_id = normalize_unique_id(body.unique_id)
    try:
        assert_streamer_unique_globally(db, unique_id, user_id=body.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    streamer = Streamer(
        user_id=body.user_id,
        unique_id=unique_id,
        display_name=body.display_name,
    )
    db.add(streamer)
    db.commit()
    db.refresh(streamer)
    streamer = db.scalar(
        select(Streamer).options(joinedload(Streamer.user)).where(Streamer.id == streamer.id)
    )
    return _streamer_to_admin(db, streamer)


@router.patch("/streamers/{streamer_id}", response_model=AdminStreamerResponse)
def update_streamer(
    streamer_id: int,
    body: AdminStreamerUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    streamer = db.scalar(
        select(Streamer).options(joinedload(Streamer.user)).where(Streamer.id == streamer_id)
    )
    if streamer is None:
        raise HTTPException(status_code=404, detail="主播不存在")
    if body.display_name is not None:
        streamer.display_name = body.display_name.strip() or None
    if body.user_id is not None and body.user_id != streamer.user_id:
        _get_user_or_404(db, body.user_id)
        streamer.user_id = body.user_id
    db.commit()
    db.refresh(streamer)
    get_monitor_manager().request_sync()
    return _streamer_to_admin(db, streamer)


@router.delete("/streamers/{streamer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_streamer(
    streamer_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    streamer = db.get(Streamer, streamer_id)
    if streamer is None:
        raise HTTPException(status_code=404, detail="主播不存在")
    db.delete(streamer)
    db.commit()
    get_monitor_manager().request_sync()


@router.get("/sign-keys", response_model=list[AdminSignKeyResponse])
def list_sign_keys(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SignApiKey).options(joinedload(SignApiKey.user)).order_by(SignApiKey.id)
    ).all()
    return [_sign_key_to_admin(db, row) for row in rows]


@router.post("/sign-keys", response_model=AdminSignKeyResponse, status_code=status.HTTP_201_CREATED)
def create_sign_key(
    body: AdminSignKeyCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, body.user_id)
    try:
        row = create_sign_api_key(db, user, body.sign_api_key, label=body.label)
        db.commit()
        db.refresh(row)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = db.scalar(
        select(SignApiKey).options(joinedload(SignApiKey.user)).where(SignApiKey.id == row.id)
    )
    return _sign_key_to_admin(db, row)


@router.patch("/sign-keys/{key_id}", response_model=AdminSignKeyResponse)
def update_sign_key(
    key_id: int,
    body: AdminSignKeyUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(SignApiKey).options(joinedload(SignApiKey.user)).where(SignApiKey.id == key_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    if body.label is not None:
        row.label = body.label.strip() or None
    if body.user_id is not None and body.user_id != row.user_id:
        _get_user_or_404(db, body.user_id)
        row.user_id = body.user_id
    db.commit()
    db.refresh(row)
    return _sign_key_to_admin(db, row)


@router.post("/sign-keys/{key_id}/refresh-limits", response_model=AdminSignKeyResponse)
def refresh_sign_key_limits(
    key_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    row = db.scalar(
        select(SignApiKey).options(joinedload(SignApiKey.user)).where(SignApiKey.id == key_id)
    )
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
    row.rate_limit_snapshot = rate_limits_to_json(raw)
    row.rate_limit_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _sign_key_to_admin(db, row)


@router.delete("/sign-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sign_key(
    key_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.get(SignApiKey, key_id)
    if row is None:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    bound = db.scalar(
        select(MonitorTask.id).where(MonitorTask.sign_api_key_id == key_id).limit(1)
    )
    if bound is not None:
        raise HTTPException(status_code=400, detail="该 API Key 正被监控任务使用，无法删除")
    db.delete(row)
    db.commit()


@router.get("/bots", response_model=list[AdminBotResponse])
def list_bots(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(TelegramBot).options(joinedload(TelegramBot.user)).order_by(TelegramBot.id)
    ).all()
    return [_bot_to_admin(row) for row in rows]


@router.post("/bots", response_model=AdminBotResponse, status_code=status.HTTP_201_CREATED)
def create_bot(
    body: AdminBotCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, body.user_id)
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
        raise HTTPException(status_code=400, detail="该用户已添加此机器人")

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
    bot = db.scalar(
        select(TelegramBot).options(joinedload(TelegramBot.user)).where(TelegramBot.id == bot.id)
    )
    return _bot_to_admin(bot)


@router.patch("/bots/{bot_id}", response_model=AdminBotResponse)
def update_bot(
    bot_id: int,
    body: AdminBotUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    bot = db.scalar(
        select(TelegramBot).options(joinedload(TelegramBot.user)).where(TelegramBot.id == bot_id)
    )
    if bot is None:
        raise HTTPException(status_code=404, detail="机器人不存在")
    if body.name is not None:
        bot.name = body.name.strip() or bot.name
    if body.is_active is not None:
        bot.is_active = body.is_active
    if body.user_id is not None and body.user_id != bot.user_id:
        _get_user_or_404(db, body.user_id)
        bot.user_id = body.user_id
    if body.bot_token:
        settings = get_settings()
        try:
            info = fetch_bot_info(body.bot_token, settings.proxy_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        bot.bot_telegram_id = info.bot_telegram_id
        bot.username = info.username or None
        bot.bot_token_encrypted = encrypt_secret(body.bot_token.strip())
        bot.token_hint = token_hint(body.bot_token)
    db.commit()
    db.refresh(bot)
    get_monitor_manager().request_sync()
    return _bot_to_admin(bot)


@router.delete("/bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(
    bot_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    bot = db.get(TelegramBot, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="机器人不存在")
    db.delete(bot)
    db.commit()
    get_monitor_manager().request_sync()


@router.get("/groups", response_model=list[AdminGroupResponse])
def list_groups(
    user_id: Optional[int] = Query(default=None, ge=1),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(TelegramGroup).options(
        joinedload(TelegramGroup.user),
        joinedload(TelegramGroup.bot),
    )
    if user_id is not None:
        stmt = stmt.where(TelegramGroup.user_id == user_id)
    rows = db.scalars(stmt.order_by(TelegramGroup.id)).all()
    return [_group_to_admin(row) for row in rows]


@router.get("/users/{user_id}/groups", response_model=list[AdminGroupResponse])
def list_user_groups(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_user_or_404(db, user_id)
    rows = db.scalars(
        select(TelegramGroup)
        .options(joinedload(TelegramGroup.user), joinedload(TelegramGroup.bot))
        .where(TelegramGroup.user_id == user_id)
        .order_by(TelegramGroup.id)
    ).all()
    return [_group_to_admin(row) for row in rows]


@router.post("/groups", response_model=AdminGroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    body: AdminGroupCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_user_or_404(db, body.user_id)
    _validate_group_bot(db, body.user_id, body.bot_id)
    chat_id = body.chat_id.strip()
    _assert_group_unique(db, user_id=body.user_id, chat_id=chat_id, bot_id=body.bot_id)

    group = TelegramGroup(
        user_id=body.user_id,
        bot_id=body.bot_id,
        name=body.name.strip(),
        chat_id=chat_id,
        is_active=body.is_active,
    )
    db.add(group)
    db.commit()
    group = db.scalar(
        select(TelegramGroup)
        .options(joinedload(TelegramGroup.user), joinedload(TelegramGroup.bot))
        .where(TelegramGroup.id == group.id)
    )
    get_monitor_manager().request_sync()
    return _group_to_admin(group)


@router.patch("/groups/{group_id}", response_model=AdminGroupResponse)
def update_group(
    group_id: int,
    body: AdminGroupUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    group = db.scalar(
        select(TelegramGroup)
        .options(joinedload(TelegramGroup.user), joinedload(TelegramGroup.bot))
        .where(TelegramGroup.id == group_id)
    )
    if group is None:
        raise HTTPException(status_code=404, detail="群组不存在")

    target_user_id = body.user_id if body.user_id is not None else group.user_id
    if body.user_id is not None:
        _get_user_or_404(db, body.user_id)
        group.user_id = body.user_id

    if body.bot_id is not None:
        _validate_group_bot(db, target_user_id, body.bot_id)
        group.bot_id = body.bot_id
    elif body.user_id is not None and group.bot_id is not None:
        _validate_group_bot(db, target_user_id, group.bot_id)

    if body.name is not None:
        group.name = body.name.strip()

    target_chat_id = group.chat_id if body.chat_id is None else body.chat_id.strip()
    if body.chat_id is not None:
        group.chat_id = target_chat_id

    if body.is_active is not None:
        group.is_active = body.is_active

    _assert_group_unique(
        db,
        user_id=target_user_id,
        chat_id=target_chat_id,
        bot_id=group.bot_id,
        exclude_id=group.id,
    )

    db.commit()
    db.refresh(group)
    get_monitor_manager().request_sync()
    return _group_to_admin(group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    group = db.get(TelegramGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="群组不存在")
    db.delete(group)
    db.commit()
    get_monitor_manager().request_sync()
