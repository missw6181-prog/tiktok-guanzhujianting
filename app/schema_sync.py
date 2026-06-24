"""将 schema_comments 同步到 SQLite 注释表或 MySQL 表级 COMMENT。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.schema_comments import TABLE_COMMENTS, iter_comment_rows

_README_TEXT = (
    "SQLite 不支持在「设计表」里显示字段注释（Navicat 的 Comment 列仅 MySQL/PG 等支持）。"
    "请打开视图「中文注释字典」或表 db_schema_comments 查看所有表/字段的中文说明。"
    "Web 版数据库文件：data/app.db"
)

_SCHEMA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS db_schema_comments (
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL DEFAULT '',
    comment_zh TEXT NOT NULL,
    PRIMARY KEY (table_name, column_name)
)
"""

_README_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS __readme__ (
    说明 TEXT NOT NULL
)
"""

_COMMENT_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS 中文注释字典 AS
SELECT
    table_name AS 表名,
    CASE WHEN column_name = '' THEN '(整表)' ELSE column_name END AS 字段名,
    comment_zh AS 中文说明
FROM db_schema_comments
ORDER BY table_name, column_name
"""

_LEGACY_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS v_schema_字典 AS
SELECT
    CASE
        WHEN column_name = '' THEN table_name
        ELSE table_name || '.' || column_name
    END AS 对象,
    comment_zh AS 中文说明
FROM db_schema_comments
ORDER BY table_name, column_name
"""

_CLI_TABLES = frozenset({"follows", "joins", "db_schema_comments", "__readme__"})

_MYSQL_SKIP_TABLES = frozenset({"db_schema_comments", "__readme__"})


def _sync_sqlite_comments(engine: Engine) -> None:
    rows = iter_comment_rows()
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA_TABLE_SQL))
        conn.execute(text(_README_TABLE_SQL))
        conn.execute(text(_COMMENT_VIEW_SQL))
        conn.execute(text(_LEGACY_VIEW_SQL))
        conn.execute(text("DELETE FROM db_schema_comments"))
        conn.execute(
            text(
                "INSERT INTO db_schema_comments (table_name, column_name, comment_zh) "
                "VALUES (:table_name, :column_name, :comment_zh)"
            ),
            [{"table_name": t, "column_name": c, "comment_zh": z} for t, c, z in rows],
        )
        conn.execute(text("DELETE FROM __readme__"))
        conn.execute(text("INSERT INTO __readme__ (说明) VALUES (:t)"), {"t": _README_TEXT})


def _sync_mysql_comments(engine: Engine) -> None:
    """MySQL 字段 COMMENT 由 create_all 写入；此处补表级 COMMENT。"""
    from app import models  # noqa: F401
    from app.database import Base

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name in _MYSQL_SKIP_TABLES:
                continue
            table_comment = table.comment or TABLE_COMMENTS.get(table.name)
            if table_comment:
                conn.execute(
                    text(f"ALTER TABLE `{table.name}` COMMENT = :c"),
                    {"c": table_comment},
                )


def sync_schema_comments_to_engine(engine: Engine) -> None:
    url = str(engine.url)
    if url.startswith("sqlite"):
        _sync_sqlite_comments(engine)
    elif url.startswith("mysql"):
        _sync_mysql_comments(engine)


def _write_comment_rows(conn, rows: list[tuple[str, str, str]]) -> None:
    conn.execute(_SCHEMA_TABLE_SQL)
    conn.execute(_README_TABLE_SQL)
    conn.execute(_COMMENT_VIEW_SQL)
    conn.execute(_LEGACY_VIEW_SQL)
    conn.execute("DELETE FROM db_schema_comments")
    conn.executemany(
        "INSERT INTO db_schema_comments (table_name, column_name, comment_zh) "
        "VALUES (?, ?, ?)",
        rows,
    )
    conn.execute("DELETE FROM __readme__")
    conn.execute("INSERT INTO __readme__ (说明) VALUES (?)", (_README_TEXT,))


def sync_schema_comments_to_sqlite_path(db_path: Path) -> None:
    """同步 CLI 库 data/follows.db 的注释表。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [(t, c, z) for t, c, z in iter_comment_rows() if t in _CLI_TABLES]

    with sqlite3.connect(db_path) as conn:
        _write_comment_rows(conn, rows)
        conn.commit()
