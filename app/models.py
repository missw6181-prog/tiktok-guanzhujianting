from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.schema_comments import TABLE_COMMENTS, column_comment


def _apply_schema_comments(model: type) -> None:
    name = model.__tablename__
    tbl = model.__table__
    if name in TABLE_COMMENTS:
        tbl.comment = TABLE_COMMENTS[name]
    for col in tbl.columns:
        c = column_comment(name, col.name)
        if c:
            col.comment = c


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_plain: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")
    status: Mapped[str] = mapped_column(String(20), default="active")
    max_monitors: Mapped[int] = mapped_column(Integer, default=10)
    max_bots: Mapped[int] = mapped_column(Integer, default=10)
    max_groups: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    bots: Mapped[List["TelegramBot"]] = relationship(back_populates="user")
    groups: Mapped[List["TelegramGroup"]] = relationship(back_populates="user")
    streamers: Mapped[List["Streamer"]] = relationship(back_populates="user")
    tasks: Mapped[List["MonitorTask"]] = relationship(back_populates="user")
    sign_api_keys: Mapped[List["SignApiKey"]] = relationship(back_populates="user")


class TelegramBot(Base):
    __tablename__ = "telegram_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    bot_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bot_token_encrypted: Mapped[str] = mapped_column(Text)
    token_hint: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="bots")


class TelegramGroup(Base):
    __tablename__ = "telegram_groups"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "chat_id",
            "bot_id",
            name="uq_group_user_chat_bot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    bot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("telegram_bots.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100))
    chat_id: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="groups")
    bot: Mapped[Optional["TelegramBot"]] = relationship(foreign_keys=[bot_id])


class Streamer(Base):
    __tablename__ = "streamers"
    __table_args__ = (
        UniqueConstraint("unique_id", name="uq_streamer_unique_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    unique_id: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="streamers")
    tasks: Mapped[List["MonitorTask"]] = relationship(back_populates="streamer")


class SignApiKey(Base):
    __tablename__ = "sign_api_keys"
    __table_args__ = (
        UniqueConstraint("sign_api_key_hash", name="uq_sign_api_key_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sign_api_key_encrypted: Mapped[str] = mapped_column(Text)
    sign_api_key_hash: Mapped[str] = mapped_column(String(64))
    rate_limit_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rate_limit_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sign_api_keys")
    task: Mapped[Optional["MonitorTask"]] = relationship(
        back_populates="sign_api_key", uselist=False
    )


class MonitorTask(Base):
    __tablename__ = "monitor_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"))
    follow_bot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("telegram_bots.id", ondelete="SET NULL"), nullable=True
    )
    follow_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("telegram_groups.id", ondelete="SET NULL"), nullable=True
    )
    join_bot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("telegram_bots.id", ondelete="SET NULL"), nullable=True
    )
    join_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("telegram_groups.id", ondelete="SET NULL"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="idle")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    join_rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=20)
    sign_api_key_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sign_api_keys.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    sign_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sign_api_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sign_api_key_hint: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship(back_populates="tasks")
    streamer: Mapped["Streamer"] = relationship(back_populates="tasks")
    follow_bot: Mapped[Optional["TelegramBot"]] = relationship(
        foreign_keys=[follow_bot_id]
    )
    follow_group: Mapped[Optional["TelegramGroup"]] = relationship(
        foreign_keys=[follow_group_id]
    )
    join_bot: Mapped[Optional["TelegramBot"]] = relationship(foreign_keys=[join_bot_id])
    join_group: Mapped[Optional["TelegramGroup"]] = relationship(
        foreign_keys=[join_group_id]
    )
    sign_api_key: Mapped[Optional["SignApiKey"]] = relationship(back_populates="task")


class FollowEvent(Base):
    __tablename__ = "follow_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "streamer_unique_id",
            "follower_unique_id",
            name="uq_follow_user_streamer_follower",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitor_tasks.id", ondelete="SET NULL"), nullable=True
    )
    streamer_unique_id: Mapped[str] = mapped_column(String(100))
    follower_unique_id: Mapped[str] = mapped_column(String(100))
    follower_nickname: Mapped[str] = mapped_column(String(200), default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JoinEvent(Base):
    __tablename__ = "join_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "streamer_unique_id",
            "guest_unique_id",
            name="uq_join_user_streamer_guest",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitor_tasks.id", ondelete="SET NULL"), nullable=True
    )
    streamer_unique_id: Mapped[str] = mapped_column(String(100))
    guest_unique_id: Mapped[str] = mapped_column(String(100))
    guest_nickname: Mapped[str] = mapped_column(String(200), default="")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(100))
    target_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


for _model in (
    User,
    TelegramBot,
    TelegramGroup,
    Streamer,
    SignApiKey,
    MonitorTask,
    FollowEvent,
    JoinEvent,
    AuditLog,
):
    _apply_schema_comments(_model)
