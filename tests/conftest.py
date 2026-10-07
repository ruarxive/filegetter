"""Pytest configuration and shared fixtures for filegetter tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


def build_config(**overrides):
    """Build a filegetter.cfg text with sane defaults and per-option overrides.

    Overrides use dotted names like 'files.root_url' or None to remove
    the option from its section.
    """
    sections = {
        "project": {
            "name": "test_project",
            "source": "data.csv",
            "source_type": "csv",
            "delimiter": ",",
        },
        "data": {
            "data_key": "url",
        },
        "files": {
            "fetch_mode": "prefix",
            "root_url": "https://example.com/",
            "keys": "url",
            "storage_mode": "filepath",
        },
        "storage": {
            "storage_type": "zip",
            "compression": "True",
        },
    }
    for key, value in overrides.items():
        section, option = key.split(".", 1)
        if value is None:
            sections[section].pop(option, None)
        else:
            sections.setdefault(section, {})[option] = str(value)
    lines = []
    for section, options in sections.items():
        if not options:
            continue
        lines.append("[%s]" % section)
        for option, value in options.items():
            lines.append("%s = %s" % (option, value))
    return "\n".join(lines) + "\n"


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory (cleaned up afterwards)."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def make_project(temp_project_dir):
    """Factory creating a project directory with config and data files.

    Accepts build_config-style overrides (e.g. files.workers=2).
    """

    def _make(cfg=None, files=None, **overrides):
        root = temp_project_dir / "proj"
        root.mkdir(exist_ok=True)
        (root / "filegetter.cfg").write_text(cfg or build_config(**overrides))
        for name, content in (files or {}).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    return _make


@pytest.fixture
def project_with_config(make_project):
    """Project with a CSV source of two files."""
    return make_project(
        files={
            "data.csv": "url,title\n" "/file1.pdf,Document 1\n" "/file2.pdf,Document 2\n",
        }
    )
