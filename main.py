import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone

import httpx
from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserOfflineError
from TikTokLive.client.web.routes.fetch_is_live import MissingRoomIdInResponse
from TikTokLive.client.web.routes.fetch_room_id_live_html import FailedParseRoomIdError
from TikTokLive.events import (
    CommentEvent,
    ConnectEvent,
    DisconnectEvent,
    FollowEvent,
    JoinEvent,
    LikeEvent,
    LiveEndEvent,
    RoomUserSeqEvent,
)

from config import Config, load_config, write_env_var
from join_rate_limiter import JoinPushRateLimiter
from room_cache import clear_room_id, get_room_id, save_room_id
from storage import (
    FollowRecord,
    FollowStorage,
    JoinRecord,
    JoinStorage,
    follow_exists_for_streamer,
    join_exists_for_streamer,
)
from telegram_notifier import (
    FollowPushCounter,
    notify_follow_async,
    notify_join_async,
    notify_message_async,
)

logger = logging.getLogger("follow_monitor")


class StartupStatusNotifier:
    """每次程序启动只推送一次主播开播状态。"""

    def __init__(self) -> None:
        self._sent = False

    async def notify_live(self, config: Config, streamer_unique_id: str) -> None:
        if self._sent:
            return
        self._sent = True
        await _notify_telegram_startup_status(
            config,
            f"目标主播 @{streamer_unique_id.lstrip('@')} 已经开播，开始监听新关注。",
        )

    def notify_offline(self, config: Config) -> None:
        if self._sent:
            return
        self._sent = True
        asyncio.run(
            _notify_telegram_startup_status(
                config,
                f"目标主播 {config.target_unique_id} 当前没有开播。",
            )
        )


def _extract_user_ids(event: FollowEvent | JoinEvent) -> tuple[str, str] | None:
    user = event.user
    if user is None:
        return None

    unique_id = getattr(user, "unique_id", None) or getattr(user, "uniqueId", None)
    if not unique_id:
        return None

    nickname = getattr(user, "nickname", None) or ""
    return str(unique_id), str(nickname)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _is_live_check_failure(exc: BaseException) -> bool:
    if isinstance(exc, (MissingRoomIdInResponse, httpx.ConnectTimeout, httpx.ReadTimeout)):
        return True
    cause = exc.__cause__
    return _is_live_check_failure(cause) if cause else False


def _is_offline_error(exc: BaseException) -> bool:
    if isinstance(exc, UserOfflineError):
        return True
    cause = exc.__cause__
    return _is_offline_error(cause) if cause else False


def _is_room_fetch_failure(exc: BaseException) -> bool:
    if isinstance(exc, (FailedParseRoomIdError, json.JSONDecodeError)):
        return True
    cause = exc.__cause__
    if cause and _is_room_fetch_failure(cause):
        return True
    msg = str(exc).lower()
    return "sigi_state" in msg or "blocked by tiktok" in msg


def _schedule_telegram_follow(
    config: Config,
    follow_counter: FollowPushCounter,
    *,
    follower_nickname: str,
    follower_unique_id: str,
    streamer_nickname: str,
    streamer_unique_id: str,
) -> None:
    tg = config.telegram
    if not tg.follow_push_enabled or not tg.bot_token or not tg.follow_chat_id:
        logger.info(
            "[新关注] @%s → Telegram: 未配置关注群组，跳过推送",
            follower_unique_id,
        )
        return

    seq = follow_counter.next()

    def _on_chat_migrated(new_chat_id: str) -> None:
        write_env_var("TELEGRAM_FOLLOW_CHAT_ID", new_chat_id)
        logger.info("已自动更新 .env 中的 TELEGRAM_FOLLOW_CHAT_ID=%s", new_chat_id)

    async def _push() -> None:
        ok = await notify_follow_async(
            bot_token=tg.bot_token,
            chat_id=tg.follow_chat_id,
            seq=seq,
            follower_nickname=follower_nickname,
            follower_unique_id=follower_unique_id,
            streamer_nickname=streamer_nickname,
            streamer_unique_id=streamer_unique_id,
            proxy_url=config.proxy_url,
            on_chat_id_migrated=_on_chat_migrated,
        )
        logger.info(
            "[新关注] #%d @%s → Telegram(%s): %s",
            seq,
            follower_unique_id,
            tg.follow_chat_id,
            "推送成功" if ok else "推送失败",
        )

    asyncio.create_task(_push(), name=f"telegram-follow-{seq}-{follower_unique_id}")


