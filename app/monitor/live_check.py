"""轻量开播检测：不进入完整 WebSocket 会话。"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from app.monitor.client_cleanup import close_event_loop, dispose_tiktok_client
from app.monitor.worker import TaskRuntime, _tiktoklive, confirm_streamer_is_live
from app.settings import Settings
from room_cache import get_room_id

logger = logging.getLogger("follow_monitor.worker")


def _build_client(runtime: TaskRuntime, settings: Settings):
    tl = _tiktoklive()
    TikTokLiveClient = tl["TikTokLiveClient"]
    proxy = httpx.Proxy(settings.proxy_url) if settings.proxy_url else None
    client = TikTokLiveClient(
        unique_id=runtime.streamer_unique_id,
        web_proxy=proxy,
        ws_proxy=proxy,
        web_kwargs={"signer_kwargs": {"sign_api_key": runtime.sign_api_key}},
    )
    if settings.tiktok_session_id:
        client.web.set_session(
            settings.tiktok_session_id,
            settings.tiktok_tt_target_idc,
        )
    return client


async def _check_live_async(
    runtime: TaskRuntime,
    settings: Settings,
    room_id: Optional[int],
) -> bool:
    client = _build_client(runtime, settings)
    try:
        return await confirm_streamer_is_live(
            client,
            runtime.streamer_unique_id,
            room_id,
        )
    finally:
        await dispose_tiktok_client(client)


def check_streamer_is_live_lightweight(runtime: TaskRuntime, settings: Settings) -> bool:
    """同步轻量检测；创建并立即释放 httpx 资源。"""
    room_id = get_room_id(runtime.streamer_unique_id)
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            _check_live_async(runtime, settings, room_id)
        )
    except Exception as exc:
        logger.debug(
            "[task %s] 轻量开播检测失败 @%s: %s",
            runtime.task_id,
            runtime.streamer_unique_id,
            exc,
        )
        return False
    finally:
        close_event_loop(loop)
