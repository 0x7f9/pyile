from pyile.lib.utils.common import get_cache_path, ensure_file_dir_exists
from pyile.lib.utils.logging import log_error, log_info
from pyile.lib.utils.lazy import LazyInit
from pyile.lib.runtime.cache_manager.slab_cache import AppCache

import threading
from typing import Any, Optional, Dict

_SLAB_PATH = get_cache_path("pyile.cache.slab")

_main_lock = threading.RLock()  

class SlabCache(LazyInit):
    __slots__ = ('_slab', '_is_init')

    def __init__(self) -> None:
        self._slab = None
        self._is_init = False

    def load(self) -> None:
        if self._is_init:
            return
        
        self._slab = load_file_cache()
        self._is_init = True

        try:
            from pyile.lib.runtime.cache_manager.cache import validate_cache
            integrity = validate_cache()
            if "error" in integrity:
                log_error(f"Error getting Application Cache: {integrity['error']}")
            else:
                log_info(f"Cache integrity check passed: {integrity}")
        except Exception as e:
            log_error(f"Cache validation failed: {e}")

    def save(self) -> bool:
        if self._is_init and self._slab:
            try:
                self._slab.flush()
                return True
            except Exception as e:
                log_error(f"Failed to save cache {e}")
                return False
        return False
    
    def close(self) -> None:
        with _main_lock:
            if not self._slab:
                return
            
            try:
                self._slab.close()
            except Exception as e:
                log_error(f"Error closing slab: {e}")
            self._slab = None
            self._is_init = False

def load_file_cache() -> Optional[AppCache]:
    ensure_file_dir_exists(_SLAB_PATH)
    slab = AppCache.get(_SLAB_PATH)
    slab.open()
    return slab

def is_file_cached(file_key: int) -> bool:
    cache = SlabCache.get()
    if not cache._slab:
        return False
    
    with _main_lock:
        try:
            return cache._slab.has_entry(file_key)
        except Exception as e:
            log_error(f"Failed to check slab cache {e}")
            return False

def update_cache_entry(file_key: int) -> None:
    cache = SlabCache.get()
    if not cache._slab:
        return None
    
    with _main_lock:
        cache._slab.append_entry(file_key)
        cache._slab.flush()

def _wait_loaded(timeout: float = 10.0) -> bool:
    import time
    cache = SlabCache.get()
    start = time.time()
    
    while not cache._is_init:
        if (time.time() - start) > timeout:
            return False
        time.sleep(0.1)
    return True

def get_cache_stats() -> Dict[str, Any]:
    if not _wait_loaded():
        log_error("Cache did not load within 10.0 seconds")
        return {
            "error": "Cache did not load within 10.0 seconds"
        }
    
    cache = SlabCache.get()
    if not cache._slab:
        return {"error": "Cache not found"}

    entries = 0
    with _main_lock:
        try:
            entries = cache._slab.get_len()
        except Exception:
            pass
    
    return {"slab_entries": entries, "slab_path": _SLAB_PATH}

def validate_cache() -> Dict[str, Any]:
    cache = SlabCache.get()
    if not cache._is_init:
        return {"error": "Cache not found"}
    
    try:
        return get_cache_stats()
    except Exception as e:
        return {"error": str(e)}
    
