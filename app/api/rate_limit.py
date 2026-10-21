from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimitExceeded(Exception):
    pass


class InMemoryRateLimiter:
    """Per-key sliding window. Not shared across processes or instances."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> None:
        now = time.monotonic()
        queue = self._hits[key]
        while queue and now - queue[0] >= self.window_seconds:
            queue.popleft()
        if len(queue) >= self.max_requests:
            raise RateLimitExceeded
        queue.append(now)
