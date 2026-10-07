"""Tests for optional WARC output (requires the filegetter[warc] extra)."""

import pytest
import responses
from warcio.archiveiterator import ArchiveIterator

from filegetter.cmds.project import ConfigError, FilegetterBuilder

warcio = pytest.importorskip("warcio")


def read_warc(path):
    """Read a WARC file into plain dicts (streams are only valid while iterating)."""
    records = []
    with open(str(path), "rb") as f:
        for record in ArchiveIterator(f):
            info = {
                "type": record.rec_type,
                "target": record.rec_headers.get("WARC-Target-URI"),
                "status": None,
                "content_type": None,
                "payload": None,
            }
            if record.http_headers is not None:
                info["status"] = record.http_headers.get_statuscode()
                info["content_type"] = record.http_headers.get_header("Content-Type")
                info["payload"] = record.raw_stream.read()
            records.append(info)
    return records


class TestWARCOutput:
    @responses.activate
    def test_successful_download_written_to_warc(self, make_project):
        responses.add(
            responses.GET,
            "https://example.com/file1.pdf",
            body=b"PDF content",
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/file2.pdf",
            body=b"PDF content 2",
            content_type="application/pdf",
        )
        project = make_project(
            **{"storage.write_warc": "True"},
            files={"data.csv": "url\n/file1.pdf\n/file2.pdf\n"},
        )

        FilegetterBuilder(str(project)).run()

        warc_path = project / "storage" / "files.warc.gz"
        assert warc_path.exists()

        records = read_warc(warc_path)
        assert [r["type"] for r in records] == ["warcinfo", "response", "response"]
        assert [r["target"] for r in records[1:]] == [
            "https://example.com/file1.pdf",
            "https://example.com/file2.pdf",
        ]

        first = records[1]
        assert first["status"] == "200"
        assert first["content_type"] == "application/pdf"
        assert first["payload"] == b"PDF content"

    @responses.activate
    def test_failures_not_written_to_warc(self, make_project):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"ok")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"nope", status=404)
        project = make_project(
            **{"storage.write_warc": "True"},
            files={"data.csv": "url\n/file1.pdf\n/file2.pdf\n"},
        )

        FilegetterBuilder(str(project)).run()

        records = read_warc(project / "storage" / "files.warc.gz")
        targets = [r["target"] for r in records[1:]]
        assert "https://example.com/file2.pdf" not in targets

    @responses.activate
    def test_second_run_appends_no_duplicates(self, make_project):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        project = make_project(
            **{"storage.write_warc": "True"},
            files={"data.csv": "url\n/file1.pdf\n"},
        )

        builder = FilegetterBuilder(str(project))
        builder.run()
        builder.run()

        records = read_warc(project / "storage" / "files.warc.gz")
        # one warcinfo + exactly one response (second run skipped the file)
        assert [r["type"] for r in records] == ["warcinfo", "response"]

    @responses.activate
    def test_no_warc_by_default(self, make_project):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        project = make_project(files={"data.csv": "url\n/file1.pdf\n"})

        FilegetterBuilder(str(project)).run()

        assert not (project / "storage" / "files.warc.gz").exists()

    def test_write_warc_without_warcio_is_config_error(self, make_project, monkeypatch):
        import filegetter.cmds.project as project_module

        monkeypatch.setattr(project_module, "WARCWriter", None)
        project = make_project(
            **{"storage.write_warc": "True"},
            files={"data.csv": "url\n/file1.pdf\n"},
        )

        with pytest.raises(ConfigError, match=r"filegetter\[warc\]"):
            FilegetterBuilder(str(project))
