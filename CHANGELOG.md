# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-07

### Added
- `--dry-run`, `--limit N`, `--refresh` and `--version` CLI options
- SHA-256 checksums and HTTP status recorded in `storage/processed.csv`
- Failed downloads are recorded and automatically retried on the next run;
  the CLI exits with code 1 whenever any file failed
- Config validation with a single consolidated error message instead of raw
  `configparser` exceptions
- New `[files]` options: `delay`, `retries` (exponential backoff for
  429/5xx/connection errors), `timeout`, `workers` (parallel downloads),
  `max_filesize`, `user_agent`, `verify_ssl`
- Streaming downloads with an enforced file size limit (default 270 MB)
- Per-file error isolation: one broken URL no longer aborts the whole run;
  report rows are flushed immediately for crash-safe resume
- `[storage] compression` option is now honoured (was documented but ignored)
- Legacy 6-column `processed.csv` reports are upgraded automatically
- Comprehensive test suite (106 tests, 94% coverage), CI on Python 3.9-3.13
- Optional WARC/1.0 output: `[storage] write_warc = True` appends every
  successful response (full HTTP headers + payload) to
  `storage/files.warc.gz`; requires the `filegetter[warc]` extra
- Migration to `pyproject.toml` packaging, type hints, pre-commit hooks,
  Markdown README and CONTRIBUTING guide

### Fixed
- **Installation**: `setup.py` used `setuptools.command.test` (removed in
  setuptools 72) and imported the package at build time; packaging moved to
  `pyproject.toml` and `pip install` works again on current tooling
- **`--verbose`** was not a flag and required a value; `filegetter run
  --verbose` failed with "Option '--verbose' requires an argument". Debug
  logging is no longer enabled globally at import time
- **`--projectpath`**: source and storage paths were resolved against the
  current working directory instead of the project directory
- **HTTP error pages were archived as files**: responses with non-200 status
  (e.g. 404 pages) were stored in the archive and marked as processed; they
  are now recorded as failures and never stored
- **JSONL mode** appended the raw `data_key` value (e.g. a whole list) to the
  download list, producing garbage URLs and crashes
- **Filesystem storage escaped the project**: URL-derived absolute paths
  (`/a/b.pdf`) were joined outside the storage directory, potentially
  writing to the filesystem root; paths are now sanitized against escape
- **`delimiter`** values other than the literal `tab` were silently replaced
  with `,`; e.g. `delimiter = ;` now works
- Double slashes in built URLs and archive entry names (`//file.pdf`)
- Config reading checked the wrong section for `id`/`splitter` options
  (copy-paste from another project)
- `python -m filegetter` always exited with code 0; exit codes now reflect
  the outcome (130 on Ctrl-C)
- Extensions: `transfer_ext` no longer duplicates extensions
  (`file.pdf.pdf`) and now falls back to `default_ext`; `default_ext` is
  only applied to files without an extension
- Fixed typo: `__licence__` → `__license__` in `__init__.py`

### Changed
- Minimum supported Python version is 3.9 (3.8 is EOL)
- Dependencies reduced to `click` and `requests` (`lxml`, `xmltodict` and
  `aria2p` are no longer needed)
- CLI: the meaningless `run MODE` argument was removed
- Config: `[files] file_storage_type` is the single storage selector;
  `[storage] storage_type` still works as a legacy alias
- `storage/files.zip` entry names no longer have leading slashes; report
  gains `status` and `sha256` columns

### Removed
- **aria2 integration**: it was non-functional (downloads were never recorded
  in `processed.csv`, so every run re-fetched everything; hardcoded RPC
  settings; `NameError` when `aria2p` was not installed). The `use_aria2`
  option is ignored with a warning
- Dead code: unfinished `init()` stub, `_url_replacer`, XML helpers in
  `common.py`, unused imports and constants

## [1.0.1] - 2022-10-05

### Added
- First public release on PyPI
- Command-line interface for file collection
- Support for CSV, JSONL, and list input formats
- ZIP and filesystem storage options
- URL prefix and pattern-based fetching
- Extension detection and transfer
- Optional aria2 integration
- Progress tracking with CSV reports
- Resume capability for interrupted downloads
