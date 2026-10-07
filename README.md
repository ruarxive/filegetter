# filegetter

[![PyPI version](https://badge.fury.io/py/filegetter.svg)](https://badge.fury.io/py/filegetter)
[![Python Versions](https://img.shields.io/pypi/pyversions/filegetter.svg)](https://pypi.org/project/filegetter/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/ruarxive/filegetter/actions/workflows/tests.yml/badge.svg)](https://github.com/ruarxive/filegetter/actions/workflows/tests.yml)

**filegetter** is a command-line tool and Python library for automated bulk
file collection from public data sources.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration Reference](#configuration-reference)
- [How It Works](#how-it-works)
- [Examples](#examples)
- [Development](#development)
- [License](#license)

---

## Overview

Filegetter automates downloading large numbers of files from URLs listed in
configuration-driven project files. It was built to streamline file collection
from datasets produced by other tools (API scrapers, data extracts), with
support for several input formats and storage backends, resumable runs and a
detailed per-file report.

---

## Features

✅ **Multiple Input Formats** - CSV, JSON Lines (JSONL) and plain text lists
✅ **Flexible URL Handling** - URL prefixes, `{}`-patterns and absolute URLs
✅ **Storage Options** - ZIP archive or filesystem directory tree
✅ **Resume Capability** - Already-downloaded files are skipped; failed files are retried
✅ **Integrity & Reporting** - CSV report with HTTP status, MIME type, size and SHA-256 checksum
✅ **WARC Output** - Optional archival WARC/1.0 records (`pip install filegetter[warc]`)
✅ **Robust Downloads** - Retries with backoff, timeouts, per-file error isolation
✅ **Politeness Controls** - Configurable delay, User-Agent, worker count and file size limit
✅ **Zip Compression Toggle** - `compression` option for smaller archives or faster writes

---

## Installation

### Requirements

- Python 3.9 or higher

### Install from PyPI

```bash
pip install --upgrade pip
pip install --upgrade filegetter

# with WARC output support (see [storage] write_warc below)
pip install --upgrade filegetter[warc]
```

### Install from Source

```bash
git clone https://github.com/ruarxive/filegetter.git
cd filegetter
pip install -e .
```

---

## Quick Start

This example demonstrates archiving files from the Russian federal draft
budget law 2023-2025.

### 1. Create a Project Directory

```bash
mkdir budget2023
cd budget2023
```

### 2. Create Configuration File

Create a file named `filegetter.cfg`:

```ini
[project]
name = budget2023
source = dataset.csv
source_type = csv
delimiter = ,

[data]
data_key = href

[files]
fetch_mode = prefix
root_url = https://sozd.duma.gov.ru
keys = href
storage_mode = filepath
transfer_ext = True

[storage]
storage_type = zip
compression = True
```

### 3. Run the Collection

```bash
filegetter run
```

Downloaded files are stored in `storage/files.zip`, with the per-file report
in `storage/processed.csv` and the cached source id list in
`storage/allfiles.csv`.

---

## Usage

### Command Syntax

```bash
filegetter [OPTIONS] COMMAND [ARGS]
```

### Commands

- **`run`** - Execute the file collection project

### Options

| Option | Description |
|--------|-------------|
| `--projectpath PATH`, `-p PATH` | Project directory (default: current directory). All relative paths in the config are resolved against this directory, so you can run projects from anywhere. |
| `--verbose`, `-v` | Debug-level logging (default: INFO) |
| `--dry-run` | List pending downloads without fetching or writing anything |
| `--limit N` | Download at most N pending files in this run |
| `--refresh` | Re-read the source file instead of the cached `allfiles.csv` |
| `--version` | Print the version and exit |

### Examples

```bash
# Run in current directory
filegetter run

# Run a project located elsewhere
filegetter run --projectpath /path/to/project

# See what would be downloaded, without touching the network
filegetter run --dry-run

# Download at most 100 pending files with debug logging
filegetter run --limit 100 --verbose

# Source file changed since the last run - rebuild the id cache
filegetter run --refresh
```

### Exit Codes

- `0` - all requested files were processed successfully (or skipped)
- `1` - configuration error, or some files failed to download

Failures are always recorded in `storage/processed.csv` (with a non-200
`status`) and retried on the next run.

---

## Configuration Reference

All configuration is stored in `filegetter.cfg` using INI format. Invalid
values produce a single error listing every problem found.

### `[project]` Section

| Option | Required | Description |
|--------|----------|-------------|
| `name` | Yes | Short name for the project |
| `source` | Yes | Source data file path, resolved relative to the project directory |
| `source_type` | Yes | One of: `csv`, `jsonl`, `list` |
| `delimiter` | No | Column delimiter for CSV (`tab` means tab; default `,`) |

### `[data]` Section

| Option | Required | Description |
|--------|----------|-------------|
| `data_key` | Yes for `csv`/`jsonl` | Column name (CSV) or dot-path into JSON records (JSONL) containing URLs or URL parts |

### `[files]` Section

| Option | Required | Description |
|--------|----------|-------------|
| `fetch_mode` | Yes | `prefix` (prepend `root_url`) or `pattern` (`root_url` with a `{}` placeholder) |
| `root_url` | Yes | Base URL. May be empty when source ids are absolute URLs. Ids starting with `http://`/`https://` always override it. |
| `keys` | Yes | Comma-separated list of keys containing file URLs/ids (used for JSONL sources) |
| `storage_mode` | No | `filepath` (mirror the URL path; default) or `id` (use the raw id as filename) |
| `transfer_ext` | No | If `True`, add an extension (from Content-Disposition, or `default_ext` as fallback) to files that have none |
| `default_ext` | No | Extension to add to extension-less files |
| `file_storage_type` | No | `zip` (default) or `filesystem` |
| `delay` | No | Delay in seconds between requests (default `0`) |
| `retries` | No | Retry attempts for transient HTTP errors (429/5xx) and connection errors (default `2`, exponential backoff) |
| `timeout` | No | Request timeout in seconds (default `30`) |
| `workers` | No | Parallel download threads (default `1`) |
| `max_filesize` | No | Skip files larger than this many bytes (default `270000000`) |
| `user_agent` | No | User-Agent header (default: a Firefox browser string) |
| `verify_ssl` | No | Verify TLS certificates (default `True`) |

### `[storage]` Section

| Option | Required | Description |
|--------|----------|-------------|
| `storage_path` | No | Directory for storage files, relative to the project (default `storage`) |
| `compression` | No | `True` (default) compresses the ZIP archive; `False` stores entries uncompressed |
| `storage_type` | Legacy | Alias for `file_storage_type` used by configs from 1.0.x |
| `write_warc` | No | If `True`, additionally write every successful response (full HTTP headers + body) to `storage/files.warc.gz` in WARC/1.0 format. Requires the `warc` extra: `pip install filegetter[warc]` |

### Report Format

`storage/processed.csv` has one row per attempted file:

| Column | Meaning |
|--------|---------|
| `url` | Requested URL |
| `filename` | Name under which the file was stored |
| `mime` | Content-Type header |
| `ext` | Extension detected from Content-Disposition |
| `disp_name` | Filename from Content-Disposition |
| `filesize` | Size in bytes |
| `status` | HTTP status code (`200`, `404`, ...) or `error` for connection failures / size limit rejections |
| `sha256` | SHA-256 checksum of the stored content |

---

## How It Works

1. The source file (`csv`, `jsonl` or `list`) is read and reduced to a
   de-duplicated list of file identifiers, cached in `allfiles.csv`
   (pass `--refresh` to rebuild it after the source changes).
2. For every id a URL is built (`prefix` or `pattern` mode); ids already
   recorded with status `200` in `processed.csv` are skipped.
3. Each pending file is downloaded (streamed, with retries, timeout and the
   size limit enforced), stored via the configured backend and recorded in
   `processed.csv` with its checksum - the row is flushed immediately, so an
   interrupted run can simply be re-run.
4. Files that failed (HTTP errors, connection problems) are recorded with
   their status and retried automatically on the next run; the command exits
   with code 1 whenever anything failed.
5. With `[storage] write_warc = True` every successful response is also
   appended to `storage/files.warc.gz` as a WARC record with the complete
   HTTP headers, preserving full provenance for archival use.

---

## Examples

See the [`examples/`](examples/) directory for complete working examples:

- **budget2023** - Russian federal budget documents
- **goskatalog** - Government catalog images
- **rupolitparties** - Russian political parties data

Each example includes a complete `filegetter.cfg` and source data file.

---

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/ruarxive/filegetter.git
cd filegetter
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
pre-commit install
```

### Running Tests

```bash
# Run all tests (with coverage)
pytest

# Run a specific test file
pytest tests/test_storage.py
```

### Code Quality

```bash
black filegetter/ tests/
isort filegetter/ tests/
flake8 filegetter/ tests/
mypy filegetter/
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for
guidelines.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE)
file for details.

Copyright (c) 2022-2026 Russian national digital archive

---

## Author

**Ivan Begtin** - [ivan@begtin.tech](mailto:ivan@begtin.tech)

---

## Links

- **GitHub Repository**: https://github.com/ruarxive/filegetter
- **PyPI Package**: https://pypi.org/project/filegetter/
- **Issue Tracker**: https://github.com/ruarxive/filegetter/issues
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
