from pyile.lib.runtime.internal.thread_safe import ThreadSafeDict, SafeThread
from pyile.lib.utils.logging import log_debug, log_error, log_info, log_warning
from pyile.lib.runtime.internal.constants import THREAD_TIMEOUT

from typing import Callable, Optional

_thread_state = ThreadSafeDict()

def is_thread_healthy(thread_key: str) -> bool:
    ref = _thread_state.get(thread_key)
    if ref is None:
        return False
    
    thread = ref()
    if thread is None:
        _thread_state.pop(thread_key, None) 
        return False
    
    return thread.is_alive()

def start_thread_if_needed(
        thread_key: str, 
        target_fn: Callable, 
        name: Optional[str] = None,  
        *args, 
        **kwargs
    ) -> bool:
    
    if not is_thread_healthy(thread_key):
        thread_name = name or f"{thread_key}_thread"
        try:
            thread = SafeThread.spawn(
                target_fn=target_fn,
                *args,
                thread_name=thread_name,
                **kwargs,
            )
        except Exception as e:
            log_error(f"Failed to spawn {thread_key}: {e}")
            return False
    
        _thread_state[thread_key] = thread 
        log_info(f"Started thread: {thread_key}")
        return True
    else:
        log_debug(f"{thread_key} already running")
        return False

def shutdown_thread(thread_key: str, timeout: float = THREAD_TIMEOUT) -> None:
    thread = _thread_state.get(thread_key)
    if thread is None:
        return

    if thread.is_alive():
        try:
            thread.join(timeout=timeout)
            if thread.is_alive():
                log_warning(f"Force killing {thread_key}")
        except Exception as e:
            log_error(f"Error shutting down {thread_key}: {e}")

    _thread_state.pop(thread_key, None)

