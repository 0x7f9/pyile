from pyile.lib.runtime.internal.constants import RECORD_SIZE, MAX_RECORDS_DEFAULT, HEADER_SIZE, RECORD_VALID_FLAG
from pyile.lib.runtime.internal.dataclasses import Rec
from pyile.lib.utils.common import open_file_rw, create_memory_mapped_file, truncate_file, close_fd, ensure_file_dir_exists
from pyile.lib.runtime.internal.thread_safe import ThreadSafeSet, AtomicFlag
from pyile.lib.utils.logging import log_error
from pyile.lib.utils.lazy import LazyInit

import os
import mmap
import ctypes
import threading
from typing import Tuple

class AppCache(LazyInit):
    __slots__ = (
        "_path", "_size", "_m", "_fd", "_max_records",
        "_head", "_is_init", "_tail", "_index", "_dirty_flag", 
        "_write_lock", "_closed",
    )
    
    def __init__(self, path: str) -> None:
        self._path = path
        self._is_init = False
        self._closed = True

    def open(self) -> None:
        if self._is_init and not self._closed:
            return
        
        ensure_file_dir_exists(self._path)

        fd = open_file_rw(self._path)
        if fd is None:
            raise RuntimeError(f"Failed to open/create slab cache file: {self._path}")

        try:
            self._size = HEADER_SIZE + RECORD_SIZE * MAX_RECORDS_DEFAULT
            current_size = os.path.getsize(self._path)
            if current_size < self._size:
                if not truncate_file(fd, self._size):
                    raise RuntimeError(f"Failed to truncate slab cache file: {self._path}")
            
            map = create_memory_mapped_file(fd, self._size)
            if map is None:
                raise RuntimeError(f"Failed to create memory mapping for slab cache: {self._path}")

            self._fd = fd
            self._m: mmap.mmap = map
            self._max_records = MAX_RECORDS_DEFAULT
            
            need = ctypes.sizeof(ctypes.c_size_t) * 2
            if HEADER_SIZE < need:
                raise RuntimeError("HEADER_SIZE too small for expected header fields")
            
            try:
                self._head = ctypes.c_size_t.from_buffer(self._m, 0)
                self._tail = ctypes.c_size_t.from_buffer(self._m, ctypes.sizeof(ctypes.c_size_t))
            except (ValueError, BufferError) as e:
                self._m.close()
                raise RuntimeError(f"Invalid mapping or offset for header fields: {e}")
        
            self._index = ThreadSafeSet()
            self._dirty_flag = AtomicFlag(False)
            self._write_lock = threading.Lock()
            
            self._is_init = True
            self._closed = False

            self._rebuild_index_safe()
                
        except Exception:
            try:
                close_fd(fd)
            except Exception:
                pass
            raise
    
    def _record_offset(self, idx: int) -> int:
        physical = idx % self._max_records
        return HEADER_SIZE + physical * RECORD_SIZE
    
    def _read_record(self, idx: int) -> Tuple[int, int]:
        if not (0 <= idx < self._max_records):
            raise IndexError(f"Record index {idx} out of bounds [0, {self._max_records})")

        off = self._record_offset(idx)
        if off + ctypes.sizeof(Rec) > self._m.size():
            raise RuntimeError("Record read would be out of bounds")

        rec = Rec.from_buffer(self._m, off)
        return int(rec.hash_value), int(rec.flags)

    def _write_record(self, idx: int, h: int, f: int) -> None:
        if not (0 <= idx < self._max_records):
            raise IndexError(f"Record index {idx} out of bounds [0, {self._max_records})")

        off = self._record_offset(idx)
        if off + ctypes.sizeof(Rec) > self._m.size():
            raise RuntimeError("Record write would be out of bounds")

        rec = Rec.from_buffer(self._m, off)
        rec.hash_value = ctypes.c_uint64(h & 0xFFFFFFFFFFFFFFFF).value
        rec.flags = ctypes.c_uint64(f & 0xFFFFFFFFFFFFFFFF).value

    def _rebuild_index_safe(self) -> None:
        # this scans all possible records, regardless of current head/tail,
        # to ensure persistent recovery of the whole slab between runs.
        # if head/tail are corrupt, will still pull out valid records

        try:
            self._index.clear()
            for i in range(self._max_records):
                try:
                    h, f = self._read_record(i)
                except (IndexError, RuntimeError):
                    continue

                if f & RECORD_VALID_FLAG: 
                    self._index.add(h)
        
        except Exception as e:
            log_error(f"Failed to rebuild index {e}")
            self._index.clear()

    def get_len(self) -> int:
        return len(self._index)

    def has_entry(self, cache_key_hash: int) -> bool:
        return cache_key_hash in self._index

    def append_entry(self, cache_key_hash: int, flags: int = 0) -> None:
        if self._closed:
            raise RuntimeError("Cannot append after slab is closed")

        if cache_key_hash < 0:
            raise ValueError("cache_key_hash must be non-negative")

        with self._write_lock:
            if self._head is None or self._tail is None:
                raise
    
            if cache_key_hash in self._index:
                return

            idx = self._tail.value % self._max_records
            valid_flags = flags | RECORD_VALID_FLAG
            self._write_record(idx, cache_key_hash & 0xFFFFFFFFFFFFFFFF, valid_flags)

            self._tail.value = (self._tail.value + 1)
            if (self._tail.value - self._head.value) > self._max_records:
                self._head.value = (self._head.value + 1)

            self._index.add(cache_key_hash)
            self._dirty_flag.set(True)

    def flush(self) -> None:
        if self._closed:
            return
        
        with self._write_lock:
            if not self._dirty_flag.get():
                return  
            
            try:
                self._m.flush()
                self._dirty_flag.clear()
            except Exception as e:
                log_error(f"Failed to flush slab cache {e}")

    def close(self) -> None:
        if self._closed:
            return
        try:
            try:
                if self._dirty_flag.get():
                    self._m.flush()
            except Exception:
                pass

            try:
                del self._head
                del self._tail
            except Exception:
                pass

            try:
                self._m.close()
            except Exception:
                pass

            try:
                if self._fd is not None:
                    close_fd(self._fd)
            except Exception:
                pass

            self._closed = True
            self._is_init = False

        except Exception as e:
            log_error(f"Failed to close slab cache: {e}")

