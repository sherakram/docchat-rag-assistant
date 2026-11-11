import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """Sliding window: har client IP ek window mein max_calls se zyada requests nahi bhej sakta.

    Sirf ek process ki memory mein rehta hai (server restart par saaf). Chhote project ke liye theek.
    """

    def __init__(self, max_calls: int, per_seconds: int):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self.calls[key]

        # Window se purani calls hata do
        while window and now - window[0] > self.per_seconds:
            window.popleft()

        if len(window) >= self.max_calls:
            retry_after = int(self.per_seconds - (now - window[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)