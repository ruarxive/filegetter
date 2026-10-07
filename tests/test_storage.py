"""Unit tests for storage classes in filegetter.storage."""

import os
from zipfile import ZipFile

import pytest

from filegetter.storage import FileStorage, FilesystemStorage, ZipFileStorage


class TestFileStorageBase:
    def test_exists_not_implemented(self):
        with pytest.raises(NotImplementedError):
            FileStorage().exists("test.txt")

    def test_store_not_implemented(self):
        with pytest.raises(NotImplementedError):
            FileStorage().store("test.txt", b"content")

    def test_close_is_noop(self):
        FileStorage().close()


class TestZipFileStorage:
    def test_creates_zip(self, temp_project_dir):
        zip_path = temp_project_dir / "test.zip"
        storage = ZipFileStorage(str(zip_path), mode="w")
        storage.close()
        assert zip_path.exists()

    def test_store_and_read_back(self, temp_project_dir):
        zip_path = temp_project_dir / "test.zip"
        storage = ZipFileStorage(str(zip_path), mode="w")
        storage.store("dir/test.txt", b"Hello, World!")
        storage.close()

        with ZipFile(str(zip_path)) as zf:
            assert zf.read("dir/test.txt") == b"Hello, World!"

    def test_exists(self, temp_project_dir):
        zip_path = temp_project_dir / "test.zip"
        storage = ZipFileStorage(str(zip_path), mode="w")
        storage.store("test.txt", b"x")
        assert storage.exists("test.txt")
        assert not storage.exists("other.txt")
        storage.close()

    def test_exists_after_reopen(self, temp_project_dir):
        zip_path = temp_project_dir / "test.zip"
        storage = ZipFileStorage(str(zip_path), mode="w")
        storage.store("test.txt", b"x")
        storage.close()

        reopened = ZipFileStorage(str(zip_path), mode="a")
        assert reopened.exists("test.txt")
        reopened.close()

    def test_leading_slash_sanitized(self, temp_project_dir):
        zip_path = temp_project_dir / "test.zip"
        storage = ZipFileStorage(str(zip_path), mode="w")
        storage.store("/abs/path.txt", b"x")
        storage.close()

        with ZipFile(str(zip_path)) as zf:
            assert zf.namelist() == ["abs/path.txt"]

    def test_creates_parent_directory(self, temp_project_dir):
        zip_path = temp_project_dir / "nested" / "dir" / "test.zip"
        storage = ZipFileStorage(str(zip_path), mode="w")
        storage.close()
        assert zip_path.exists()


class TestFilesystemStorage:
    def test_store_creates_file(self, temp_project_dir):
        dirpath = temp_project_dir / "files"
        storage = FilesystemStorage(str(dirpath))
        storage.store("test.txt", b"content")
        assert (dirpath / "test.txt").read_bytes() == b"content"

    def test_store_nested_path(self, temp_project_dir):
        dirpath = temp_project_dir / "files"
        storage = FilesystemStorage(str(dirpath))
        storage.store("a/b/c.txt", b"content")
        assert (dirpath / "a" / "b" / "c.txt").read_bytes() == b"content"

    def test_absolute_path_cannot_escape_root(self, temp_project_dir):
        dirpath = temp_project_dir / "files"
        storage = FilesystemStorage(str(dirpath))
        storage.store("/fg-escape-test/pwned.txt", b"content")
        assert not os.path.exists("/fg-escape-test")
        assert (dirpath / "fg-escape-test/pwned.txt").exists()

    def test_exists(self, temp_project_dir):
        dirpath = temp_project_dir / "files"
        storage = FilesystemStorage(str(dirpath))
        storage.store("test.txt", b"content")
        assert storage.exists("test.txt")
        assert not storage.exists("missing.txt")

    def test_creates_directory(self, temp_project_dir):
        dirpath = temp_project_dir / "deep" / "nested" / "files"
        FilesystemStorage(str(dirpath))
        assert dirpath.is_dir()
