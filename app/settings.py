import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

from app.paths import get_project_root

PROJECT_ROOT = get_project_root()
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def _build_database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "").strip()
    mysql_host = os.getenv("MYSQL_HOST", "").strip()
    if not mysql_host and explicit:
        return explicit

    if mysql_host:
        user = os.getenv("MYSQL_USER", "root").strip() or "root"
        password = os.getenv("MYSQL_PASSWORD", "")
        port = os.getenv("MYSQL_PORT", "3306").strip() or "3306"
        database = os.getenv("MYSQL_DATABASE", "follow_monitor").strip() or "follow_monitor"
        auth = quote_plus(user)
        if password:
            auth = f"{auth}:{quote_plus(password)}"
        return f"mysql+pymysql://{auth}@{mysql_host}:{port}/{database}"

    if explicit:
        return explicit

    db_path = PROJECT_ROOT / "data" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


class Settings:
    def __init__(self) -> None:
        self.database_url = _build_database_url()
        self.jwt_secret = os.getenv("JWT_SECRET", "change-me-in-production")
        self.jwt_expire_hours = int(os.getenv("JWT_EXPIRE_HOURS", "72"))
        self.token_encrypt_key = os.getenv("TOKEN_ENCRYPT_KEY", "").strip()

        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.reconnect_delay_seconds = int(os.getenv("RECONNECT_DELAY_SECONDS", "30"))
        self.fetch_live_check = os.getenv("FETCH_LIVE_CHECK", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.proxy_url = (
            os.getenv("HTTPS_PROXY", "").strip()
            or os.getenv("HTTP_PROXY", "").strip()
            or None
        )
        self.tiktok_session_id = os.getenv("TIKTOK_SESSION_ID", "").strip() or None
        self.tiktok_tt_target_idc = (
            os.getenv("TIKTOK_TT_TARGET_IDC", "").strip() or None
        )
        self.sign_api_key = os.getenv("SIGN_API_KEY", "").strip() or None
        self.default_max_monitors = int(os.getenv("DEFAULT_MAX_MONITORS", "10"))
        self.default_max_bots = int(os.getenv("DEFAULT_MAX_BOTS", "10"))
        self.default_max_groups = int(os.getenv("DEFAULT_MAX_GROUPS", "10"))
        self.default_join_rate_limit = int(
            os.getenv("TELEGRAM_JOIN_RATE_LIMIT_PER_MINUTE", "20")
        )
        self.host = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"
        self.port = int(os.getenv("PORT", "8000"))
        self.serve_static = os.getenv("SERVE_STATIC", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.cors_origins = [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
            ).split(",")
            if o.strip()
        ]
        # all = API + 监控同进程；api = 仅 Web；worker = 仅监控 Worker
        mode = os.getenv("FOLLOW_MONITOR_MODE", "all").strip().lower()
        if mode not in {"all", "api", "worker"}:
            mode = "all"
        self.monitor_mode = mode

    @property
    def runs_api(self) -> bool:
        return self.monitor_mode in {"all", "api"}

    @property
    def runs_monitor_workers(self) -> bool:
        return self.monitor_mode in {"all", "worker"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
