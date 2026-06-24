#!/usr/bin/env python3
"""生产环境入口：启动 Web 服务、监控 Worker 或初始化数据库。"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time


def _ensure_import_path() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def _set_monitor_mode(mode: str) -> None:
    os.environ["FOLLOW_MONITOR_MODE"] = mode
    from app.settings import get_settings

    get_settings.cache_clear()


def _setup_logging() -> None:
    from app.settings import get_settings

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def cmd_run(args: argparse.Namespace) -> None:
    import uvicorn

    from app.main import app

    if args.worker_only:
        cmd_worker(args)
        return

    mode = "api" if args.api_only else "all"
    _set_monitor_mode(mode)
    _setup_logging()

    host = args.host or os.getenv("HOST", "0.0.0.0")
    port = args.port or int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())


def cmd_worker(_args: argparse.Namespace) -> None:
    from app.database import init_db
    from app.monitor.manager import get_monitor_manager
    from app.monitor.worker import check_monitor_runtime

    _set_monitor_mode("worker")
    _setup_logging()
    logger = logging.getLogger("follow_monitor")

    init_db()
    runtime_error = check_monitor_runtime()
    if runtime_error:
        logger.error("监控 Worker 无法启动: %s", runtime_error)
        sys.exit(1)

    manager = get_monitor_manager()
    manager.start()
    logger.info("监控 Worker 进程已启动 (mode=worker)")

    stop = {"done": False}

    def _handle_signal(_signum, _frame) -> None:
        stop["done"] = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        while not stop["done"]:
            time.sleep(1)
    finally:
        manager.stop()
        logger.info("监控 Worker 进程已停止")


def cmd_init_db(args: argparse.Namespace) -> None:
    from sqlalchemy import select

    from app.crypto import apply_user_password
    from app.database import SessionLocal, init_db
    from app.models import User
    from app.settings import get_settings

    if len(args.password) < 6:
        print("密码至少 6 位")
        sys.exit(1)

    settings = get_settings()
    init_db()

    with SessionLocal() as db:
        exists = db.scalar(select(User).where(User.email == args.email))
        if exists:
            print(f"用户已存在: {args.email}")
            sys.exit(1)

        admin = User(
            email=args.email,
            role="admin",
            max_monitors=settings.default_max_monitors,
            max_bots=settings.default_max_bots,
            max_groups=settings.default_max_groups,
        )
        apply_user_password(admin, args.password)
        db.add(admin)
        db.commit()
        print(f"管理员已创建: {args.email}")
        print(f"数据库: {settings.database_url}")


def main() -> None:
    _ensure_import_path()

    parser = argparse.ArgumentParser(description="TikTok 关注监听 Web 服务")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="启动 API（默认 all=API+监控同进程）")
    run_parser.add_argument("--host", default=None, help="监听地址，默认 0.0.0.0")
    run_parser.add_argument("--port", type=int, default=None, help="端口，默认 8000")
    run_parser.add_argument(
        "--api-only",
        action="store_true",
        help="仅启动 Web/API，监控由独立 Worker 进程负责",
    )
    run_parser.add_argument(
        "--worker-only",
        action="store_true",
        help="仅启动监控 Worker（不监听 HTTP 端口）",
    )
    run_parser.set_defaults(func=cmd_run)

    worker_parser = sub.add_parser("worker", help="仅启动监控 Worker 进程")
    worker_parser.set_defaults(func=cmd_worker)

    init_parser = sub.add_parser("init-db", help="初始化数据库并创建管理员")
    init_parser.add_argument("--email", required=True, help="管理员邮箱")
    init_parser.add_argument("--password", required=True, help="管理员密码（至少6位）")
    init_parser.set_defaults(func=cmd_init_db)

    args = parser.parse_args()
    if args.command is None:
        cmd_run(
            argparse.Namespace(
                command="run",
                host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "8000")),
                api_only=False,
                worker_only=False,
                func=cmd_run,
            )
        )
        return

    args.func(args)


if __name__ == "__main__":
    main()
