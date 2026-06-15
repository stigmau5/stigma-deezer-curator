from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """
    Write text by replacing the target with a fully flushed temp file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding=encoding,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())

        os.replace(tmp_name, path)
        tmp_name = None

        if hasattr(os, "O_DIRECTORY"):
            dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
