"""Unit tests for FilegetterBuilder and helpers in filegetter.cmds.project."""

import csv
import hashlib
import os
from zipfile import ZipFile

import pytest
import responses

from filegetter.cmds.project import (
    ConfigError,
    FilegetterBuilder,
    build_url,
    load_csv_data,
    load_file_list,
    load_processed_files_list,
    parse_content_disposition,
)


def read_processed(project):
    path = project / "storage" / "processed.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestHelperFunctions:
    def test_load_file_list(self, temp_project_dir):
        path = temp_project_dir / "files.txt"
        path.write_text("line1\nline2\nline3\n")
        assert load_file_list(str(path)) == ["line1", "line2", "line3"]

    def test_load_file_list_empty(self, temp_project_dir):
        path = temp_project_dir / "empty.txt"
        path.write_text("")
        assert load_file_list(str(path)) == []

    def test_load_csv_data(self, temp_project_dir):
        path = temp_project_dir / "data.csv"
        path.write_text("id;name\n1;item1\n2;item2\n")
        result = load_csv_data(str(path), "id", delimiter=";")
        assert result["1"]["name"] == "item1"
        assert result["2"]["name"] == "item2"

    def test_load_csv_data_missing_column(self, temp_project_dir):
        path = temp_project_dir / "data.csv"
        path.write_text("id,name\n1,item1\n")
        with pytest.raises(ValueError):
            load_csv_data(str(path), "missing")

    def test_load_processed_files_list(self, temp_project_dir):
        path = temp_project_dir / "processed.csv"
        path.write_text("url,filename\nhttp://a/f1,f1.pdf\n")
        result = load_processed_files_list(str(path))
        assert result["http://a/f1"]["filename"] == "f1.pdf"

    def test_parse_content_disposition_simple(self):
        value = 'attachment; filename="report.pdf"'
        assert parse_content_disposition(value) == "report.pdf"

    def test_parse_content_disposition_unquoted(self):
        value = "attachment; filename=report.pdf"
        assert parse_content_disposition(value) == "report.pdf"

    def test_parse_content_disposition_rfc5987(self):
        value = "attachment; filename*=UTF-8''%D0%BE%D1%82%D1%87%D0%B5%D1%82.pdf"
        assert parse_content_disposition(value) == "отчет.pdf"

    def test_parse_content_disposition_none(self):
        assert parse_content_disposition("attachment") is None

    def test_build_url_prefix(self):
        assert build_url("https://example.com", "/f.pdf", "prefix") == "https://example.com/f.pdf"

    def test_build_url_prefix_no_double_slash(self):
        assert build_url("https://example.com/", "/f.pdf", "prefix") == "https://example.com/f.pdf"

    def test_build_url_prefix_absolute_id(self):
        assert (
            build_url("https://example.com", "http://other/f.pdf", "prefix") == "http://other/f.pdf"
        )

    def test_build_url_prefix_empty_root(self):
        assert build_url("", "http://other/f.pdf", "prefix") == "http://other/f.pdf"

    def test_build_url_pattern(self):
        assert (
            build_url("https://example.com/files/{}.pdf", "42", "pattern")
            == "https://example.com/files/42.pdf"
        )


