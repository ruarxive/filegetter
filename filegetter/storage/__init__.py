"""Storage backends for downloaded files."""

import os
from typing import Literal, Set
from zipfile import ZIP_DEFLATED, ZipFile

from ..common import sanitize_filename


class FileStorage:
    """Base file storage class."""

    def exists(self, name: str) -> bool:
        """Check if a file exists in storage."""
        raise NotImplementedError

    def store(self, filename: str, content: bytes) -> None:
        """Store file content under the given filename."""
        raise NotImplementedError

    def close(self) -> None:
        """Release resources held by the storage."""


class ZipFileStorage(FileStorage):
    """Store files as entries of a ZIP archive."""

    def __init__(
        self,
        filename: str,
        mode: Literal["r", "w", "x", "a"] = "a",
        compression: int = ZIP_DEFLATED,
    ) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        self.mzip: ZipFile = ZipFile(filename, mode=mode, compression=compression)
        self.allfiles: Set[str] = set(self.mzip.namelist())

    def store(self, filename: str, content: bytes) -> None:
        name = sanitize_filename(filename)
        self.mzip.writestr(name, content)
        self.allfiles.add(name)

    def exists(self, filename: str) -> bool:
        return sanitize_filename(filename) in self.allfiles

    def close(self) -> None:
        self.mzip.close()


class FilesystemStorage(FileStorage):
    """Store files in a directory tree."""

    def __init__(self, dirpath: str) -> None:
        self.dirpath: str = dirpath
        os.makedirs(self.dirpath, exist_ok=True)

    def _fullpath(self, filename: str) -> str:
        # sanitize_filename guarantees a relative path, so the join can
        # never escape dirpath.
        return os.path.join(self.dirpath, sanitize_filename(filename))

    def exists(self, filename: str) -> bool:
        return os.path.exists(self._fullpath(filename))

    def store(self, filename: str, content: bytes) -> None:
        fullname = self._fullpath(filename)
        os.makedirs(os.path.dirname(fullname), exist_ok=True)
        with open(fullname, "wb") as f:
            f.write(content)