def _schedule_telegram_join(
    config: Config,
    join_limiter: JoinPushRateLimiter | None,
    user_unique_id: str,
    nickname: str,
) -> None:
    tg = config.telegram
    if not tg.join_push_enabled or not tg.bot_token or not tg.join_chat_id:
        logger.info(
            "[新进直播间] @%s → Telegram: 未配置进场群组，跳过推送",
            user_unique_id,
        )
        return

    if join_limiter is not None and not join_limiter.allow():
        logger.info(
            "[新进直播间] @%s → Telegram: 跳过推送（已达每分钟 %d 条上限）",
            user_unique_id,
            tg.join_rate_limit_per_minute,
        )
        return

    def _on_chat_migrated(new_chat_id: str) -> None:
        write_env_var("TELEGRAM_JOIN_CHAT_ID", new_chat_id)
        logger.info("已自动更新 .env 中的 TELEGRAM_JOIN_CHAT_ID=%s", new_chat_id)

    async def _push() -> None:
        ok = await notify_join_async(
            bot_token=tg.bot_token,
            chat_id=tg.join_chat_id,
            user_unique_id=user_unique_id,
            nickname=nickname,
            proxy_url=config.proxy_url,
            on_chat_id_migrated=_on_chat_migrated,
        )
        logger.info(
            "[新进直播间] @%s → Telegram(%s): %s",
            user_unique_id,
            tg.join_chat_id,
            "推送成功" if ok else "推送失败",
        )

    asyncio.create_task(_push(), name=f"telegram-join-{user_unique_id}")


def _telegram_status_targets(config: Config) -> list[tuple[str, str]]:
    tg = config.telegram
    if not tg.enabled or not tg.bot_token:
        return []

    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chat_id, env_key in (
        (tg.follow_chat_id, "TELEGRAM_FOLLOW_CHAT_ID"),
        (tg.join_chat_id, "TELEGRAM_JOIN_CHAT_ID"),
    ):
        if chat_id and chat_id not in seen:
            targets.append((chat_id, env_key))
            seen.add(chat_id)
    return targets


async def _notify_telegram_startup_status(config: Config, text: str) -> None:
    tg = config.telegram
    targets = _telegram_status_targets(config)
    if not targets or not tg.bot_token:
        logger.info("[主播状态] Telegram: 未配置群组，跳过推送")
        return

    for chat_id, env_key in targets:
        def _on_chat_migrated(new_chat_id: str, key: str = env_key) -> None:
            write_env_var(key, new_chat_id)
            logger.info("已自动更新 .env 中的 %s=%s", key, new_chat_id)

        await notify_message_async(
            bot_token=tg.bot_token,
            chat_id=chat_id,
            text=text,
            proxy_url=config.proxy_url,
            env_chat_key=env_key,
            on_chat_id_migrated=_on_chat_migrated,
        )
        logger.info("[主播状态] → Telegram(%s): %s", chat_id, text)


def _log_telegram_status(config: Config) -> None:
    tg = config.telegram
    if not tg.enabled:
        logger.info("Telegram: 未启用")
        return

    if tg.follow_push_enabled:
        logger.info("Telegram 关注推送 → %s", tg.follow_chat_id)
    else:
        logger.info("Telegram 关注推送 → 未配置群组，已跳过")

    if tg.join_push_enabled:
        logger.info(
            "Telegram 进场推送 → %s（限速 %d 条/分钟）",
            tg.join_chat_id,
            tg.join_rate_limit_per_minute,
        )
    else:
        logger.info("Telegram 进场推送 → 未配置群组，已跳过")


