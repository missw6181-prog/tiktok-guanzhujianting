import time


class JoinPushRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._timestamps: list[float] = []

    def allow(self) -> bool:
        if self._limit <= 0:
            return True

        now = time.monotonic()
        self._timestamps = [t for t in self._timestamps if now - t < 60.0]
        if len(self._timestamps) >= self._limit:
            return False

        self._timestamps.append(now)
        return True
