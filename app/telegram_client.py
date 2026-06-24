from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx


@dataclass(frozen=True)
class TelegramBotInfo:
    bot_telegram_id: int
    username: str
    display_name: str


@dataclass(frozen=True)
class TelegramChatInfo:
    chat_id: str
    name: str
    chat_type: str


def _telegram_request(
    bot_token: str,
    method: str,
    *,
    proxy_url: Optional[str] = None,
    params: Optional[dict] = None,
) -> dict:
    token = bot_token.strip()
    url = f"https://api.telegram.org/bot{token}/{method}"
    client_kwargs: dict = {"timeout": 20.0}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with httpx.Client(**client_kwargs) as client:
        response = client.get(url, params=params or {})
        try:
            body = response.json()
        except Exception as exc:
            raise ValueError("Telegram 返回无效响应") from exc

    if not body.get("ok"):
        desc = body.get("description") or "Telegram 请求失败"
        raise ValueError(desc)
    return body


def fetch_bot_info(bot_token: str, proxy_url: Optional[str] = None) -> TelegramBotInfo:
    """调用 Telegram getMe 验证 Token 并获取机器人信息。"""
    body = _telegram_request(bot_token, "getMe", proxy_url=proxy_url)
    result = body.get("result") or {}
    bot_id = result.get("id")
    if not bot_id:
        raise ValueError("无法解析机器人 ID")

    username = (result.get("username") or "").strip()
    first_name = (result.get("first_name") or "").strip()
    if first_name:
        display_name = first_name
    elif username:
        display_name = f"@{username}"
    else:
        display_name = str(bot_id)

    return TelegramBotInfo(
        bot_telegram_id=int(bot_id),
        username=username,
        display_name=display_name,
    )


def _chat_from_update(update: dict) -> Optional[dict]:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        payload = update.get(key)
        if payload and payload.get("chat"):
            return payload["chat"]
    member = update.get("my_chat_member") or update.get("chat_member")
    if member and member.get("chat"):
        return member["chat"]
    return None


def _chat_display_name(chat: dict) -> str:
    title = (chat.get("title") or "").strip()
    if title:
        return title
    username = (chat.get("username") or "").strip()
    if username:
        return f"@{username}"
    first_name = (chat.get("first_name") or "").strip()
    if first_name:
        return first_name
    return str(chat.get("id", ""))


def fetch_bot_chats(bot_token: str, proxy_url: Optional[str] = None) -> List[TelegramChatInfo]:
    """
    通过 getUpdates 发现 Bot 接触过的群/超级群/频道。
    注意：Telegram 不提供「Bot 所在全部群组」列表，只能发现有过更新的会话。
    """
    webhook = _telegram_request(bot_token, "getWebhookInfo", proxy_url=proxy_url)
    if (webhook.get("result") or {}).get("url"):
        raise ValueError(
            "该 Bot 已启用 Webhook，无法拉取更新记录。"
            "请先在 BotFather 或其他服务关闭 Webhook 后再试。"
        )

    discovered: Dict[str, TelegramChatInfo] = {}
    offset = None

    for _ in range(5):
        params = {"limit": 100, "timeout": 0}
        if offset is not None:
            params["offset"] = offset
        body = _telegram_request(bot_token, "getUpdates", proxy_url=proxy_url, params=params)
        updates = body.get("result") or []
        if not updates:
            break

        for update in updates:
            offset = int(update["update_id"]) + 1
            chat = _chat_from_update(update)
            if not chat:
                continue
            chat_type = chat.get("type") or ""
            if chat_type not in {"group", "supergroup", "channel"}:
                continue
            chat_id = str(chat["id"])
            discovered[chat_id] = TelegramChatInfo(
                chat_id=chat_id,
                name=_chat_display_name(chat),
                chat_type=chat_type,
            )

    return sorted(discovered.values(), key=lambda item: item.name.lower())


def fetch_chat_title(
    bot_token: str,
    chat_id: str,
    proxy_url: Optional[str] = None,
) -> str:
    """通过 getChat 获取群/频道当前名称。"""
    body = _telegram_request(
        bot_token,
        "getChat",
        proxy_url=proxy_url,
        params={"chat_id": chat_id},
    )
    result = body.get("result") or {}
    name = _chat_display_name(result)
    if not name or name == str(result.get("id", "")):
        raise ValueError("无法解析群组名称")
    return name
