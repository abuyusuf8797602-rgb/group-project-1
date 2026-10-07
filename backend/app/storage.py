"""Private on-disk storage for uploaded documents.

Files live on a Docker volume mounted at STORAGE_DIR and are only reachable
through the API (by signing token) - there is no public URL.
"""

import os
from pathlib import Path

STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/data/documents"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))


def path_for(token: str) -> Path:
    return STORAGE_DIR / token


def save(token: str, data: bytes) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path_for(token).write_bytes(data)


def read(token: str) -> bytes:
    return path_for(token).read_bytes()
