import xxhash # type: ignore
from typing import Union

class HashManager:

    @staticmethod
    def xxh3_64(data: Union[str, bytes]) -> int:
        if isinstance(data, str):
            data = data.encode("utf-8")
        return xxhash.xxh3_64(data).intdigest()

    # @staticmethod
    # def hash_path_and_contents(path: str, contents: bytes) -> int:
    #     h = xxhash.xxh3_64()
    #     h.update(path.encode("utf-8"))
    #     h.update(b"\0")
    #     h.update(contents)
    #     return h.intdigest()

    @staticmethod
    def hash_contents(contents: bytes) -> int:
        h = xxhash.xxh3_64()
        h.update(contents)
        return h.intdigest()

    # @staticmethod
    # def fnv1a(data: Union[str, bytes, int]) -> int:
    #     if not isinstance(data, bytes):
    #         data = str(data).encode("utf-8")

    #     hash_value = 0x811c9dc5
    #     for byte in data:
    #         hash_value ^= byte
    #         hash_value = (hash_value * 0x01000193) & 0xffffffffffffffff
    #     return hash_value

