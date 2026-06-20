import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

DisplayMode = Literal["full", "follow_only"]

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

INVALID_TARGETS = {"", "@your_streamer", "your_streamer"}


def _normalize_unique_id(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("TARGET_UNIQUE_ID 不能为空")
    return value if value.startswith("@") else f"@{value}"


def _is_valid_target(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    if not normalized.startswith("@"):
        normalized = f"@{normalized}"
    return normalized.lower() not in INVALID_TARGETS


def ensure_env_file() -> None:
    if ENV_PATH.exists():
        return
    if ENV_EXAMPLE_PATH.exists():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        ENV_PATH.write_text("TARGET_UNIQUE_ID=\n", encoding="utf-8")


def write_env_var(key: str, value: str) -> None:
    _write_env_var(key, value)


def _write_env_var(key: str, value: str) -> None:
    ensure_env_file()
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def _prompt_target_unique_id() -> str:
    if not sys.stdin.isatty():
        raise ValueError(
            "未配置 TARGET_UNIQUE_ID，请先编辑 .env 填写目标主播 ID，或在终端交互运行"
        )

    print()
    print("=" * 50)
    print("  尚未配置目标主播 TikTok ID")
    print("=" * 50)
    print("  填写主播主页里的用户名即可，例如：")
    print("  https://www.tiktok.com/@somecreator  →  somecreator")
    print()

    while True:
        raw = input("请输入目标主播 unique_id: ").strip()
        if _is_valid_target(raw):
            return _normalize_unique_id(raw)
        print("输入无效，请重新输入（不能为空或占位符）")


def resolve_target_unique_id() -> str:
    load_dotenv(ENV_PATH)
    raw_target = os.getenv("TARGET_UNIQUE_ID", "").strip()

    if _is_valid_target(raw_target):
        return _normalize_unique_id(raw_target)

    target = _prompt_target_unique_id()
    _write_env_var("TARGET_UNIQUE_ID", target)
    os.environ["TARGET_UNIQUE_ID"] = target
    print(f"已保存到 {ENV_PATH}: TARGET_UNIQUE_ID={target}")
    print()
    return target


def _parse_bool(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_display_mode(value: str) -> DisplayMode | None:
    normalized = value.strip().lower()
    if normalized in {"full", "1", "全量"}:
        return "full"
    if normalized in {"follow_only", "2", "follow", "关注"}:
        return "follow_only"
    return None


def _load_display_mode() -> DisplayMode:
    raw = os.getenv("DISPLAY_MODE", "follow_only")
    mode = _parse_display_mode(raw)
    if mode:
        return mode
    raise ValueError(
        f"DISPLAY_MODE 配置无效: {raw!r}，请使用 full 或 follow_only"
    )


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    bot_token: str | None
    follow_chat_id: str | None
    join_chat_id: str | None
    join_rate_limit_per_minute: int

    @property
    def follow_push_enabled(self) -> bool:
        return self.enabled and bool(self.bot_token and self.follow_chat_id)

    @property
    def join_push_enabled(self) -> bool:
        return self.enabled and bool(self.bot_token and self.join_chat_id)


def _optional_chat_id(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return None


@dataclass(frozen=True)
class Config:
    target_unique_id: str
    db_path: Path
    reconnect_delay_seconds: int
    log_level: str
    display_mode: DisplayMode
    fetch_live_check: bool
    room_id: int | None
    use_cached_room_id: bool
    proxy_url: str | None
    tiktok_session_id: str | None
    tiktok_tt_target_idc: str | None
    telegram: TelegramConfig


def _load_telegram_config() -> TelegramConfig:
    enabled = _parse_bool(os.getenv("TELEGRAM_ENABLED", "false"))
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
    follow_chat_id = _optional_chat_id("TELEGRAM_FOLLOW_CHAT_ID", "TELEGRAM_CHAT_ID")
    join_chat_id = _optional_chat_id("TELEGRAM_JOIN_CHAT_ID")
    join_rate_limit = int(os.getenv("TELEGRAM_JOIN_RATE_LIMIT_PER_MINUTE", "20"))

    if enabled and (follow_chat_id or join_chat_id) and not bot_token:
        raise ValueError(
            "TELEGRAM_ENABLED=true 且配置了群组 ID 时，必须填写 TELEGRAM_BOT_TOKEN"
        )

    return TelegramConfig(
        enabled=enabled,
        bot_token=bot_token,
        follow_chat_id=follow_chat_id,
        join_chat_id=join_chat_id,
        join_rate_limit_per_minute=join_rate_limit,
    )


def load_config() -> Config:
    ensure_env_file()
    load_dotenv(ENV_PATH)

    target_unique_id = resolve_target_unique_id()
    db_path = Path(os.getenv("DB_PATH", "data/follows.db"))
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    reconnect = int(os.getenv("RECONNECT_DELAY_SECONDS", "30"))
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    display_mode = _load_display_mode()
    # 默认跳过 check_alive：该接口常因网络/地区原因超时，与是否在线无关
    fetch_live_check = _parse_bool(os.getenv("FETCH_LIVE_CHECK", "false"))

    room_id_raw = os.getenv("ROOM_ID", "").strip()
    room_id = int(room_id_raw) if room_id_raw.isdigit() else None
    # 默认每次连接都重新抓取 room_id；旧场次 room_id 会导致「已连接但无任何事件」
    use_cached_room_id = _parse_bool(os.getenv("USE_CACHED_ROOM_ID", "false"))

    proxy_url = (
        os.getenv("HTTPS_PROXY", "").strip()
        or os.getenv("HTTP_PROXY", "").strip()
        or None
    )
    tiktok_session_id = os.getenv("TIKTOK_SESSION_ID", "").strip() or None
    tiktok_tt_target_idc = os.getenv("TIKTOK_TT_TARGET_IDC", "").strip() or None

    return Config(
        target_unique_id=target_unique_id,
        db_path=db_path,
        reconnect_delay_seconds=reconnect,
        log_level=log_level,
        display_mode=display_mode,
        fetch_live_check=fetch_live_check,
        room_id=room_id,
        use_cached_room_id=use_cached_room_id,
        proxy_url=proxy_url,
        tiktok_session_id=tiktok_session_id,
        tiktok_tt_target_idc=tiktok_tt_target_idc,
        telegram=_load_telegram_config(),
    )
