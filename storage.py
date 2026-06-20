import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FollowRecord:
    follower_unique_id: str
    follower_nickname: str
    streamer_unique_id: str
    detected_at: datetime


@dataclass(frozen=True)
class JoinRecord:
    user_unique_id: str
    nickname: str
    streamer_unique_id: str
    detected_at: datetime


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_unique_id TEXT NOT NULL,
            follower_nickname TEXT NOT NULL,
            streamer_unique_id TEXT NOT NULL,
            detected_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS joins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_unique_id TEXT NOT NULL,
            nickname TEXT NOT NULL,
            streamer_unique_id TEXT NOT NULL,
            detected_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_follows_user_streamer
        ON follows (follower_unique_id, streamer_unique_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_joins_user_streamer
        ON joins (user_unique_id, streamer_unique_id)
        """
    )


def follow_exists_for_streamer(
    db_path: Path,
    follower_unique_id: str,
    streamer_unique_id: str,
) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM follows
            WHERE follower_unique_id = ? AND streamer_unique_id = ?
            LIMIT 1
            """,
            (follower_unique_id, streamer_unique_id),
        ).fetchone()
    return row is not None


def join_exists_for_streamer(
    db_path: Path,
    user_unique_id: str,
    streamer_unique_id: str,
) -> bool:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM joins
            WHERE user_unique_id = ? AND streamer_unique_id = ?
            LIMIT 1
            """,
            (user_unique_id, streamer_unique_id),
        ).fetchone()
    return row is not None


class FollowStorage:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            _ensure_schema(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def should_save(self, follower_unique_id: str, streamer_unique_id: str) -> bool:
        return not follow_exists_for_streamer(
            self._db_path, follower_unique_id, streamer_unique_id
        )

    def save(self, record: FollowRecord) -> bool:
        if not self.should_save(record.follower_unique_id, record.streamer_unique_id):
            return False

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO follows (
                    follower_unique_id,
                    follower_nickname,
                    streamer_unique_id,
                    detected_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.follower_unique_id,
                    record.follower_nickname,
                    record.streamer_unique_id,
                    record.detected_at.isoformat(),
                ),
            )
        return True

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM follows").fetchone()
        return int(row["n"]) if row else 0


class JoinStorage:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            _ensure_schema(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def should_save(self, user_unique_id: str, streamer_unique_id: str) -> bool:
        return not join_exists_for_streamer(
            self._db_path, user_unique_id, streamer_unique_id
        )

    def save(self, record: JoinRecord) -> bool:
        if not self.should_save(record.user_unique_id, record.streamer_unique_id):
            return False

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO joins (
                    user_unique_id,
                    nickname,
                    streamer_unique_id,
                    detected_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.user_unique_id,
                    record.nickname,
                    record.streamer_unique_id,
                    record.detected_at.isoformat(),
                ),
            )
        return True

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM joins").fetchone()
        return int(row["n"]) if row else 0
