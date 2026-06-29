import collections
import time


class WebSocketRateLimiter:
    def __init__(self, max_messages, window_seconds, clock=time.monotonic):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.clock = clock
        self.timestamps = collections.deque()

    def clear(self):
        self.timestamps.clear()

    def allow(self):
        now = self.clock()
        window_start = now - self.window_seconds
        while self.timestamps and self.timestamps[0] < window_start:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.max_messages:
            return False

        self.timestamps.append(now)
        return True
