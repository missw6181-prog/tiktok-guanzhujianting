import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.crypto import decrypt_secret
from app.database import SessionLocal
from app.models import FollowEvent as FollowEventModel
from app.models import JoinEvent as JoinEventModel
from app.models import MonitorTask
from app.monitor.client_cleanup import close_event_loop, dispose_tiktok_client_sync
from app.monitor.task_status import (
    STATUS_CONNECTING,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_LIVE,
    STATUS_OFFLINE,
    STATUS_RATE_LIMITED,
    STATUS_RETRYING,
    classify_connection_error,
    format_rate_limit_message,
    is_rate_limit_error,
)
from app.settings import get_settings
from join_rate_limiter import JoinPushRateLimiter
from room_cache import clear_room_id, get_room_id, save_room_id
from telegram_notifier import FollowPushCounter, notify_follow_async, notify_join_async, notify_live_started_async

logger = logging.getLogger("follow_monitor.worker")

STALE_ROOM_SECONDS = 90
_TIKTOKLIVE: Optional[Dict[str, Any]] = None
_TIKTOKLIVE_ERROR: Optional[str] = None


def get_tiktoklive_load_error() -> Optional[str]:
    return _TIKTOKLIVE_ERROR


def check_monitor_runtime() -> Optional[str]:
    """返回 None 表示可用，否则为错误说明。"""
    if sys.version_info < (3, 10):
        return (
            f"监控功能需要 Python 3.10+，当前为 {sys.version_info.major}."
            f"{sys.version_info.minor}。请用 ./start.sh 启动或重建虚拟环境。"
        )
    try:
        _tiktoklive()
    except RuntimeError as exc:
        return str(exc)
    return None


def _tiktoklive() -> Dict[str, Any]:
    """延迟导入，避免 API 启动时因 Python/TikTokLive 版本不兼容而失败。"""
    global _TIKTOKLIVE, _TIKTOKLIVE_ERROR
    if _TIKTOKLIVE is not None:
        return _TIKTOKLIVE
    if _TIKTOKLIVE_ERROR is not None:
        raise RuntimeError(_TIKTOKLIVE_ERROR)

    if sys.version_info < (3, 10):
        _TIKTOKLIVE_ERROR = (
            "TikTokLive 需要 Python 3.10+。"
            f"当前 Python {sys.version_info.major}.{sys.version_info.minor} 无法加载监听库。"
        )
        raise RuntimeError(_TIKTOKLIVE_ERROR)

    try:
        from TikTokLive import TikTokLiveClient
        from TikTokLive.client.errors import UserOfflineError
        from TikTokLive.client.web.routes.fetch_is_live import MissingRoomIdInResponse
        from TikTokLive.client.web.routes.fetch_room_id_live_html import FailedParseRoomIdError
        from TikTokLive.events import (
            ConnectEvent,
            DisconnectEvent,
            FollowEvent,
            JoinEvent,
            LiveEndEvent,
        )
    except Exception as exc:
        _TIKTOKLIVE_ERROR = f"TikTokLive 加载失败: {exc}"
        raise RuntimeError(_TIKTOKLIVE_ERROR) from exc

    _TIKTOKLIVE = {
        "TikTokLiveClient": TikTokLiveClient,
        "UserOfflineError": UserOfflineError,
        "MissingRoomIdInResponse": MissingRoomIdInResponse,
        "FailedParseRoomIdError": FailedParseRoomIdError,
        "ConnectEvent": ConnectEvent,
        "DisconnectEvent": DisconnectEvent,
        "FollowEvent": FollowEvent,
        "JoinEvent": JoinEvent,
        "LiveEndEvent": LiveEndEvent,
    }
    return _TIKTOKLIVE


@dataclass(frozen=True)
class TaskRuntime:
    task_id: int
    user_id: int
    streamer_unique_id: str
    sign_api_key: Optional[str]
    follow_bot_token: Optional[str]
    follow_chat_id: Optional[str]
    join_bot_token: Optional[str]
    join_chat_id: Optional[str]
    join_rate_limit_per_minute: int


def _extract_user_ids(event) -> Optional[Tuple[str, str]]:
    user = event.user
    if user is None:
        return None
    unique_id = getattr(user, "unique_id", None) or getattr(user, "uniqueId", None)
    if not unique_id:
        return None
    nickname = getattr(user, "nickname", None) or ""
    return str(unique_id), str(nickname)


def _is_live_check_failure(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout)):
        return True
    if _TIKTOKLIVE is not None:
        missing = _TIKTOKLIVE["MissingRoomIdInResponse"]
        if isinstance(exc, missing):
            return True
    cause = exc.__cause__
    return _is_live_check_failure(cause) if cause else False


