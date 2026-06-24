import json
from typing import Any, Optional

import httpx

EULER_SIGN_BASE = "https://tiktok.eulerstream.com"


def fetch_sign_api_rate_limits(
    api_key: str,
    *,
    proxy_url: Optional[str] = None,
) -> dict[str, Any]:
    """查询 Euler Sign Server 当前 Key 的速率/配额信息。"""
    headers = {
        "X-Api-Key": api_key.strip(),
        "User-Agent": "TikTokLiveMonitor/1.0",
        "Accept": "application/json",
    }
    client_kwargs: dict = {"timeout": 20.0}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with httpx.Client(**client_kwargs) as client:
        response = client.get(f"{EULER_SIGN_BASE}/webcast/rate_limits", headers=headers)
        try:
            body = response.json()
        except Exception as exc:
            raise ValueError("Euler 返回无效 JSON") from exc

    if response.status_code == 401:
        raise ValueError("API Key 无效")
    if not response.is_success:
        message = body.get("message") if isinstance(body, dict) else str(body)
        raise ValueError(message or f"查询配额失败 (HTTP {response.status_code})")

    return body if isinstance(body, dict) else {"data": body}


def summarize_rate_limits(body: dict[str, Any]) -> dict[str, Any]:
    """从 Euler 响应中提取常用配额字段（兼容多种结构）。"""
    raw = body.get("raw") if isinstance(body.get("raw"), dict) else body

    day = raw.get("day") if isinstance(raw.get("day"), dict) else {}
    hour = raw.get("hour") if isinstance(raw.get("hour"), dict) else {}
    minute = raw.get("minute") if isinstance(raw.get("minute"), dict) else {}

    daily_limit = _pick_int([day], "max", "limit", "daily_limit", "day_limit")
    daily_remaining = _pick_int([day], "remaining", "daily_remaining", "remaining_today")
    daily_used = None
    if daily_limit is not None and daily_remaining is not None:
        daily_used = max(daily_limit - daily_remaining, 0)

    if daily_limit is None or daily_remaining is None:
        candidates = [
            raw,
            body,
            body.get("limits"),
            body.get("rate_limits"),
            body.get("data"),
            body.get("response"),
        ]
        daily_limit = daily_limit or _pick_int(
            candidates, "daily_limit", "day_limit", "limit_per_day", "limit", "max"
        )
        daily_remaining = daily_remaining or _pick_int(
            candidates,
            "daily_remaining",
            "remaining",
            "remaining_today",
            "requests_remaining",
        )
        daily_used = _pick_int(candidates, "daily_used", "used", "used_today", "requests_used")
        if daily_limit is not None and daily_remaining is not None and daily_used is None:
            daily_used = max(daily_limit - daily_remaining, 0)
        if daily_limit is not None and daily_used is not None and daily_remaining is None:
            daily_remaining = max(daily_limit - daily_used, 0)

    return {
        "daily_limit": daily_limit,
        "daily_remaining": daily_remaining,
        "daily_used": daily_used,
        "hour_limit": _pick_int([hour], "max", "limit"),
        "hour_remaining": _pick_int([hour], "remaining"),
        "minute_limit": _pick_int([minute], "max", "limit"),
        "minute_remaining": _pick_int([minute], "remaining"),
        "day_reset_at": day.get("reset_at"),
        "raw": raw if isinstance(raw, dict) else body,
    }


def _pick_int(groups: list[Any], *names: str) -> Optional[int]:
    for group in groups:
        if not isinstance(group, dict):
            continue
        for name in names:
            value = group.get(name)
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return None


def rate_limits_to_json(body: dict[str, Any]) -> str:
    return json.dumps(summarize_rate_limits(body), ensure_ascii=False)