STALE_ROOM_SECONDS = 90


def _resolve_room_id(config: Config) -> int | None:
    if config.room_id is not None:
        return config.room_id
    if config.use_cached_room_id:
        return get_room_id(config.target_unique_id)
    return None


def _room_id_source(config: Config, room_id: int | None) -> str:
    if room_id is None:
        return "fresh"
    if config.room_id is not None:
        return "env"
    return "cache"


def _create_client(
    config: Config,
    storage: FollowStorage,
    join_storage: JoinStorage,
    join_limiter: JoinPushRateLimiter | None,
    follow_counter: FollowPushCounter,
    startup_status: StartupStatusNotifier,
    *,
    room_source: str = "fresh",
) -> TikTokLiveClient:
    proxy = httpx.Proxy(config.proxy_url) if config.proxy_url else None
    client = TikTokLiveClient(
        unique_id=config.target_unique_id.lstrip("@"),
        web_proxy=proxy,
        ws_proxy=proxy,
    )
    if config.tiktok_session_id:
        client.web.set_session(config.tiktok_session_id, config.tiktok_tt_target_idc)
    _register_handlers(
        client,
        config,
        storage,
        join_storage,
        join_limiter,
        follow_counter,
        startup_status,
        room_source=room_source,
    )
    return client


def _run_once(
    client: TikTokLiveClient,
    *,
    fetch_live_check: bool,
    room_id: int | None,
) -> None:
    kwargs: dict = {"fetch_live_check": fetch_live_check}
    if room_id is not None:
        kwargs["room_id"] = room_id
    client.run(**kwargs)


def _run_client(
    config: Config,
    storage: FollowStorage,
    join_storage: JoinStorage,
    join_limiter: JoinPushRateLimiter | None,
    follow_counter: FollowPushCounter,
    startup_status: StartupStatusNotifier,
) -> None:
    room_id = _resolve_room_id(config)
    room_source = _room_id_source(config, room_id)
    client = _create_client(
        config,
        storage,
        join_storage,
        join_limiter,
        follow_counter,
        startup_status,
        room_source=room_source,
    )

    if room_id is not None:
        if room_source == "env":
            logger.info("使用 .env 指定的 room_id=%s 连接", room_id)
        else:
            logger.info("使用缓存 room_id=%s 连接（USE_CACHED_ROOM_ID=true）", room_id)
    else:
        logger.info("正在获取最新直播间 room_id（不使用缓存，避免连到已结束场次）…")

    try:
        _run_once(client, fetch_live_check=config.fetch_live_check, room_id=room_id)
        return
    except Exception as exc:
        if config.fetch_live_check and _is_live_check_failure(exc):
            logger.warning(
                "直播状态检查失败（多为 webcast.tiktok.com 网络超时），正在跳过检查直接连接…"
            )
            client = _create_client(
                config,
                storage,
                join_storage,
                join_limiter,
                follow_counter,
                startup_status,
                room_source=room_source,
            )
            _run_once(client, fetch_live_check=False, room_id=room_id)
            return

        if room_id is None and _is_room_fetch_failure(exc):
            cached = get_room_id(config.target_unique_id)
            if cached is not None:
                logger.warning(
                    "页面抓取被 TikTok 拦截，改用缓存 room_id=%s 重试…", cached
                )
                client = _create_client(
                    config,
                    storage,
                    join_storage,
                    join_limiter,
                    follow_counter,
                    startup_status,
                    room_source="cache",
                )
                _run_once(
                    client,
                    fetch_live_check=False,
                    room_id=cached,
                )
                return
            logger.error(
                "无法获取直播间 room_id（可能被 TikTok 限制）。可尝试：\n"
                "  1. 在 .env 设置代理，例如 HTTPS_PROXY=http://127.0.0.1:7890\n"
                "  2. 浏览器打开直播页，从地址栏或开发者工具找到 room_id，写入 .env：ROOM_ID=数字\n"
                "  3. 稍后重试，或更换网络/VPN"
            )

        raise


