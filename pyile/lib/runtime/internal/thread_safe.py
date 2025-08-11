from pyile.lib.runtime.internal.constants import MAX_CACHE_SIZE, CACHE_TTL

import threading
import time
from typing import Any, Optional, Iterator, List, Callable
from collections import deque, OrderedDict

class SafeThread(threading.Thread):
    __slots__ = ('_fn', '_args', '_kwargs')

    def __init__(
        self, 
        target_fn: Optional[Callable] = None, 
        name: Optional[str] = None, 
        args: tuple = (), 
        kwargs: Optional[dict] = None, 
        **thread_kwargs
    ) -> None:
        super().__init__(name=name, daemon=True, **thread_kwargs)
        self._fn = target_fn
        self._args = args
        self._kwargs = kwargs or {}

    def run(self) -> None:
        try:
            if self._fn:
                self._fn(*self._args, **self._kwargs)
        except Exception as e:
            fn_name = getattr(self._fn, "__name__", "unknown_function") if self._fn else "unknown_function"
            from pyile.lib.utils.logging import log_error
            log_error(f"Thread error in {fn_name}: {e}", exc_info=True)
    
    @classmethod
    def spawn(cls, target_fn: Callable, *args, thread_name: Optional[str] = None, **kwargs) -> "SafeThread":
        thread = cls(target_fn=target_fn, name=thread_name, args=args, kwargs=kwargs)
        thread.start()
        return thread


class AtomicCounter:
    __slots__ = ('_value', '_lock')
    
    def __init__(self, initial_value: int = 0):
        self._value = initial_value
        self._lock = threading.Lock()
    
    def __int__(self) -> int:
        with self._lock:
            return self._value
    
    def __iadd__(self, other: int) -> "AtomicCounter":
        with self._lock:
            self._value += other
            return self
    
    def __isub__(self, other: int) -> "AtomicCounter":
        with self._lock:
            self._value -= other
            return self
    
    def reset(self, value: int = 0) -> None:
        with self._lock:
            self._value = value


class AtomicFlag(AtomicCounter):
    def __init__(self, initial: bool = False):
        super().__init__(1 if initial else 0)

    def __bool__(self):
        return self.get()

    def get(self) -> bool:
        with self._lock:
            return bool(self._value)

    def set(self, value: bool = True) -> None:
        with self._lock:
            self._value = 1 if value else 0

    def clear(self) -> None:
        self.set(False)


class ThreadSafeDict:
    __slots__ = ('_dict', '_lock')
    
    def __init__(self):
        self._dict = {}
        self._lock = threading.Lock()
    
    def __getitem__(self, key: Any) -> Any:
        with self._lock:
            return self._dict[key]
    
    def __delitem__(self, key: Any) -> None:
        with self._lock:
            del self._dict[key]
    
    def __setitem__(self, key: Any, value: Any) -> None:
        with self._lock:
            self._dict[key] = value
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._dict)
    
    def __iter__(self):
        with self._lock:
            keys = list(self._dict.keys())
        return iter(keys)
    
    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._dict
    
    def pop(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            return self._dict.pop(key, default)

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            return self._dict.get(key, default)
    
    def increment(self, key: Any, amount: int = 1) -> int:
        with self._lock:
            current = self._dict.get(key, 0)
            new_value = current + amount
            self._dict[key] = new_value
            return new_value
    
    def get_or_set(self, key: Any, default_value: Any) -> Any:
        with self._lock:
            if key not in self._dict:
                self._dict[key] = default_value
            return self._dict[key]
    
    def clear(self) -> None:
        with self._lock:
            self._dict.clear()
    
    def items(self):
        with self._lock:
            return list(self._dict.items())

    def keys(self):
        with self._lock:
            return list(self._dict.keys())

    def values(self):
        with self._lock:
            return list(self._dict.values())


class TTLCache:
    __slots__ = (
        '_cache', '_timestamps', '_maxsize', '_ttl', 
        '_lock', '_ttls', '_last_cleanup', '_cleanup_interval'
    )
    
    def __init__(self, maxsize: int = MAX_CACHE_SIZE, ttl: float = CACHE_TTL):
        self._cache = {}
        self._timestamps = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.Lock()
        self._ttls = {}
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 1.0  

    def __setitem__(self, key: Any, value: Any) -> None:
        self.put(key, value)

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            self._maybe_cleanup()
            try:
                return self._cache[key]
            except KeyError:
                return default

    def put(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._maybe_cleanup()
            if len(self._cache) >= self._maxsize:
                oldest_key = next(iter(self._timestamps))
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
                del self._ttls[oldest_key]
            self._cache[key] = value
            now = time.monotonic()
            self._timestamps[key] = now
            self._timestamps.move_to_end(key)
            if ttl is not None:
                self._ttls[key] = ttl
            else:
                self._ttls[key] = None 

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if (now - self._last_cleanup) > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired_keys = []
        for key, timestamp in self._timestamps.items():
            ttl = self._ttls.get(key)
            if ttl is None:
                continue
            if (now - timestamp) > ttl:
                expired_keys.append(key)
        for key in expired_keys:
            del self._cache[key]
            del self._timestamps[key]
            del self._ttls[key]


class RingBuffer:
    __slots__ = ('max_size', '_buffer', '_sum', '_lock')
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._buffer = deque(maxlen=None)
        self._sum = 0.0
        self._lock = threading.RLock()
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
    
    def __iter__(self) -> Iterator[Any]:
        with self._lock:
            buf = list(self._buffer)
        return iter(buf)
    
    def append(self, item: Any) -> None:
        with self._lock:
            if len(self._buffer) == self.max_size:
                evicted = self._buffer.popleft()
                self._sum -= evicted
            self._buffer.append(item)
            self._sum += item
    
    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._sum = 0.0
    
    def snapshot(self) -> List[Any]:
        with self._lock:
            return list(self._buffer)
    

class ThreadSafeList:
    __slots__ = ('_lock', '_list')
    
    def __init__(self, initial=None, max_size: Optional[int] = None):
        self._lock = threading.RLock()
        if max_size is not None:
            self._list = RingBuffer(max_size)
        else:
            self._list = []
    
    def __iter__(self):
        with self._lock:
            if isinstance(self._list, RingBuffer):
                buf = list(self._list._buffer)
            else:
                buf = self._list.copy()
        return iter(buf)
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._list)

    def append(self, item: Any) -> None:
        with self._lock:
            self._list.append(item)
    
    def clear(self) -> None:
        with self._lock:
            self._list.clear()
    
    def bounded_append(self, item: Any, max_size: int) -> None:
        with self._lock:
            if isinstance(self._list, RingBuffer):
                self._list.append(item)
            else:
                self._list.append(item)
                while len(self._list) > max_size:
                    self._list.pop(0)


class ThreadSafeSet:
    __slots__ = ('_set', '_lock')
    
    def __init__(self, iterable=None):
        self._set = set(iterable) if iterable else set()
        self._lock = threading.Lock()
    
    def __len__(self) -> int:
        with self._lock:
            return len(self._set)
    
    def __contains__(self, item: Any) -> bool:
        with self._lock:
            return item in self._set
    
    def __iter__(self):
        with self._lock:
            items = tuple(self._set)
        return iter(items)

    def add(self, item: Any) -> None:
        with self._lock:
            self._set.add(item)
    
    def clear(self) -> None:
        with self._lock:
            self._set.clear()

        