#!/usr/bin/env python3
"""将 Web 版 SQLite (data/app.db) 数据迁移到 MySQL。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIGRATION_TABLES = [
    "users",
    "telegram_bots",
    "telegram_groups",
    "streamers",
    "sign_api_keys",
    "monitor_tasks",
    "follow_events",
    "join_events",
    "audit_logs",
]


def _resolve_mysql_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    from app.settings import get_settings

    return get_settings().database_url


def _configure_target_mysql(mysql_url: str) -> None:
    os.environ.pop("MYSQL_HOST", None)
    os.environ["DATABASE_URL"] = mysql_url
    from app.settings import get_settings

    get_settings.cache_clear()


def _ensure_mysql_database(mysql_url: str) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    url = make_url(mysql_url)
    db_name = url.database
    if not db_name:
        return
    server_url = url.set(database="mysql")
    engine = create_engine(server_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def export_sql(sqlite_path: Path, output_path: Path, mysql_url: str) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.schema import CreateTable
    from sqlalchemy.dialects import mysql

    _configure_target_mysql(mysql_url)
    from app import models  # noqa: F401
    from app.database import Base

    sqlite_engine = create_engine(
        f"sqlite:///{sqlite_path.resolve()}",
        connect_args={"check_same_thread": False},
    )
    dialect = mysql.dialect()
    lines = [
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS=0;",
    ]
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in MIGRATION_TABLES:
            lines.append(f"DROP TABLE IF EXISTS `{table.name}`;")
    for table in Base.metadata.sorted_tables:
        if table.name not in MIGRATION_TABLES:
            continue
        lines.append(str(CreateTable(table).compile(dialect=dialect)).rstrip(";") + ";")
    for table in MIGRATION_TABLES:
        with sqlite_engine.connect() as conn:
            rows = conn.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
        if not rows:
            continue
        columns = list(rows[0].keys())
        col_sql = ", ".join(f"`{c}`" for c in columns)
        for row in rows:
            vals = ", ".join(_sql_literal(row[c]) for c in columns)
            lines.append(f"INSERT INTO `{table}` ({col_sql}) VALUES ({vals});")
        max_id = max(int(row["id"]) for row in rows)
        lines.append(f"ALTER TABLE `{table}` AUTO_INCREMENT = {max_id + 1};")
    lines.append("SET FOREIGN_KEY_CHECKS=1;")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已导出 SQL: {output_path} ({len(lines)} 语句)")


def _count_rows(engine, table: str) -> int:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if not insp.has_table(table):
        return 0
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one())


def migrate(sqlite_path: Path, mysql_url: str, *, force: bool) -> None:
    sqlite_path = sqlite_path.resolve()
    if not sqlite_path.is_file():
        print(f"SQLite 文件不存在: {sqlite_path}")
        sys.exit(1)
    if not mysql_url.startswith("mysql"):
        print(f"目标不是 MySQL: {mysql_url}")
        sys.exit(1)

    try:
        import pymysql  # noqa: F401
    except ImportError:
        print("请先安装: pip install pymysql")
        sys.exit(1)

    _configure_target_mysql(mysql_url)
    _ensure_mysql_database(mysql_url)

    from sqlalchemy import create_engine, inspect, text

    from app.database import init_db, engine as mysql_engine

    sqlite_engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
    )

    print(f"源 SQLite: {sqlite_path}")
    print(f"目标 MySQL: {mysql_url}")

    try:
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"无法连接 MySQL: {exc}")
        sys.exit(1)

    sqlite_counts = {t: _count_rows(sqlite_engine, t) for t in MIGRATION_TABLES}
    total_source = sum(sqlite_counts.values())
    print("源库记录数:")
    for table, count in sqlite_counts.items():
        if count:
            print(f"  {table}: {count}")
    print(f"  合计: {total_source}")

    mysql_total_before = sum(_count_rows(mysql_engine, t) for t in MIGRATION_TABLES)
    if mysql_total_before > 0 and not force:
        print(
            f"\n目标 MySQL 已有 {mysql_total_before} 条业务数据。"
            "请加 --force 确认清空后覆盖导入。"
        )
        sys.exit(1)

    print("\n正在 MySQL 建表并写入中文 COMMENT …")
    with mysql_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(MIGRATION_TABLES):
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    init_db()

    with mysql_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(MIGRATION_TABLES):
            if inspect(mysql_engine).has_table(table):
                conn.execute(text(f"TRUNCATE TABLE `{table}`"))

        for table in MIGRATION_TABLES:
            count = sqlite_counts[table]
            if count == 0:
                continue
            with sqlite_engine.connect() as sconn:
                rows = sconn.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
            if not rows:
                continue
            columns = list(rows[0].keys())
            col_sql = ", ".join(f"`{c}`" for c in columns)
            val_sql = ", ".join(f":{c}" for c in columns)
            conn.execute(
                text(f"INSERT INTO `{table}` ({col_sql}) VALUES ({val_sql})"),
                [dict(row) for row in rows],
            )
            max_id = max(int(row["id"]) for row in rows if row.get("id") is not None)
            conn.execute(text(f"ALTER TABLE `{table}` AUTO_INCREMENT = :n"), {"n": max_id + 1})
            print(f"  已导入 {table}: {len(rows)} 行")

        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    print("\n校验行数:")
    ok = True
    for table in MIGRATION_TABLES:
        src = sqlite_counts[table]
        dst = _count_rows(mysql_engine, table)
        mark = "OK" if src == dst else "MISMATCH"
        if src or dst:
            print(f"  {table}: sqlite={src} mysql={dst} [{mark}]")
        if src != dst:
            ok = False

    if not ok:
        print("\n迁移校验失败，请检查日志。")
        sys.exit(1)

    print("\n迁移完成。请重启后端使 MySQL 配置生效。")


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite app.db → MySQL 数据迁移")
    parser.add_argument(
        "--sqlite",
        default=str(ROOT / "data" / "app.db"),
        help="SQLite 文件路径（默认 data/app.db）",
    )
    parser.add_argument(
        "--mysql-url",
        default="",
        help="MySQL 连接串；留空则读取 .env 的 MYSQL_* / DATABASE_URL",
    )
    parser.add_argument(
        "--export-sql",
        default="",
        help="仅导出 SQL 文件到指定路径，不连接 MySQL",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="目标库已有数据时仍清空并覆盖",
    )
    args = parser.parse_args()
    mysql_url = _resolve_mysql_url(args.mysql_url or None)
    if args.export_sql:
        export_sql(Path(args.sqlite), Path(args.export_sql), mysql_url)
        return
    migrate(Path(args.sqlite), mysql_url, force=args.force)


if __name__ == "__main__":
    main()
