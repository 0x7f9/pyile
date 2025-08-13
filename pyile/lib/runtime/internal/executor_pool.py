from pyile.lib.utils.common import get_thread_count
from pyile.lib.runtime.internal.constants import MAX_WORKERS_BACKUP
from pyile.lib.utils.lazy import LazyInit

from concurrent.futures import ThreadPoolExecutor
import threading 
from typing import Optional

class ExecutorPool(LazyInit):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hash_executor = None
        self._backup_executor = None
        self._shutdown = False

    def _new_executor(self, max_workers: int, prefix: str) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=prefix
        )

    def restart(self) -> None:
        with self._lock:
            if self._shutdown:
                self._shutdown = False

    def get_hash_executor(self) -> Optional[ThreadPoolExecutor]:
        if self._shutdown:
            return None
        if self._hash_executor is not None:
            return self._hash_executor

        executor = self._new_executor(get_thread_count(), "BGHasher")
        with self._lock:
            if self._hash_executor is None and not self._shutdown:
                self._hash_executor = executor
                return self._hash_executor
        executor.shutdown(wait=False)
        return self._hash_executor

    def get_backup_executor(self) -> Optional[ThreadPoolExecutor]:
        if self._shutdown:
            return None
        if self._backup_executor is not None:
            return self._backup_executor

        workers = min(MAX_WORKERS_BACKUP, get_thread_count())
        executor = self._new_executor(workers, "BGBackup")
        with self._lock:
            if self._backup_executor is None and not self._shutdown:
                self._backup_executor = executor
                return self._backup_executor
        executor.shutdown(wait=False)
        return self._backup_executor

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
            if self._hash_executor:
                self._hash_executor.shutdown(wait=wait)
                self._hash_executor = None
            if self._backup_executor:
                self._backup_executor.shutdown(wait=wait)
                self._backup_executor = None

