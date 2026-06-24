"""监控任务运行状态常量与错误分类。"""

from __future__ import annotations

from typing import Optional, Tuple

STATUS_IDLE = "idle"
STATUS_CONNECTING = "connecting"
STATUS_LIVE = "live"
STATUS_OFFLINE = "offline"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_RETRYING = "retrying"
STATUS_ERROR = "error"

ALL_STATUSES = (
    STATUS_IDLE,
    STATUS_CONNECTING,
    STATUS_LIVE,
    STATUS_OFFLINE,
    STATUS_RATE_LIMITED,
    STATUS_RETRYING,
    STATUS_ERROR,
)


def is_rate_limit_error(exc: BaseException) -> bool:
    err = str(exc).lower()
    return (
        "rate_limit" in err
        or "rate limit" in err
        or "429" in err
        or "频率超限" in err
        or "too many requests" in err
    )


def format_rate_limit_message(exc: BaseException) -> str:
    detail = str(exc)
    return (
        "TikTok 签名服务频率超限。"
        "请为该监控任务配置独立的 API Key，或稍后再试。"
        f" 详情: {detail}"
    )


def is_offline_error(exc: BaseException) -> bool:
    if type(exc).__name__ == "UserOfflineError":
        return True
    cause = exc.__cause__
    return is_offline_error(cause) if cause else False


def classify_connection_error(exc: BaseException) -> Tuple[str, Optional[str]]:
    """将连接异常映射为 (status, last_error)。"""
    if is_offline_error(exc):
        return STATUS_OFFLINE, None
    if is_rate_limit_error(exc):
        return STATUS_RATE_LIMITED, format_rate_limit_message(exc)
    return STATUS_ERROR, str(exc)
