from pyile.lib.runtime.internal.thread_safe import AtomicCounter, ThreadSafeDict
from pyile.lib.utils.lazy import LazyInit

import threading
from typing import Optional

class GlobalStats(LazyInit):
    def __init__(self) -> None:
        self.file_count = AtomicCounter(0)
        self.match_count = AtomicCounter(0)
        self.file_hashes = ThreadSafeDict()
        self.user_stats = ThreadSafeDict()

        self._lock = threading.RLock()
        # self._lock = threading.Lock()
        self._last_file = None

    def set_last_file(self, value: Optional[str]) -> None:
        with self._lock:
            self._last_file = value

    def get_last_file(self) -> Optional[str]:
        with self._lock:
            return self._last_file

