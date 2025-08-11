from pyile.lib.runtime.internal.thread_safe import AtomicFlag

from typing import Optional

import threading
import weakref

class DirState:
    __slots__ = (
        "path", "_lock", "_monitor", "is_active"
    )

    def __init__(self, path):
        self.path = path
        self.is_active = AtomicFlag(False)
        
        self._lock = threading.RLock()
        self._monitor = None  
    
    def set_monitor(self, monitor_instance) -> None:
        self._monitor = weakref.ref(monitor_instance)
        self.is_active.set()
    
    def get_monitor(self) -> Optional[None]:
        if self._monitor:
            return self._monitor()
        return None
    
    def cleanup(self) -> None:
        with self._lock:
            monitor = self.get_monitor()
            if monitor:
                try:
                    monitor.stop()
                except Exception:
                    pass
            self._monitor = None
            self.is_active.clear()

            