def _is_offline_error(exc: BaseException) -> bool:
    if type(exc).__name__ == "UserOfflineError":
        return True
    if _TIKTOKLIVE is not None and isinstance(exc, _TIKTOKLIVE["UserOfflineError"]):
        return True
    cause = exc.__cause__
    return _is_offline_error(cause) if cause else False


def _is_room_fetch_failure(exc: BaseException) -> bool:
    if isinstance(exc, json.JSONDecodeError):
        return True
    if _TIKTOKLIVE is not None and isinstance(exc, _TIKTOKLIVE["FailedParseRoomIdError"]):
        return True
    cause = exc.__cause__
    if cause and _is_room_fetch_failure(cause):
        return True
    msg = str(exc).lower()
    return "sigi_state" in msg or "blocked by tiktok" in msg


async def confirm_streamer_is_live(
    client,
    streamer_id: str,
    room_id: Optional[int] = None,
) -> bool:
    """严格确认主播是否在播；无法确认时视为未开播。"""
    tl = _tiktoklive()
    MissingRoomIdInResponse = tl["MissingRoomIdInResponse"]
    uid = streamer_id.lstrip("@")

    try:
        return await client.web.fetch_is_live(unique_id=uid)
    except Exception as exc:
        if _is_offline_error(exc) or isinstance(exc, MissingRoomIdInResponse):
            return False
        logger.debug("[confirm_is_live] unique_id @%s 检查失败: %s", uid, exc)

    if room_id is not None:
        try:
            return await client.web.fetch_is_live(room_id=int(room_id))
        except Exception as exc:
            if _is_offline_error(exc) or isinstance(exc, MissingRoomIdInResponse):
                return False
            logger.debug("[confirm_is_live] room_id %s 检查失败: %s", room_id, exc)

    return False


def load_task_runtime(task_id: int) -> Optional[TaskRuntime]:
    with SessionLocal() as db:
        task = db.scalar(
            select(MonitorTask)
            .options(
                joinedload(MonitorTask.user),
                joinedload(MonitorTask.streamer),
                joinedload(MonitorTask.sign_api_key),
                joinedload(MonitorTask.follow_bot),
                joinedload(MonitorTask.follow_group),
                joinedload(MonitorTask.join_bot),
                joinedload(MonitorTask.join_group),
            )
            .where(MonitorTask.id == task_id)
        )
        if task is None or not task.enabled or task.user.status != "active":
            return None

        follow_token = (
            decrypt_secret(task.follow_bot.bot_token_encrypted)
            if task.follow_bot and task.follow_group
            else None
        )
        follow_chat = task.follow_group.chat_id if task.follow_group else None
        join_token = (
            decrypt_secret(task.join_bot.bot_token_encrypted)
            if task.join_bot and task.join_group
            else None
        )
        join_chat = task.join_group.chat_id if task.join_group else None

        sign_api_key = None
        if task.sign_api_key is not None:
            try:
                sign_api_key = decrypt_secret(task.sign_api_key.sign_api_key_encrypted)
            except ValueError:
                sign_api_key = None
        elif task.sign_api_key_encrypted:
            try:
                sign_api_key = decrypt_secret(task.sign_api_key_encrypted)
            except ValueError:
                sign_api_key = None

        return TaskRuntime(
            task_id=task.id,
            user_id=task.user_id,
            streamer_unique_id=task.streamer.unique_id,
            sign_api_key=sign_api_key,
            follow_bot_token=follow_token,
            follow_chat_id=follow_chat,
            join_bot_token=join_token,
            join_chat_id=join_chat,
            join_rate_limit_per_minute=task.join_rate_limit_per_minute,
        )


def update_task_status(task_id: int, status: str, last_error: Optional[str] = None) -> None:
    with SessionLocal() as db:
        task = db.get(MonitorTask, task_id)
        if task is None:
            return
        task.status = status
        task.last_error = last_error
        db.commit()


