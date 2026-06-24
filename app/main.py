import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin_routes import router as admin_router
from app.api.user_routes import router as user_router
from app.database import init_db
from app.monitor.manager import get_monitor_manager
from app.monitor.worker import check_monitor_runtime
from app.settings import PROJECT_ROOT, get_settings

logger = logging.getLogger("follow_monitor")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    _setup_logging(settings.log_level)
    init_db()
    runtime_error = check_monitor_runtime()
    if runtime_error:
        logger.error("监控功能不可用: %s", runtime_error)
    manager = None
    if settings.runs_monitor_workers:
        if runtime_error:
            logger.error("监控 Worker 未启动: %s", runtime_error)
        else:
            manager = get_monitor_manager()
            manager.start()
            logger.info("监控 Worker 已启动 (mode=%s)", settings.monitor_mode)
    logger.info("Web 服务已启动 (mode=%s)", settings.monitor_mode)
    yield
    if manager is not None:
        manager.stop()


app = FastAPI(title="TikTok 关注监听", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(admin_router)


@app.get("/api/health")
def health():
    settings = get_settings()
    runtime_error = check_monitor_runtime()
    payload = {"status": "ok", "mode": settings.monitor_mode}
    if runtime_error:
        payload["monitor"] = "unavailable"
        payload["monitor_error"] = runtime_error
    elif settings.monitor_mode == "api":
        payload["monitor"] = "external"
        payload["monitor_note"] = "监控运行在独立 Worker 进程"
    else:
        payload["monitor"] = "ok"
    return payload


def _mount_static_assets() -> None:
    settings = get_settings()
    admin_dist = PROJECT_ROOT / "frontend-admin" / "dist"
    user_dist = PROJECT_ROOT / "frontend-user" / "dist"
    should_serve = settings.serve_static or getattr(sys, "frozen", False)
    if not should_serve:
        return

    if admin_dist.is_dir():
        app.mount(
            "/admin",
            StaticFiles(directory=str(admin_dist), html=True),
            name="admin-static",
        )
        logger.info("已挂载管理端静态资源: %s", admin_dist)

    if user_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(user_dist), html=True),
            name="user-static",
        )
        logger.info("已挂载用户端静态资源: %s", user_dist)


_mount_static_assets()
