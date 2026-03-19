"""
Rate limiter for Instagram Graph API.
Instagram allows 200 calls/hour per user token (standard tier).
We stay conservative at 150/hour with a per-call minimum gap.
"""

import time
import threading
from collections import deque
from typing import Optional


class RateLimiter:
    """
    Token-bucket style rate limiter.
    Tracks calls in a rolling 1-hour window.
    """

    HOURLY_LIMIT = 150          # Instagram allows 200; we cap at 150
    MIN_CALL_GAP_SEC = 1.5      # Minimum seconds between any two calls
    BURST_MAX = 10              # Max calls in any 60-second window

    def __init__(self):
        self._lock = threading.Lock()
        self._call_times: deque = deque()   # timestamps of recent calls
        self._last_call: float = 0.0

    def wait(self) -> None:
        """Block until it is safe to make the next API call."""
        with self._lock:
            now = time.monotonic()

            # 1. Enforce minimum gap between consecutive calls
            gap = now - self._last_call
            if gap < self.MIN_CALL_GAP_SEC:
                time.sleep(self.MIN_CALL_GAP_SEC - gap)
                now = time.monotonic()

            # 2. Purge timestamps older than 1 hour
            one_hour_ago = now - 3600
            while self._call_times and self._call_times[0] < one_hour_ago:
                self._call_times.popleft()

            # 3. Enforce hourly limit
            if len(self._call_times) >= self.HOURLY_LIMIT:
                oldest = self._call_times[0]
                sleep_for = (oldest + 3600) - now + 1
                time.sleep(sleep_for)
                now = time.monotonic()
                # Re-purge after sleep
                one_hour_ago = now - 3600
                while self._call_times and self._call_times[0] < one_hour_ago:
                    self._call_times.popleft()

            # 4. Enforce burst limit (10 calls per 60 seconds)
            one_min_ago = now - 60
            recent = sum(1 for t in self._call_times if t > one_min_ago)
            if recent >= self.BURST_MAX:
                # Find oldest call in the last minute and wait past it
                for t in self._call_times:
                    if t > one_min_ago:
                        sleep_for = (t + 60) - now + 0.5
                        time.sleep(sleep_for)
                        break
                now = time.monotonic()

            self._call_times.append(now)
            self._last_call = now

    @property
    def calls_this_hour(self) -> int:
        now = time.monotonic()
        one_hour_ago = now - 3600
        return sum(1 for t in self._call_times if t > one_hour_ago)

    @property
    def calls_remaining(self) -> int:
        return self.HOURLY_LIMIT - self.calls_this_hour