class TestConfigParsing:
    def test_defaults(self, project_with_config):
        b = FilegetterBuilder(str(project_with_config))
        assert b.name == "test_project"
        assert b.source_type == "csv"
        assert b.delimiter == ","
        assert b.data_key == "url"
        assert b.fetch_mode == "prefix"
        assert b.root_url == "https://example.com/"
        assert b.files_keys == ["url"]
        assert b.storage_mode == "filepath"
        assert b.file_storage_type == "zip"
        assert b.transfer_ext is False
        assert b.compression is True
        assert b.verify_ssl is True
        assert b.workers == 1
        assert b.timeout == 30.0
        assert b.retries == 2

    def test_source_resolved_relative_to_project(self, make_project):
        project = make_project(files={"data.csv": "url\n/f1.pdf\n"})
        b = FilegetterBuilder(str(project))
        assert b.source == str(project / "data.csv")
        assert b.storagedir == str(project / "storage")

    def test_custom_delimiter_semicolon(self, make_project):
        project = make_project(
            **{"project.delimiter": ";"},
            files={"data.csv": "url;x\n/f1.pdf;a\n"},
        )
        b = FilegetterBuilder(str(project))
        assert b.delimiter == ";"

    def test_delimiter_tab(self, make_project):
        project = make_project(
            **{"project.delimiter": "tab"},
            files={"data.csv": "url\tx\n/f1.pdf\ta\n"},
        )
        b = FilegetterBuilder(str(project))
        assert b.delimiter == "\t"

    def test_missing_config_raises(self, temp_project_dir):
        with pytest.raises(ConfigError, match="not found"):
            FilegetterBuilder(str(temp_project_dir))

    @pytest.mark.parametrize(
        "overrides,pattern",
        [
            ({"project.name": None}, r"\[project\] name"),
            ({"project.source": None}, r"\[project\] source"),
            ({"project.source_type": "xml"}, r"source_type"),
            ({"data.data_key": None}, r"data_key"),
            ({"files.keys": None}, r"\[files\] keys"),
            ({"files.fetch_mode": "magic"}, r"fetch_mode"),
            ({"files.root_url": None}, r"root_url"),
            ({"files.storage_mode": "magic"}, r"storage_mode"),
            ({"files.file_storage_type": "db"}, r"file_storage_type"),
            (
                {"files.fetch_mode": "pattern", "files.root_url": "https://example.com/id"},
                r"placeholder",
            ),
            ({"files.workers": 0}, r"workers"),
            ({"files.retries": -1}, r"retries"),
            ({"files.verify_ssl": "maybe"}, r"verify_ssl"),
        ],
    )
    def test_invalid_config_raises(self, make_project, overrides, pattern):
        project = make_project(**overrides, files={"data.csv": "url\n/f1.pdf\n"})
        with pytest.raises(ConfigError, match=pattern):
            FilegetterBuilder(str(project))

    def test_legacy_storage_type_used_as_file_storage(self, make_project):
        project = make_project(
            **{"files.file_storage_type": None, "storage.storage_type": "filesystem"},
            files={"data.csv": "url\n/f1.pdf\n"},
        )
        b = FilegetterBuilder(str(project))
        assert b.file_storage_type == "filesystem"

    def test_default_project_path_is_cwd(self, make_project, monkeypatch):
        project = make_project(files={"data.csv": "url\n/f1.pdf\n"})
        monkeypatch.chdir(project)
        b = FilegetterBuilder(None)
        assert b.project_path == os.getcwd()


class TestRunWithCsvSource:
    @responses.activate
    def test_successful_download(self, project_with_config):
        responses.add(
            responses.GET,
            "https://example.com/file1.pdf",
            body=b"PDF content 1",
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/file2.pdf",
            body=b"PDF content 2",
            content_type="application/pdf",
        )

        stats = FilegetterBuilder(str(project_with_config)).run()

        assert stats == {"total": 2, "skipped": 0, "downloaded": 2, "failed": 0}
        with ZipFile(str(project_with_config / "storage" / "files.zip")) as zf:
            assert sorted(zf.namelist()) == ["file1.pdf", "file2.pdf"]
            assert zf.read("file1.pdf") == b"PDF content 1"

        rows = read_processed(project_with_config)
        assert len(rows) == 2
        row = rows[0]
        assert row["status"] == "200"
        assert row["mime"] == "application/pdf"
        assert row["filesize"] == str(len(b"PDF content 1"))
        assert row["sha256"] == hashlib.sha256(b"PDF content 1").hexdigest()

    @responses.activate
    def test_http_error_not_stored(self, project_with_config):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"ok")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"Not Found", status=404)

        stats = FilegetterBuilder(str(project_with_config)).run()

        assert stats["downloaded"] == 1
        assert stats["failed"] == 1
        with ZipFile(str(project_with_config / "storage" / "files.zip")) as zf:
            assert zf.namelist() == ["file1.pdf"]

        rows = read_processed(project_with_config)
        statuses = {r["url"]: r["status"] for r in rows}
        assert statuses["https://example.com/file2.pdf"] == "404"

    @responses.activate
    def test_connection_error_does_not_abort_run(self, project_with_config):
        # only one of two URLs is mocked; the other raises ConnectionError
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"ok")

        stats = FilegetterBuilder(str(project_with_config)).run()

        assert stats["downloaded"] == 1
        assert stats["failed"] == 1
        rows = read_processed(project_with_config)
        statuses = {r["url"]: r["status"] for r in rows}
        assert statuses["https://example.com/file2.pdf"] == "error"

    @responses.activate
    def test_resume_skips_processed_files(self, project_with_config):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"two")

        builder = FilegetterBuilder(str(project_with_config))
        first = builder.run()
        second = builder.run()

        assert first["downloaded"] == 2
        assert second == {"total": 2, "skipped": 2, "downloaded": 0, "failed": 0}
        # no duplicate rows after the second run
        assert len(read_processed(project_with_config)) == 2

    @responses.activate
    def test_failed_files_are_retried(self, project_with_config):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"Not Found", status=404)

        builder = FilegetterBuilder(str(project_with_config))
        builder.run()

        responses.replace(responses.GET, "https://example.com/file2.pdf", body=b"two")
        second = builder.run()

        assert second["downloaded"] == 1
        assert second["failed"] == 0

    @responses.activate
    def test_legacy_processed_csv_upgraded(self, project_with_config):
        storage = project_with_config / "storage"
        storage.mkdir()
        (storage / "processed.csv").write_text(
            "url,filename,mime,ext,disp_name,filesize\n"
            "https://example.com/file1.pdf,file1.pdf,application/pdf,,,\n"
        )

        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"two")
        stats = FilegetterBuilder(str(project_with_config)).run()

        assert stats["skipped"] == 1  # legacy row without status counts as done
        assert stats["downloaded"] == 1
        rows = read_processed(project_with_config)
        assert rows[0]["filename"] == "file1.pdf"
        assert rows[0]["status"] == ""
        assert rows[1]["url"] == "https://example.com/file2.pdf"


