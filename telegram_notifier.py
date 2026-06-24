import asyncio
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger("follow_monitor.telegram")

_MAX_RETRIES = 3
_RETRY_DELAYS = (1.0, 2.0, 4.0)


class FollowPushCounter:
    """每次程序启动从 1 开始递增的关注推送编号。"""

    def __init__(self) -> None:
        self._count = 0

    def next(self) -> int:
        self._count += 1
        return self._count


def build_tiktok_profile_url(unique_id: str) -> str:
    return f"https://www.tiktok.com/@{unique_id.lstrip('@')}"


def build_follow_message(
    *,
    seq: int,
    follower_nickname: str,
    follower_unique_id: str,
    streamer_nickname: str,
    streamer_unique_id: str,
) -> str:
    follower_name = follower_nickname or follower_unique_id
    streamer_name = streamer_nickname or streamer_unique_id
    follower_user = follower_unique_id.lstrip("@")
    return (
        f"{seq}、有新用户{follower_name}({follower_user})"
        f"关注了主播{streamer_name}({streamer_unique_id.lstrip('@')})\n"
        f"客户链接\n"
        f"{build_tiktok_profile_url(follower_user)}"
    )


def build_live_started_message(streamer_unique_id: str) -> str:
    uid = streamer_unique_id.lstrip("@")
    return f"目标主播 @{uid} 已经开播，开始监听新关注。"


def build_join_message(user_unique_id: str, nickname: str) -> str:
    user = user_unique_id.lstrip("@")
    display_name = nickname or user
    return (
        f"新进直播间: @{user} ({display_name})\n"
        f"{build_tiktok_profile_url(user)}"
    )


def _parse_telegram_error(response: httpx.Response, env_chat_key: str) -> str:
    try:
        body = response.json()
        desc = body.get("description", "")
        params = body.get("parameters") or {}
        migrate_id = params.get("migrate_to_chat_id")
        if migrate_id is not None:
            return f"{desc} → 请把 .env 中 {env_chat_key} 改为 {migrate_id}"
        if desc:
            return desc
    except Exception:
        pass
    return response.text or str(response.status_code)


async def send_telegram_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    proxy_url: Optional[str] = None,
    env_chat_key: str = "TELEGRAM_CHAT_ID",
) -> Tuple[bool, Optional[str]]:
    """返回 (是否成功, 若群组升级则返回新的 chat_id)"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}

    client_kwargs: dict = {"timeout": 15.0}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    migrated_chat_id: Optional[str] = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(url, json=payload)
                body = response.json() if response.content else {}

                if response.is_success and body.get("ok"):
                    return True, migrated_chat_id

                migrate_id = (body.get("parameters") or {}).get("migrate_to_chat_id")
                if migrate_id is not None:
                    migrated_chat_id = str(migrate_id)
                    logger.warning(
                        "群组已升级为超级群，自动改用新 chat_id=%s 重试", migrated_chat_id
                    )
                    payload["chat_id"] = migrated_chat_id
                    continue

                detail = _parse_telegram_error(response, env_chat_key)
                logger.error("Telegram API 错误: %s", detail)
                return False, migrated_chat_id

        except Exception as exc:
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.warning("Telegram 推送失败 (%s)，%s 秒后重试…", exc, delay)
                await asyncio.sleep(delay)
            else:
                logger.error("Telegram 推送失败，已放弃: %s", exc)

    return False, migrated_chat_id


async def notify_message_async(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    proxy_url: Optional[str] = None,
    env_chat_key: str = "TELEGRAM_CHAT_ID",
    on_chat_id_migrated=None,
) -> None:
    try:
        ok, new_chat_id = await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=text,
            proxy_url=proxy_url,
            env_chat_key=env_chat_key,
        )
        if ok and new_chat_id and on_chat_id_migrated:
            on_chat_id_migrated(new_chat_id)
    except Exception:
        logger.exception("Telegram 推送异常")


async def notify_live_started_async(
    *,
    bot_token: str,
    chat_id: str,
    streamer_unique_id: str,
    proxy_url: Optional[str] = None,
    on_chat_id_migrated=None,
) -> bool:
    text = build_live_started_message(streamer_unique_id)
    try:
        ok, new_chat_id = await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=text,
            proxy_url=proxy_url,
            env_chat_key="TELEGRAM_FOLLOW_CHAT_ID",
        )
        if ok and new_chat_id and on_chat_id_migrated:
            on_chat_id_migrated(new_chat_id)
        return ok
    except Exception:
        logger.exception("Telegram 开播通知推送异常")
        return False


async def notify_follow_async(
    *,
    bot_token: str,
    chat_id: str,
    seq: int,
    follower_nickname: str,
    follower_unique_id: str,
    streamer_nickname: str,
    streamer_unique_id: str,
    proxy_url: Optional[str] = None,
    on_chat_id_migrated=None,
) -> bool:
    text = build_follow_message(
        seq=seq,
        follower_nickname=follower_nickname,
        follower_unique_id=follower_unique_id,
        streamer_nickname=streamer_nickname,
        streamer_unique_id=streamer_unique_id,
    )
    try:
        ok, new_chat_id = await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=text,
            proxy_url=proxy_url,
            env_chat_key="TELEGRAM_FOLLOW_CHAT_ID",
        )
        if ok and new_chat_id and on_chat_id_migrated:
            on_chat_id_migrated(new_chat_id)
        return ok
    except Exception:
        logger.exception("Telegram 推送异常")
        return False


async def notify_join_async(
    *,
    bot_token: str,
    chat_id: str,
    user_unique_id: str,
    nickname: str,
    proxy_url: Optional[str] = None,
    on_chat_id_migrated=None,
) -> bool:
    text = build_join_message(user_unique_id, nickname)
    try:
        ok, new_chat_id = await send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=text,
            proxy_url=proxy_url,
            env_chat_key="TELEGRAM_JOIN_CHAT_ID",
        )
        if ok and new_chat_id and on_chat_id_migrated:
            on_chat_id_migrated(new_chat_id)
        return ok
    except Exception:
        logger.exception("Telegram 推送异常")
        return False
