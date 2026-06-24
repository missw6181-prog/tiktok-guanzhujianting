"""TikTokLive 客户端资源释放（防止文件句柄泄漏）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger("follow_monitor.worker")


async def dispose_tiktok_client(client: Any) -> None:
    """断开 WebSocket 并关闭 httpx 客户端。"""
    if client is None:
        return
    try:
        if getattr(client, "_ws", None) is not None and client._ws.connected:
            await client.disconnect()
    except Exception as exc:
        logger.debug("disconnect 时忽略: %s", exc)
    try:
        await client.close()
    except Exception as exc:
        logger.debug("close 时忽略: %s", exc)


def dispose_tiktok_client_sync(client: Any, loop: Optional[asyncio.AbstractEventLoop]) -> None:
    """在同步上下文中释放 TikTokLive 客户端。"""
    if client is None:
        return
    if loop is None or loop.is_closed():
        return
    try:
        loop.run_until_complete(dispose_tiktok_client(client))
    except Exception as exc:
        logger.debug("同步释放客户端时忽略: %s", exc)


def close_event_loop(loop: Optional[asyncio.AbstractEventLoop]) -> None:
    if loop is not None and not loop.is_closed():
        loop.close()