async def _stale_room_watchdog(
    client: TikTokLiveClient,
    config: Config,
    activity_state: dict[str, float],
    room_source: str,
) -> None:
    await asyncio.sleep(STALE_ROOM_SECONDS)
    if time.time() - activity_state["last_event"] < STALE_ROOM_SECONDS - 5:
        return

    logger.warning(
        "连接后 %d 秒内未收到任何直播间数据，"
        "很可能是 room_id 已过期（主播重新开播后会变更）。"
        "正在清除缓存并断开重连…",
        STALE_ROOM_SECONDS,
    )
    if room_source == "cache":
        clear_room_id(config.target_unique_id)
    elif room_source == "env":
        logger.warning("若仍无数据，请更新或删除 .env 中的 ROOM_ID")
    await client.disconnect()


def _register_handlers(
    client: TikTokLiveClient,
    config: Config,
    storage: FollowStorage,
    join_storage: JoinStorage,
    join_limiter: JoinPushRateLimiter | None,
    follow_counter: FollowPushCounter,
    startup_status: StartupStatusNotifier,
    *,
    room_source: str = "fresh",
) -> None:
    streamer_id = config.target_unique_id.lstrip("@")
    streamer_state = {"nickname": streamer_id}
    db_path = config.db_path
    activity_state = {"last_event": time.time()}
    viewer_log_state = {"last_log": 0.0}
    watchdog_state = {"started": False}

    def _touch_activity() -> None:
        activity_state["last_event"] = time.time()

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent) -> None:
        _touch_activity()
        if client.room_id:
            save_room_id(streamer_id, int(client.room_id))
        logger.info(
            "已连接直播间 @%s (room_id=%s, follows=%d, joins=%d)",
            event.unique_id,
            client.room_id,
            storage.count(),
            join_storage.count(),
        )
        await startup_status.notify_live(config, event.unique_id)
        logger.info("终端将显示: 弹幕 / 进场 / 点赞 / 新关注 / 新进直播间及推送结果")
        if not watchdog_state["started"]:
            watchdog_state["started"] = True
            asyncio.create_task(
                _stale_room_watchdog(client, config, activity_state, room_source),
                name="stale-room-watchdog",
            )

    @client.on(RoomUserSeqEvent)
    async def on_room_users(event: RoomUserSeqEvent) -> None:
        _touch_activity()
        now = time.time()
        if now - viewer_log_state["last_log"] < 60:
            return
        viewer_log_state["last_log"] = now
        total = getattr(event, "total_user", None) or getattr(event, "m_total", None)
        logger.info("[状态] 直播间在线约 %s 人", total if total else "?")

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent) -> None:
        _touch_activity()
        user = event.user
        name = getattr(user, "nickname", None) if user else "未知"
        logger.info("[互动] 弹幕: %s → %s", name, event.comment)

    @client.on(LikeEvent)
    async def on_like(event: LikeEvent) -> None:
        _touch_activity()
        user = event.user
        name = getattr(user, "nickname", None) if user else "未知"
        logger.info("[互动] 点赞: %s", name)

    @client.on(JoinEvent)
    async def on_join(event: JoinEvent) -> None:
        _touch_activity()
        extracted = _extract_user_ids(event)
        if extracted is None:
            logger.warning("[新进直播间] 收到事件但无法解析用户信息")
            return

        user_unique_id, nickname = extracted
        logger.info(
            "[互动] 进场: @%s (%s)",
            user_unique_id,
            nickname or user_unique_id,
        )

        if join_exists_for_streamer(db_path, user_unique_id, streamer_id):
            logger.info(
                "[新进直播间] @%s 数据库比对: 已存在（joins 表）→ 跳过入库与推送",
                user_unique_id,
            )
            return

        record = JoinRecord(
            user_unique_id=user_unique_id,
            nickname=nickname,
            streamer_unique_id=streamer_id,
            detected_at=datetime.now(timezone.utc),
        )
        if not join_storage.save(record):
            logger.warning(
                "[新进直播间] @%s 数据库比对: 写入失败（并发冲突？）",
                user_unique_id,
            )
            return

        logger.info("[新进直播间] @%s 数据库比对: 新用户 → 已写入 joins 表", user_unique_id)
        _schedule_telegram_join(config, join_limiter, user_unique_id, nickname)

    @client.on(FollowEvent)
    async def on_follow(event: FollowEvent) -> None:
        _touch_activity()
        extracted = _extract_user_ids(event)
        if extracted is None:
            logger.warning("[新关注] 收到事件但无法解析用户信息")
            return

        follower_unique_id, follower_nickname = extracted
        logger.info(
            "[互动] 新关注: @%s (%s) → 主播 @%s",
            follower_unique_id,
            follower_nickname or follower_unique_id,
            streamer_id,
        )

        if follow_exists_for_streamer(db_path, follower_unique_id, streamer_id):
            logger.info(
                "[新关注] @%s 数据库比对: 已存在（follows 表）→ 跳过入库与推送",
                follower_unique_id,
            )
            return

        record = FollowRecord(
            follower_unique_id=follower_unique_id,
            follower_nickname=follower_nickname,
            streamer_unique_id=streamer_id,
            detected_at=datetime.now(timezone.utc),
        )
        if not storage.save(record):
            logger.warning(
                "[新关注] @%s 数据库比对: 写入失败（并发冲突？）",
                follower_unique_id,
            )
            return

        logger.info("[新关注] @%s 数据库比对: 新用户 → 已写入 follows 表", follower_unique_id)
        _schedule_telegram_follow(
            config,
            follow_counter,
            follower_nickname=follower_nickname,
            follower_unique_id=follower_unique_id,
            streamer_nickname=streamer_state["nickname"],
            streamer_unique_id=streamer_id,
        )

    @client.on(LiveEndEvent)
    async def on_live_end(_event: LiveEndEvent) -> None:
        logger.info("直播已结束")

    @client.on(DisconnectEvent)
    async def on_disconnect(_event: DisconnectEvent) -> None:
        logger.info("已断开连接")


