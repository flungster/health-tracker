"""In-memory sliding-window rate limiter.

The limiter counts how often a key (for example a client IP address) is
seen within a fixed window and rejects calls once the limit is reached.
It is in-memory and process-local: state is shared across all requests
handled by this process and is lost on a restart. That is deliberate —
the app is self-hosted and runs a single API process, and a counter reset
on restart is acceptable for a LAN deployment.

State stays bounded: a key whose most recent hit is older than
``_STALE_AFTER_SECONDS`` is swept away, so idle or one-off keys do not
accumulate. Every window used by this app is 60 seconds, well below that.
"""

import math
import threading
import time
from collections import deque

_STALE_AFTER_SECONDS = 300.0
_SWEEP_INTERVAL_SECONDS = 60.0


class RateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary string."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, deque[float]] = {}
        self._last_sweep = time.monotonic()

    def check(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Record one hit for ``key``.

        Returns ``None`` when the hit is allowed, otherwise the number of
        whole seconds to wait before the key may try again.
        """
        now = time.monotonic()
        with self._lock:
            self._sweep_stale_locked(now)
            window = self._windows.setdefault(key, deque())
            cutoff = now - window_seconds
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                retry_after = math.ceil(window[0] + window_seconds - now)
                return max(1, retry_after)
            window.append(now)
            return None

    def reset(self) -> None:
        """Forget every recorded hit (used by the test suite)."""
        with self._lock:
            self._windows.clear()
            self._last_sweep = time.monotonic()

    def _sweep_stale_locked(self, now: float) -> None:
        """Periodically drop keys whose most recent hit is long past."""
        if now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep = now
        stale = [
            key
            for key, window in self._windows.items()
            if not window or window[-1] + _STALE_AFTER_SECONDS < now
        ]
        for key in stale:
            del self._windows[key]