class TestRunOptions:
    @responses.activate
    def test_dry_run_touches_nothing(self, project_with_config):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"two")

        stats = FilegetterBuilder(str(project_with_config)).run(dry_run=True)

        assert stats == {"total": 2, "skipped": 0, "pending": 2}
        assert not (project_with_config / "storage").exists()
        assert len(responses.calls) == 0

    @responses.activate
    def test_limit(self, project_with_config):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"two")

        stats = FilegetterBuilder(str(project_with_config)).run(limit=1)

        assert stats["downloaded"] == 1
        assert stats["skipped"] == 0
        assert len(responses.calls) == 1

    @responses.activate
    def test_refresh_rereads_source(self, project_with_config):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"two")

        builder = FilegetterBuilder(str(project_with_config))
        builder.run()
        # source changes between runs
        (project_with_config / "data.csv").write_text("url,title\n/file1.pdf,A\n/file3.pdf,C\n")
        responses.add(responses.GET, "https://example.com/file3.pdf", body=b"three")

        stats = builder.run(refresh=True)

        assert stats["total"] == 2  # file1 + file3 (file2 gone from source)
        assert stats["skipped"] == 1
        assert stats["downloaded"] == 1


class TestExtensions:
    @responses.activate
    def test_extension_added_when_missing(self, make_project):
        responses.add(
            responses.GET,
            "https://example.com/images/327671",
            body=b"jpegdata",
            content_type="image/jpeg",
            headers={"content-disposition": 'attachment; filename="photo.jpg"'},
        )
        project = make_project(
            **{"files.transfer_ext": "True"}, files={"data.csv": "url\n/images/327671\n"}
        )
        FilegetterBuilder(str(project)).run()

        rows = read_processed(project)
        assert rows[0]["filename"] == "images/327671.jpg"
        assert rows[0]["ext"] == "jpg"

    @responses.activate
    def test_extension_not_duplicated(self, make_project):
        responses.add(
            responses.GET,
            "https://example.com/file1.pdf",
            body=b"pdf",
            content_type="application/pdf",
            headers={"content-disposition": 'attachment; filename="doc.pdf"'},
        )
        project = make_project(
            **{"files.transfer_ext": "True"}, files={"data.csv": "url\n/file1.pdf\n"}
        )
        FilegetterBuilder(str(project)).run()

        rows = read_processed(project)
        assert rows[0]["filename"] == "file1.pdf"

    @responses.activate
    def test_default_ext_fallback(self, make_project):
        responses.add(responses.GET, "https://example.com/images/327671", body=b"jpegdata")
        project = make_project(
            **{"files.transfer_ext": "True", "files.default_ext": "jpg"},
            files={"data.csv": "url\n/images/327671\n"},
        )
        FilegetterBuilder(str(project)).run()

        rows = read_processed(project)
        assert rows[0]["filename"] == "images/327671.jpg"

    @responses.activate
    def test_default_ext_without_transfer(self, make_project):
        responses.add(responses.GET, "https://example.com/images/327671", body=b"jpegdata")
        project = make_project(
            **{"files.default_ext": "jpg"}, files={"data.csv": "url\n/images/327671\n"}
        )
        FilegetterBuilder(str(project)).run()

        rows = read_processed(project)
        assert rows[0]["filename"] == "images/327671.jpg"