def main() -> None:
    try:
        config = load_config()
    except ValueError as exc:
        print(f"\n配置错误: {exc}\n", file=sys.stderr)
        sys.exit(1)

    _setup_logging(config.log_level)
    storage = FollowStorage(config.db_path)
    join_storage = JoinStorage(config.db_path)
    join_limiter: JoinPushRateLimiter | None = None
    if config.telegram.join_push_enabled:
        join_limiter = JoinPushRateLimiter(config.telegram.join_rate_limit_per_minute)
    follow_counter = FollowPushCounter()
    startup_status = StartupStatusNotifier()

    logger.info(
        "用户去重: 新关注查 follows 表，新进直播间查 joins 表，各自独立去重"
    )

    if config.proxy_url:
        logger.info("使用代理: %s", config.proxy_url)

    _log_telegram_status(config)

    logger.info("开始监听 %s", config.target_unique_id)

    try:
        while True:
            try:
                _run_client(
                    config,
                    storage,
                    join_storage,
                    join_limiter,
                    follow_counter,
                    startup_status,
                )
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                if _is_offline_error(exc):
                    logger.info("目标主播 %s 当前没有开播", config.target_unique_id)
                    startup_status.notify_offline(config)
                else:
                    logger.exception("连接异常")

            logger.info("%d 秒后再检查…", config.reconnect_delay_seconds)
            time.sleep(config.reconnect_delay_seconds)
    except KeyboardInterrupt:
        logger.info("已退出")


if __name__ == "__main__":
    main()
