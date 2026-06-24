#!/usr/bin/env python3
"""生产环境入口：启动 Web 服务或初始化数据库。"""
from __future__ import annotations

import argparse
import os
import sys


def _ensure_import_path() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)


def cmd_run(args: argparse.Namespace) -> None:
    import uvicorn

    from app.main import app

    host = args.host or os.getenv("HOST", "0.0.0.0")
    port = args.port or int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level=os.getenv("LOG_LEVEL", "info").lower())


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

    run_parser = sub.add_parser("run", help="启动 API 与监听服务（默认）")
    run_parser.add_argument("--host", default=None, help="监听地址，默认 0.0.0.0")
    run_parser.add_argument("--port", type=int, default=None, help="端口，默认 8000")
    run_parser.set_defaults(func=cmd_run)

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
                func=cmd_run,
            )
        )
        return

    args.func(args)


if __name__ == "__main__":
    main()
