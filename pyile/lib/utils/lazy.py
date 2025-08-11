import threading
from typing import TypeVar, Type

T = TypeVar("T", bound="LazyInit")

class LazyInit:
    __slots__ = ()
    _s_lock = threading.Lock()

    @classmethod
    def get(cls: Type[T], *args, **kwargs) -> T:
        if "_singleton_instance" not in cls.__dict__:
            with cls._s_lock:
                if "_singleton_instance" not in cls.__dict__:
                    cls._singleton_instance = cls(*args, **kwargs)
        return cls._singleton_instance  # type: ignore