class TaskWorker(threading.Thread):
    def __init__(self, task_id: int, stop_event: threading.Event) -> None:
        super().__init__(name=f"monitor-task-{task_id}", daemon=True)
        self.task_id = task_id
        self.stop_event = stop_event
        self.settings = get_settings()

    def run(self) -> None:
        last_error: Optional[str] = None
        while not self.stop_event.is_set():
            runtime = load_task_runtime(self.task_id)
            if runtime is None:
                update_task_status(self.task_id, STATUS_IDLE)
                return

            if not runtime.sign_api_key:
                last_error = "请为监控任务配置独立的 API Key（每个主播一个 Key，全局不可重复）"
                update_task_status(self.task_id, STATUS_ERROR, last_error)
                update_task_status(self.task_id, STATUS_RETRYING, last_error)
                if self.stop_event.wait(self.settings.reconnect_delay_seconds):
                    return
                continue

            from app.monitor.live_check import check_streamer_is_live_lightweight

            if not check_streamer_is_live_lightweight(runtime, self.settings):
                logger.info(
                    "[task %s] @%s 未开播（轻量检测）",
                    self.task_id,
                    runtime.streamer_unique_id,
                )
                update_task_status(self.task_id, STATUS_OFFLINE)
                if self.stop_event.is_set():
                    return
                update_task_status(self.task_id, STATUS_RETRYING, None)
                if self.stop_event.wait(self.settings.reconnect_delay_seconds):
                    return
                continue

            update_task_status(self.task_id, STATUS_CONNECTING)
            try:
                self._run_session(runtime)
                last_error = None
            except RuntimeError as exc:
                if is_rate_limit_error(exc):
                    last_error = format_rate_limit_message(exc)
                    status = STATUS_RATE_LIMITED
                else:
                    last_error = str(exc)
                    status = STATUS_ERROR
                logger.error("[task %s] %s", self.task_id, last_error)
                update_task_status(self.task_id, status, last_error)
            except Exception as exc:
                status, last_error = classify_connection_error(exc)
                if status == STATUS_OFFLINE:
                    logger.info(
                        "[task %s] @%s 未开播",
                        self.task_id,
                        runtime.streamer_unique_id,
                    )
                elif status == STATUS_ERROR:
                    logger.exception("[task %s] 连接异常", self.task_id)
                else:
                    logger.warning("[task %s] %s", self.task_id, last_error)
                update_task_status(self.task_id, status, last_error)

            if self.stop_event.is_set():
                return
            update_task_status(self.task_id, STATUS_RETRYING, last_error)
            if self.stop_event.wait(self.settings.reconnect_delay_seconds):
                return

    def _run_session(self, runtime: TaskRuntime) -> None:
        import asyncio

        tl = _tiktoklive()
        TikTokLiveClient = tl["TikTokLiveClient"]
        UserOfflineError = tl["UserOfflineError"]

        proxy = httpx.Proxy(self.settings.proxy_url) if self.settings.proxy_url else None
        client = TikTokLiveClient(
            unique_id=runtime.streamer_unique_id,
            web_proxy=proxy,
            ws_proxy=proxy,
            web_kwargs={"signer_kwargs": {"sign_api_key": runtime.sign_api_key}},
        )
        if self.settings.tiktok_session_id:
            client.web.set_session(
                self.settings.tiktok_session_id,
                self.settings.tiktok_tt_target_idc,
            )

        follow_counter = FollowPushCounter()
        join_limiter = (
            JoinPushRateLimiter(runtime.join_rate_limit_per_minute)
            if runtime.join_bot_token and runtime.join_chat_id
            else None
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self._register_handlers(client, runtime, follow_counter, join_limiter, loop, tl)

        room_id = get_room_id(runtime.streamer_unique_id)

        try:
            async def preflight() -> bool:
                return await confirm_streamer_is_live(
                    client,
                    runtime.streamer_unique_id,
                    room_id,
                )

            if not loop.run_until_complete(preflight()):
                clear_room_id(runtime.streamer_unique_id)
                update_task_status(runtime.task_id, STATUS_OFFLINE)
                raise UserOfflineError(f"@{runtime.streamer_unique_id} 未开播")

            kwargs: dict = {"fetch_live_check": True}
            if room_id is not None:
                kwargs["room_id"] = room_id

            client.run(**kwargs)
        except Exception as exc:
            if _is_offline_error(exc):
                clear_room_id(runtime.streamer_unique_id)
                raise
            if _is_live_check_failure(exc):
                clear_room_id(runtime.streamer_unique_id)
                raise UserOfflineError(f"@{runtime.streamer_unique_id} 未开播") from exc
            if _is_room_fetch_failure(exc):
                clear_room_id(runtime.streamer_unique_id)
            raise
        finally:
            dispose_tiktok_client_sync(client, loop)
            close_event_loop(loop)

    def _register_handlers(
        self,
        client,
        runtime: TaskRuntime,
        follow_counter: FollowPushCounter,
        join_limiter: Optional[JoinPushRateLimiter],
        loop,
        tl: dict,
    ) -> None:
        ConnectEvent = tl["ConnectEvent"]
        FollowEvent = tl["FollowEvent"]
        JoinEvent = tl["JoinEvent"]
        LiveEndEvent = tl["LiveEndEvent"]
        DisconnectEvent = tl["DisconnectEvent"]

        streamer_id = runtime.streamer_unique_id
        activity_state = {"last_event": time.time()}
        notify_state = {"live_notified": False}

        @client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent) -> None:
            activity_state["last_event"] = time.time()
            is_live = await confirm_streamer_is_live(
                client,
                streamer_id,
                client.room_id,
            )
            if not is_live:
                clear_room_id(streamer_id)
                update_task_status(runtime.task_id, STATUS_OFFLINE)
                logger.info(
                    "[task %s] @%s 未开播，不推送开播通知",
                    runtime.task_id,
                    event.unique_id,
                )
                await client.disconnect()
                return

            if client.room_id:
                save_room_id(streamer_id, int(client.room_id))
            update_task_status(runtime.task_id, STATUS_LIVE)
            logger.info(
                "[task %s] 直播中 @%s room_id=%s",
                runtime.task_id,
                event.unique_id,
                client.room_id,
            )
            if (
                not notify_state["live_notified"]
                and runtime.follow_bot_token
                and runtime.follow_chat_id
            ):
                ok = await notify_live_started_async(
                    bot_token=runtime.follow_bot_token,
                    chat_id=runtime.follow_chat_id,
                    streamer_unique_id=streamer_id,
                    proxy_url=self.settings.proxy_url,
                )
                if ok:
                    notify_state["live_notified"] = True
                logger.info(
                    "[task %s] 开播通知 Telegram: %s",
                    runtime.task_id,
                    "推送成功" if ok else "推送失败",
                )

        @client.on(FollowEvent)
        async def on_follow(event: FollowEvent) -> None:
            activity_state["last_event"] = time.time()
            extracted = _extract_user_ids(event)
            if extracted is None:
                return
            follower_unique_id, follower_nickname = extracted

            with SessionLocal() as db:
                exists = db.scalar(
                    select(FollowEventModel.id).where(
                        FollowEventModel.user_id == runtime.user_id,
                        FollowEventModel.streamer_unique_id == streamer_id,
                        FollowEventModel.follower_unique_id == follower_unique_id,
                    )
                )
                if exists:
                    return
                db.add(
                    FollowEventModel(
                        user_id=runtime.user_id,
                        task_id=runtime.task_id,
                        streamer_unique_id=streamer_id,
                        follower_unique_id=follower_unique_id,
                        follower_nickname=follower_nickname,
                        detected_at=datetime.now(timezone.utc),
                    )
                )
                db.commit()

            if runtime.follow_bot_token and runtime.follow_chat_id:
                seq = follow_counter.next()
                await notify_follow_async(
                    bot_token=runtime.follow_bot_token,
                    chat_id=runtime.follow_chat_id,
                    seq=seq,
                    follower_nickname=follower_nickname,
                    follower_unique_id=follower_unique_id,
                    streamer_nickname=streamer_id,
                    streamer_unique_id=streamer_id,
                    proxy_url=self.settings.proxy_url,
                )

        @client.on(JoinEvent)
        async def on_join(event: JoinEvent) -> None:
            activity_state["last_event"] = time.time()
            extracted = _extract_user_ids(event)
            if extracted is None:
                return
            guest_unique_id, guest_nickname = extracted

            with SessionLocal() as db:
                exists = db.scalar(
                    select(JoinEventModel.id).where(
                        JoinEventModel.user_id == runtime.user_id,
                        JoinEventModel.streamer_unique_id == streamer_id,
                        JoinEventModel.guest_unique_id == guest_unique_id,
                    )
                )
                if exists:
                    return
                db.add(
                    JoinEventModel(
                        user_id=runtime.user_id,
                        task_id=runtime.task_id,
                        streamer_unique_id=streamer_id,
                        guest_unique_id=guest_unique_id,
                        guest_nickname=guest_nickname,
                        detected_at=datetime.now(timezone.utc),
                    )
                )
                db.commit()

            if (
                runtime.join_bot_token
                and runtime.join_chat_id
                and join_limiter is not None
                and join_limiter.allow()
            ):
                await notify_join_async(
                    bot_token=runtime.join_bot_token,
                    chat_id=runtime.join_chat_id,
                    user_unique_id=guest_unique_id,
                    nickname=guest_nickname,
                    proxy_url=self.settings.proxy_url,
                )

        @client.on(LiveEndEvent)
        async def on_live_end(_event: LiveEndEvent) -> None:
            notify_state["live_notified"] = False
            clear_room_id(streamer_id)
            update_task_status(runtime.task_id, STATUS_OFFLINE)

        @client.on(DisconnectEvent)
        async def on_disconnect(_event: DisconnectEvent) -> None:
            update_task_status(runtime.task_id, STATUS_OFFLINE)
            logger.info("[task %s] 已断开", runtime.task_id)
