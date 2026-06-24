import csv
import io
from datetime import datetime
from typing import Literal, Optional, TypeVar

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import FollowEvent, JoinEvent
from app.services import tiktok_profile_url

_EXPORT_MAX_ROWS = 50_000

ModelT = TypeVar("ModelT")


def build_follow_filters(
    user_id: int,
    streamer: Optional[str],
    today_only: bool,
    today_start: datetime,
) -> list:
    filters = [FollowEvent.user_id == user_id]
    if streamer:
        filters.append(FollowEvent.streamer_unique_id == streamer)
    if today_only:
        filters.append(FollowEvent.detected_at >= today_start)
    return filters


def build_join_filters(
    user_id: int,
    streamer: Optional[str],
    today_only: bool,
    today_start: datetime,
) -> list:
    filters = [JoinEvent.user_id == user_id]
    if streamer:
        filters.append(JoinEvent.streamer_unique_id == streamer)
    if today_only:
        filters.append(JoinEvent.detected_at >= today_start)
    return filters


def count_rows(db: Session, model: type[ModelT], filters: list) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0


def fetch_follow_rows(
    db: Session,
    filters: list,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[FollowEvent]:
    return db.scalars(
        select(FollowEvent)
        .where(*filters)
        .order_by(desc(FollowEvent.detected_at))
        .offset(offset)
        .limit(limit)
    ).all()


def fetch_join_rows(
    db: Session,
    filters: list,
    *,
    offset: int = 0,
    limit: int = 50,
) -> list[JoinEvent]:
    return db.scalars(
        select(JoinEvent)
        .where(*filters)
        .order_by(desc(JoinEvent.detected_at))
        .offset(offset)
        .limit(limit)
    ).all()


def _format_dt(value: datetime) -> str:
    if value.tzinfo is not None:
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return value.strftime("%Y-%m-%d %H:%M:%S")


def export_follows_txt(rows: list[FollowEvent]) -> str:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        follower = row.follower_unique_id.lstrip("@")
        streamer = row.streamer_unique_id.lstrip("@")
        nickname = row.follower_nickname or follower
        lines.append(
            f"{index}、有新用户{nickname}({follower})关注了主播@{streamer}\n"
            f"客户首页链接\n"
            f"{tiktok_profile_url(follower)}\n"
            f"时间: {_format_dt(row.detected_at)}"
        )
    return "\n\n".join(lines)


def export_joins_txt(rows: list[JoinEvent]) -> str:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        guest = row.guest_unique_id.lstrip("@")
        streamer = row.streamer_unique_id.lstrip("@")
        nickname = row.guest_nickname or guest
        lines.append(
            f"{index}、用户{nickname}({guest})进入@{streamer}直播间\n"
            f"客户首页链接\n"
            f"{tiktok_profile_url(guest)}\n"
            f"时间: {_format_dt(row.detected_at)}"
        )
    return "\n\n".join(lines)


def export_follows_csv(rows: list[FollowEvent]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["主播", "主播首页链接", "关注者", "昵称", "客户首页链接", "时间"]
    )
    for row in rows:
        streamer = row.streamer_unique_id.lstrip("@")
        follower = row.follower_unique_id.lstrip("@")
        writer.writerow(
            [
                f"@{streamer}",
                tiktok_profile_url(streamer),
                f"@{follower}",
                row.follower_nickname,
                tiktok_profile_url(follower),
                _format_dt(row.detected_at),
            ]
        )
    return buffer.getvalue()


def export_joins_csv(rows: list[JoinEvent]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["主播", "主播首页链接", "用户", "昵称", "客户首页链接", "时间"]
    )
    for row in rows:
        streamer = row.streamer_unique_id.lstrip("@")
        guest = row.guest_unique_id.lstrip("@")
        writer.writerow(
            [
                f"@{streamer}",
                tiktok_profile_url(streamer),
                f"@{guest}",
                row.guest_nickname,
                tiktok_profile_url(guest),
                _format_dt(row.detected_at),
            ]
        )
    return buffer.getvalue()


def export_content(
    kind: Literal["follows", "joins"],
    fmt: Literal["txt", "csv"],
    rows: list,
) -> tuple[str, str, str]:
    if kind == "follows":
        if fmt == "txt":
            return export_follows_txt(rows), "text/plain; charset=utf-8", "txt"
        return export_follows_csv(rows), "text/csv; charset=utf-8", "csv"
    if fmt == "txt":
        return export_joins_txt(rows), "text/plain; charset=utf-8", "txt"
    return export_joins_csv(rows), "text/csv; charset=utf-8", "csv"


def export_max_rows() -> int:
    return _EXPORT_MAX_ROWS
