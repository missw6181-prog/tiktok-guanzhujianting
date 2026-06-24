import json
from pathlib import Path
from typing import Dict, Optional

CACHE_PATH = Path(__file__).resolve().parent / "data" / "room_cache.json"


def _load_all() -> Dict[str, int]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def get_room_id(streamer_unique_id: str) -> Optional[int]:
    return _load_all().get(streamer_unique_id.lstrip("@"))


def save_room_id(streamer_unique_id: str, room_id: int) -> None:
    streamer = streamer_unique_id.lstrip("@")
    cache = _load_all()
    cache[streamer] = int(room_id)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def clear_room_id(streamer_unique_id: str) -> None:
    streamer = streamer_unique_id.lstrip("@")
    cache = _load_all()
    if streamer not in cache:
        return
    del cache[streamer]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if cache:
        CACHE_PATH.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    elif CACHE_PATH.exists():
        CACHE_PATH.unlink()
