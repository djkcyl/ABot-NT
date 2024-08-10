import hashlib


def data_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()  # noqa: S324
