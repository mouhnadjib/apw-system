"""تحديد معدل الطلبات في الذاكرة (نافذة منزلقة).

مناسب لخادم بعملية واحدة (uvicorn بلا عمّال متعددين، كما في النشر الحالي).
إعادة تشغيل الخادم تصفّر العدّادات، وهذا مقبول: الحماية الأساسية للعدّ لا للتخزين.
"""
import threading
import time
from collections import deque


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_gc = time.monotonic()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        return q

    def _gc(self, now: float) -> None:
        if now - self._last_gc < 300:
            return
        self._last_gc = now
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] > 3600]:
            del self._hits[k]

    def hit(self, key: str, limit: int, window: float) -> bool:
        """يسجّل محاولة؛ يُرجع False إن تجاوزت الحد (ولا تُسجَّل المحاولة الزائدة)."""
        now = time.monotonic()
        with self._lock:
            self._gc(now)
            q = self._prune(key, window, now)
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def count(self, key: str, window: float) -> int:
        now = time.monotonic()
        with self._lock:
            return len(self._prune(key, window, now))

    def add(self, key: str) -> None:
        with self._lock:
            self._hits.setdefault(key, deque()).append(time.monotonic())

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


limiter = SlidingWindow()
