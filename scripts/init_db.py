#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.crypto import apply_user_password
from app.database import SessionLocal, init_db
from app.models import User
from app.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化数据库并创建管理员")
    parser.add_argument("--email", required=True, help="管理员邮箱")
    parser.add_argument("--password", required=True, help="管理员密码（至少6位）")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
