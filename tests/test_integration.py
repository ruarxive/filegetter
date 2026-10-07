"""Integration tests for end-to-end filegetter workflows."""

import csv
from zipfile import ZipFile

import responses
from click.testing import CliRunner

from filegetter.core import cli


def read_processed(project):
    path = project / "storage" / "processed.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestCSVWorkflow:
    @responses.activate
    def test_complete_workflow_via_cli(self, make_project, tmp_path, monkeypatch):
        responses.add(
            responses.GET,
            "https://example.com/file1.pdf",
            body=b"PDF content",
            content_type="application/pdf",
        )
        responses.add(
            responses.GET,
            "https://example.com/file2.jpg",
            body=b"JPEG content",
            content_type="image/jpeg",
        )

        project = make_project(files={"data.csv": "url,title\n/file1.pdf,A\n/file2.jpg,B\n"})

        # run from an unrelated cwd through --projectpath
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(cli, ["run", "--projectpath", str(project)])

        assert result.exit_code == 0
        with ZipFile(str(project / "storage" / "files.zip")) as zf:
            assert sorted(zf.namelist()) == ["file1.pdf", "file2.jpg"]
        rows = read_processed(project)
        assert len(rows) == 2
        assert all(r["status"] == "200" for r in rows)


class TestJSONLWorkflow:
    @responses.activate
    def test_complete_workflow_via_cli(self, make_project):
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
                "data.jsonl": '{"files": [{"url": "/doc1.pdf"}]}\n'
                '{"files": [{"url": "/doc2.pdf"}]}\n'
            },
        )

        result = CliRunner().invoke(cli, ["run", "--projectpath", str(project)])

        assert result.exit_code == 0
        with ZipFile(str(project / "storage" / "files.zip")) as zf:
            assert sorted(zf.namelist()) == ["doc1.pdf", "doc2.pdf"]


class TestErrorWorkflow:
    @responses.activate
    def test_failures_produce_nonzero_exit(self, make_project):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"Not Found", status=404)
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"ok")

        project = make_project(files={"data.csv": "url\n/file1.pdf\n/file2.pdf\n"})

        result = CliRunner().invoke(cli, ["run", "--projectpath", str(project)])

        assert result.exit_code == 1
        rows = read_processed(project)
        statuses = {r["url"]: r["status"] for r in rows}
        assert statuses["https://example.com/file1.pdf"] == "404"
        assert statuses["https://example.com/file2.pdf"] == "200"
        # error pages must not be archived
        with ZipFile(str(project / "storage" / "files.zip")) as zf:
            assert zf.namelist() == ["file2.pdf"]


class TestMissingConfig:
    def test_missing_config_clean_error(self, tmp_path):
        empty = tmp_path / "no-config"
        empty.mkdir()
        result = CliRunner().invoke(cli, ["run", "--projectpath", str(empty)])

        assert result.exit_code == 1
        assert "not found" in result.output


class TestResumeWorkflow:
    @responses.activate
    def test_second_run_resumes(self, make_project):
        responses.add(responses.GET, "https://example.com/file1.pdf", body=b"one")
        responses.add(responses.GET, "https://example.com/file2.pdf", body=b"two")

        project = make_project(files={"data.csv": "url\n/file1.pdf\n/file2.pdf\n"})

        runner = CliRunner()
        first = runner.invoke(cli, ["run", "--projectpath", str(project)])
        second = runner.invoke(cli, ["run", "--projectpath", str(project)])

        assert first.exit_code == 0
        assert second.exit_code == 0
        # 2 downloads on the first run, 0 on the second
        assert len(responses.calls) == 2
        assert len(read_processed(project)) == 2


class TestEntryPoint:
    def test_module_version(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "filegetter", "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "filegetter" in result.stdout

    def test_module_exit_code_on_missing_config(self, tmp_path):
        import subprocess
        import sys

        empty = tmp_path / "no-config"
        empty.mkdir()
        result = subprocess.run(
            [sys.executable, "-m", "filegetter", "run", "--projectpath", str(empty)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1