class TestRunWithJsonlSource:
    @responses.activate
    def test_nested_keys_extracted(self, make_project):
        responses.add(responses.GET, "https://example.com/doc1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/doc2.pdf", body=b"two")
        project = make_project(
            **{
                "project.source": "data.jsonl",
                "project.source_type": "jsonl",
                "data.data_key": "files",
                "files.keys": "url",
            },
            files={
                "data.jsonl": '{"id": 1, "files": [{"url": "/doc1.pdf"}, {"url": "/doc2.pdf"}]}\n'
                '{"id": 2, "files": []}\n'
            },
        )

        stats = FilegetterBuilder(str(project)).run()

        assert stats["downloaded"] == 2
        assert stats["failed"] == 0
        # The raw data_key value must not leak into the URL list
        requested = {call.request.url for call in responses.calls}
        assert requested == {"https://example.com/doc1.pdf", "https://example.com/doc2.pdf"}

    @responses.activate
    def test_dotted_data_key(self, make_project):
        responses.add(responses.GET, "https://example.com/327671", body=b"img")
        project = make_project(
            **{
                "project.source": "data.jsonl",
                "project.source_type": "jsonl",
                "data.data_key": "items",
                "files.keys": "images.url",
            },
            files={"data.jsonl": '{"items": [{"images": {"url": "/327671"}}]}\n'},
        )

        stats = FilegetterBuilder(str(project)).run()
        assert stats["downloaded"] == 1

    @responses.activate
    def test_malformed_line_skipped(self, make_project):
        responses.add(responses.GET, "https://example.com/doc1.pdf", body=b"one")
        project = make_project(
            **{
                "project.source": "data.jsonl",
                "project.source_type": "jsonl",
                "data.data_key": "files",
                "files.keys": "url",
            },
            files={"data.jsonl": '{"files": [{"url": "/doc1.pdf"}]}\n' "this is not json\n"},
        )

        stats = FilegetterBuilder(str(project)).run()
        assert stats == {"total": 1, "skipped": 0, "downloaded": 1, "failed": 0}


class TestRunWithListSource:
    @responses.activate
    def test_absolute_urls(self, make_project):
        responses.add(responses.GET, "https://other.example/f1.pdf", body=b"one")
        project = make_project(
            **{"project.source": "files.txt", "project.source_type": "list", "files.root_url": ""},
            files={"files.txt": "https://other.example/f1.pdf\n"},
        )

        stats = FilegetterBuilder(str(project)).run()
        assert stats["downloaded"] == 1
        rows = read_processed(project)
        assert rows[0]["filename"] == "f1.pdf"


class TestPatternMode:
    @responses.activate
    def test_pattern_url(self, make_project):
        responses.add(responses.GET, "https://example.com/files/42.pdf", body=b"pdf")
        project = make_project(
            **{"files.fetch_mode": "pattern", "files.root_url": "https://example.com/files/{}.pdf"},
            files={"data.csv": "url\n42\n"},
        )

        stats = FilegetterBuilder(str(project)).run()
        assert stats["downloaded"] == 1


class TestFilesystemStorageMode:
    @responses.activate
    def test_files_stored_under_storage(self, make_project):
        responses.add(responses.GET, "https://example.com/docs/a/f1.pdf", body=b"one")
        project = make_project(
            **{"files.file_storage_type": "filesystem"}, files={"data.csv": "url\n/docs/a/f1.pdf\n"}
        )

        FilegetterBuilder(str(project)).run()

        stored = project / "storage" / "files" / "docs" / "a" / "f1.pdf"
        assert stored.read_bytes() == b"one"


class TestWorkers:
    @responses.activate
    def test_parallel_download(self, make_project):
        for name in ("file1.pdf", "file2.pdf"):
            responses.add(
                responses.GET, "https://example.com/%s" % name, body=("data-%s" % name).encode()
            )

        project = make_project(
            **{"files.workers": 2}, files={"data.csv": "url\n/file1.pdf\n/file2.pdf\n"}
        )
        stats = FilegetterBuilder(str(project)).run()

        assert stats["downloaded"] == 2
        with ZipFile(str(project / "storage" / "files.zip")) as zf:
            assert sorted(zf.namelist()) == ["file1.pdf", "file2.pdf"]


class TestSizeLimit:
    @responses.activate
    def test_oversize_file_rejected(self, make_project):
        responses.add(responses.GET, "https://example.com/big.bin", body=b"x" * 100)
        project = make_project(**{"files.max_filesize": 10}, files={"data.csv": "url\n/big.bin\n"})

        stats = FilegetterBuilder(str(project)).run()

        assert stats["failed"] == 1
        assert stats["downloaded"] == 0
        with ZipFile(str(project / "storage" / "files.zip")) as zf:
            assert zf.namelist() == []
