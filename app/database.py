from collections.abc import Generator

from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith(
    "sqlite"
) else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _is_sqlite_engine() -> bool:
    return settings.database_url.startswith("sqlite")


def _index_exists(insp, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in insp.get_indexes(table_name))


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_schema()


def _migrate_schema() -> None:
    """为已有 SQLite 数据库补字段（create_all 不会 ALTER 旧表）。"""
    insp = inspect(engine)

    user_statements = []
    if insp.has_table("users"):
        user_cols = {col["name"] for col in insp.get_columns("users")}
        if "password_plain" not in user_cols:
            user_statements.append(
                "ALTER TABLE users ADD COLUMN password_plain VARCHAR(128)"
            )
    if user_statements:
        with engine.begin() as conn:
            for sql in user_statements:
                conn.execute(text(sql))

    if not insp.has_table("telegram_bots"):
        return

    bot_cols = {col["name"] for col in insp.get_columns("telegram_bots")}
    bot_statements = []
    if "bot_telegram_id" not in bot_cols:
        bot_statements.append("ALTER TABLE telegram_bots ADD COLUMN bot_telegram_id INTEGER")
    if "username" not in bot_cols:
        bot_statements.append("ALTER TABLE telegram_bots ADD COLUMN username VARCHAR(100)")

    group_statements = []
    if insp.has_table("telegram_groups"):
        group_cols = {col["name"] for col in insp.get_columns("telegram_groups")}
        if "bot_id" not in group_cols:
            group_statements.append(
                "ALTER TABLE telegram_groups ADD COLUMN bot_id INTEGER "
                "REFERENCES telegram_bots(id) ON DELETE SET NULL"
            )

    task_statements = []
    if insp.has_table("monitor_tasks"):
        task_cols = {col["name"] for col in insp.get_columns("monitor_tasks")}
        if "sign_api_key_encrypted" not in task_cols:
            task_statements.append(
                "ALTER TABLE monitor_tasks ADD COLUMN sign_api_key_encrypted TEXT"
            )
        if "sign_api_key_hash" not in task_cols:
            task_statements.append(
                "ALTER TABLE monitor_tasks ADD COLUMN sign_api_key_hash VARCHAR(64)"
            )
        if "sign_api_key_hint" not in task_cols:
            task_statements.append(
                "ALTER TABLE monitor_tasks ADD COLUMN sign_api_key_hint VARCHAR(20)"
            )
        if "sign_api_key_id" not in task_cols:
            task_statements.append(
                "ALTER TABLE monitor_tasks ADD COLUMN sign_api_key_id INTEGER "
                "REFERENCES sign_api_keys(id) ON DELETE SET NULL"
            )

    statements = bot_statements + group_statements + task_statements
    if statements:
        with engine.begin() as conn:
            for sql in statements:
                conn.execute(text(sql))

    _migrate_task_keys_to_pool()
    _ensure_sign_api_key_pool_unique_index()
    _sync_schema_comments()


def _sync_schema_comments() -> None:
    from app.schema_sync import sync_schema_comments_to_engine

    sync_schema_comments_to_engine(engine)


def _migrate_task_keys_to_pool() -> None:
    """将任务上遗留的 Key 迁移到 API Key 池。"""
    insp = inspect(engine)
    if not insp.has_table("sign_api_keys") or not insp.has_table("monitor_tasks"):
        return

    from app.models import SignApiKey

    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT id, user_id, sign_api_key_encrypted, sign_api_key_hash "
                "FROM monitor_tasks "
                "WHERE sign_api_key_encrypted IS NOT NULL AND sign_api_key_id IS NULL"
            )
        ).all()
        for task_id, user_id, enc, fp in rows:
            pool_id = db.scalar(
                text("SELECT id FROM sign_api_keys WHERE sign_api_key_hash = :fp LIMIT 1"),
                {"fp": fp},
            )
            if pool_id is None:
                row = SignApiKey(
                    user_id=user_id,
                    sign_api_key_encrypted=enc,
                    sign_api_key_hash=fp,
                )
                db.add(row)
                db.flush()
                pool_id = row.id
            db.execute(
                text("UPDATE monitor_tasks SET sign_api_key_id = :pid WHERE id = :tid"),
                {"pid": pool_id, "tid": task_id},
            )
        db.commit()


def _ensure_sign_api_key_pool_unique_index() -> None:
    insp = inspect(engine)
    if not insp.has_table("sign_api_keys"):
        return
    with engine.begin() as conn:
        if not _index_exists(insp, "sign_api_keys", "uq_sign_api_key_hash"):
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_sign_api_key_hash "
                    "ON sign_api_keys (sign_api_key_hash)"
                )
            )
        if _is_sqlite_engine() and not _index_exists(
            insp, "monitor_tasks", "uq_task_sign_api_key_id"
        ):
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_task_sign_api_key_id "
                    "ON monitor_tasks(sign_api_key_id) "
                    "WHERE sign_api_key_id IS NOT NULL"
                )
            )

