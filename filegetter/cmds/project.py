"""Filegetter project runner: config parsing and bulk file downloads."""

import configparser
import csv
import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from zipfile import ZIP_DEFLATED, ZIP_STORED

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:  # optional extra: pip install filegetter[warc]
    from warcio.statusandheaders import StatusAndHeaders
    from warcio.warcwriter import WARCWriter
except ImportError:
    StatusAndHeaders = None  # type: ignore[assignment,misc]
    WARCWriter = None  # type: ignore[assignment,misc]

from .. import __version__
from ..common import get_dict_value, sanitize_filename
from ..constants import (
    DEFAULT_DELAY,
    DEFAULT_FIELD_SPLITTER,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    DEFAULT_WORKERS,
    FILE_SIZE_DOWNLOAD_LIMIT,
    PROCESSED_FIELDS,
    WARC_FILENAME,
)
from ..storage import FileStorage, FilesystemStorage, ZipFileStorage

logger = logging.getLogger(__name__)

SOURCE_TYPES = ("csv", "jsonl", "list")
FETCH_MODES = ("prefix", "pattern")
STORAGE_MODES = ("filepath", "id")
FILE_STORAGE_TYPES = ("zip", "filesystem")

_CD_FILENAME_STAR_RE = re.compile(r"filename\*\s*=\s*(?:utf-8|UTF-8)''([^;]+)", re.IGNORECASE)
_CD_FILENAME_RE = re.compile(r'filename\s*=\s*"?([^";]+)"?', re.IGNORECASE)


class ConfigError(Exception):
    """Raised when filegetter.cfg is missing, incomplete or invalid."""


def load_file_list(filename: str, encoding: str = "utf-8") -> List[str]:
    """Read a text file and return its non-empty lines."""
    with open(filename, "r", encoding=encoding) as f:
        return [line.rstrip() for line in f]


def load_csv_data(
    filename: str,
    key: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> Dict[str, Dict[str, str]]:
    """Read a CSV file into a dict keyed by the given column."""
    result: Dict[str, Dict[str, str]] = {}
    with open(filename, "r", encoding=encoding) as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None or key not in reader.fieldnames:
            raise ValueError(
                "Column '%s' not found in %s (columns: %s)" % (key, filename, reader.fieldnames)
            )
        for row in reader:
            if row.get(key):
                result[row[key]] = row
    return result


def load_processed_files_list(filename: str, encoding: str = "utf-8") -> Dict[str, Dict[str, str]]:
    """Read processed.csv into a dict keyed by URL."""
    return load_csv_data(filename, "url", encoding=encoding)


def parse_content_disposition(value: str) -> Optional[str]:
    """Extract a filename from a Content-Disposition header value."""
    match = _CD_FILENAME_STAR_RE.search(value)
    if match:
        return unquote(match.group(1).strip())
    match = _CD_FILENAME_RE.search(value)
    if match:
        return match.group(1).strip().strip('"')
    return None


def build_url(root_url: str, uniq_id: str, fetch_mode: str) -> str:
    """Build the download URL for a source identifier."""
    uid = str(uniq_id).strip()
    if fetch_mode == "pattern":
        return root_url.format(uid)
    if uid.startswith(("http://", "https://")):
        return uid
    if not root_url:
        return uid
    return root_url.rstrip("/") + "/" + uid.lstrip("/")


class FilegetterBuilder:
    """Reads a filegetter project config and downloads the listed files."""

    def __init__(self, project_path: Optional[str] = None):
        self.project_path = os.getcwd() if project_path is None else project_path
        self.config_filename = os.path.join(self.project_path, "filegetter.cfg")
        self._read_config(self.config_filename)
        self.http = self._build_session()

    # ------------------------------------------------------------------
    # Configuration

    def _read_config(self, filename: str) -> None:
        if not os.path.exists(filename):
            raise ConfigError(
                "Config file not found: %s. Run in a project directory or "
                "pass --projectpath." % filename
            )
        conf = configparser.ConfigParser()
        conf.read(filename, encoding="utf-8")
        self.config = conf

        errors: List[str] = []

        def get(section: str, option: str, fallback: Optional[str] = None) -> Optional[str]:
            if conf.has_option(section, option):
                return conf.get(section, option)
            return fallback

        def get_bool(section: str, option: str, fallback: bool) -> bool:
            if not conf.has_option(section, option):
                return fallback
            try:
                return conf.getboolean(section, option)
            except ValueError:
                errors.append("Option [%s] %s must be True or False" % (section, option))
                return fallback

        def get_number(section: str, option: str, fallback: float, minimum: float) -> float:
            raw = get(section, option)
            if raw is None:
                return fallback
            try:
                value = float(raw)
            except ValueError:
                errors.append("Option [%s] %s must be a number" % (section, option))
                return fallback
            if value < minimum:
                errors.append("Option [%s] %s must be >= %s" % (section, option, minimum))
                return fallback
            return value

        # [project]
        name = get("project", "name") or ""
        source_type = get("project", "source_type") or ""
        self.field_splitter = get("project", "splitter") or DEFAULT_FIELD_SPLITTER
        delimiter = get("project", "delimiter") or ","
        self.delimiter = "\t" if delimiter == "tab" else delimiter
        source = get("project", "source") or ""

        # [data]
        data_key = get("data", "data_key") or ""

        # [files]
        fetch_mode = get("files", "fetch_mode") or ""
        root_url_raw = get("files", "root_url")
        keys_raw = get("files", "keys")
        files_keys = [k.strip() for k in keys_raw.split(",")] if keys_raw else []
        storage_mode = get("files", "storage_mode") or "filepath"
        self.default_ext = get("files", "default_ext")
        self.transfer_ext = get_bool("files", "transfer_ext", False)
        file_storage_type = get("files", "file_storage_type")
        if file_storage_type is None:
            # legacy option from [storage]
            file_storage_type = get("storage", "storage_type") or "zip"
        self.delay = get_number("files", "delay", DEFAULT_DELAY, 0)
        self.retries = int(get_number("files", "retries", DEFAULT_RETRIES, 0))
        self.timeout = get_number("files", "timeout", DEFAULT_TIMEOUT, 0)
        self.workers = int(get_number("files", "workers", DEFAULT_WORKERS, 1))
        self.max_filesize = int(get_number("files", "max_filesize", FILE_SIZE_DOWNLOAD_LIMIT, 1))
        self.user_agent = get("files", "user_agent") or DEFAULT_USER_AGENT
        self.verify_ssl = get_bool("files", "verify_ssl", True)

        # [storage]
        storagedir = get("storage", "storage_path") or "storage"
        self.compression = get_bool("storage", "compression", True)
        self.write_warc = get_bool("storage", "write_warc", False)

        if (get("files", "use_aria2") or "False").lower() == "true":
            logger.warning(
                "Option [files] use_aria2 is ignored: aria2 support was "
                "removed in filegetter 1.1.0 (it never recorded downloads "
                "in processed.csv); built-in downloading is used instead"
            )

        # Validation
        if not name:
            errors.append("Option [project] name is required")
        if not source:
            errors.append("Option [project] source is required")
        if source_type not in SOURCE_TYPES:
            errors.append(
                "Option [project] source_type must be one of: %s" % ", ".join(SOURCE_TYPES)
            )
        if source_type in ("csv", "jsonl") and not data_key:
            errors.append("Option [data] data_key is required for source_type=%s" % source_type)
        if not files_keys:
            errors.append("Option [files] keys is required (comma-separated list)")
        if fetch_mode not in FETCH_MODES:
            errors.append("Option [files] fetch_mode must be one of: %s" % ", ".join(FETCH_MODES))
        if fetch_mode == "pattern" and root_url_raw is not None and "{}" not in root_url_raw:
            errors.append(
                "Option [files] root_url must contain a '{}' placeholder " "when fetch_mode=pattern"
            )
        if root_url_raw is None:
            errors.append("Option [files] root_url is required")
        if storage_mode not in STORAGE_MODES:
            errors.append(
                "Option [files] storage_mode must be one of: %s" % ", ".join(STORAGE_MODES)
            )
        if file_storage_type not in FILE_STORAGE_TYPES:
            errors.append(
                "Option [files] file_storage_type must be one of: %s"
                % ", ".join(FILE_STORAGE_TYPES)
            )
        if self.write_warc and WARCWriter is None:
            errors.append(
                "Option [storage] write_warc requires the warcio package: "
                "pip install filegetter[warc]"
            )

        if errors:
            raise ConfigError("Invalid configuration:\n- " + "\n- ".join(errors))

        # Resolved, non-optional attributes
        if not os.path.isabs(source):
            source = os.path.join(self.project_path, source)
        if not os.path.isabs(storagedir):
            storagedir = os.path.join(self.project_path, storagedir)
        self.name = name
        self.source_type = source_type
        self.source = source
        self.data_key = data_key
        self.fetch_mode = fetch_mode
        self.root_url = root_url_raw or ""
        self.files_keys = files_keys
        self.storage_mode = storage_mode
        self.file_storage_type = file_storage_type
        self.storagedir = storagedir

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=max(self.workers, 1))
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers["User-Agent"] = self.user_agent
        return session

    # ------------------------------------------------------------------
    # Source parsing

    def _load_ids(self) -> List[str]:
        ids: List[str] = []
        if self.source_type == "list":
            ids = [line.strip() for line in load_file_list(self.source) if line.strip()]
        elif self.source_type == "csv":
            with open(self.source, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=self.delimiter)
                if reader.fieldnames is None or self.data_key not in reader.fieldnames:
                    raise ConfigError(
                        "Column '%s' not found in %s (columns: %s)"
                        % (self.data_key, self.source, reader.fieldnames)
                    )
                for row in reader:
                    value = row.get(self.data_key)
                    if value:
                        ids.append(value)
        elif self.source_type == "jsonl":
            with open(self.source, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.warning("Skipping malformed JSON line %d: %s", lineno, e)
                        continue
                    if self.data_key:
                        records = (
                            get_dict_value(
                                row,
                                self.data_key,
                                as_array=True,
                                splitter=self.field_splitter,
                            )
                            or []
                        )
                    else:
                        records = [row]
                    for record in records:
                        for key in self.files_keys:
                            values = (
                                get_dict_value(
                                    record,
                                    key,
                                    as_array=True,
                                    splitter=self.field_splitter,
                                )
                                or []
                            )
                            for value in values:
                                if value is not None and str(value).strip():
                                    ids.append(str(value).strip())
        # Deduplicate while preserving order
        return list(dict.fromkeys(ids))

    # ------------------------------------------------------------------
    # Downloading

    def _fetch(self, url: str, filename: str) -> Tuple[Dict[str, Any], Optional[bytes]]:
        if self.delay > 0:
            time.sleep(self.delay)
        response = self.http.get(url, stream=True, timeout=self.timeout, verify=self.verify_ssl)
        record: Dict[str, Any] = {
            "url": url,
            "filename": filename,
            "mime": None,
            "ext": None,
            "disp_name": None,
            "filesize": 0,
            "status": str(response.status_code),
            "sha256": "",
        }
        try:
            record["mime"] = response.headers.get("content-type")
            disposition = response.headers.get("content-disposition")
            if disposition:
                record["disp_name"] = parse_content_disposition(disposition)

            if response.status_code != 200:
                record["error"] = "HTTP %d" % response.status_code
                return record, None

            # full header set kept for the WARC record
            record["http_headers"] = list(response.headers.items())
            record["reason"] = response.reason or ""

            hasher = hashlib.sha256()
            chunks: List[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > self.max_filesize:
                    record["error"] = (
                        "File exceeds max_filesize limit (%d bytes)" % self.max_filesize
                    )
                    record["status"] = "error"
                    return record, None
                hasher.update(chunk)
                chunks.append(chunk)
            record["filesize"] = size
            record["sha256"] = hasher.hexdigest()
            return record, b"".join(chunks)
        finally:
            response.close()

    def _fetch_safe(self, url: str, filename: str) -> Tuple[Dict[str, Any], Optional[bytes]]:
        try:
            return self._fetch(url, filename)
        except requests.RequestException as e:
            logger.warning("Download failed: %s (%s)", url, e)
        except Exception:  # keep the batch running on unexpected errors
            logger.exception("Unexpected error downloading %s", url)
        record = {
            "url": url,
            "filename": filename,
            "mime": None,
            "ext": None,
            "disp_name": None,
            "filesize": 0,
            "status": "error",
            "sha256": "",
            "error": "connection error",
        }
        return record, None

    def _apply_ext(self, filename: str, disp_name: Optional[str]) -> Tuple[str, Optional[str]]:
        ext = None
        if disp_name and "." in disp_name:
            ext = disp_name.rsplit(".", 1)[-1].lower()
        target = None
        if self.transfer_ext:
            target = ext or self.default_ext
        elif self.default_ext:
            target = self.default_ext
        # Only extend names that have no extension at all
        if target and "." not in os.path.basename(filename):
            filename = filename + "." + target.lstrip(".").lower()
        return filename, ext

    def _filename_for(self, uniq_id: str, url: str, index: int) -> str:
        if self.storage_mode == "filepath":
            filename = sanitize_filename(urlparse(url).path)
            if not filename:
                filename = sanitize_filename(str(uniq_id))
        else:
            filename = sanitize_filename(str(uniq_id))
        return filename or "file_%06d" % index

    def _build_storage(self) -> FileStorage:
        if self.file_storage_type == "zip":
            compression = ZIP_DEFLATED if self.compression else ZIP_STORED
            return ZipFileStorage(
                os.path.join(self.storagedir, "files.zip"),
                mode="a",
                compression=compression,
            )
        return FilesystemStorage(os.path.join(self.storagedir, "files"))

    def _open_warc(self):
        """Open (or create) the WARC file and return (file, writer)."""
        if not self.write_warc:
            return None, None
        warc_path = os.path.join(self.storagedir, WARC_FILENAME)
        is_new = not os.path.exists(warc_path) or os.path.getsize(warc_path) == 0
        warc_file = open(warc_path, "ab")
        writer = WARCWriter(warc_file, gzip=True)
        if is_new:
            warcinfo = writer.create_warcinfo_record(
                WARC_FILENAME,
                {
                    "software": "filegetter/%s" % __version__,
                    "format": "WARC file version 1.0",
                },
            )
            writer.write_record(warcinfo)
        return warc_file, writer

    def _write_warc_record(self, writer, record: Dict[str, Any], content: bytes) -> None:
        http_headers = StatusAndHeaders(
            "%s %s" % (record["status"], record.get("reason") or "OK"),
            list(record.get("http_headers") or []),
            protocol="HTTP/1.1",
        )
        warc_record = writer.create_warc_record(
            record["url"],
            "response",
            payload=BytesIO(content),
            http_headers=http_headers,
        )
        writer.write_record(warc_record)

    def run(
        self, dry_run: bool = False, limit: Optional[int] = None, refresh: bool = False
    ) -> Dict[str, int]:
        """Download all files listed in the project source.

        Returns a stats dict with 'total', 'skipped', 'downloaded' and
        'failed' counters ('pending' instead for dry runs).
        """
        if dry_run:
            uniq_ids = self._load_ids()
        else:
            os.makedirs(self.storagedir, exist_ok=True)
            allfiles_name = os.path.join(self.storagedir, "allfiles.csv")
            if refresh or not os.path.exists(allfiles_name):
                uniq_ids = self._load_ids()
                logger.info("Storing %d file ids", len(uniq_ids))
                with open(allfiles_name, "w", encoding="utf-8") as f:
                    for uid in uniq_ids:
                        f.write(str(uid) + "\n")
            else:
                logger.info("Loading cached file ids from %s", allfiles_name)
                uniq_ids = [u for u in load_file_list(allfiles_name) if u.strip()]

        if not uniq_ids:
            logger.error("No file identifiers found in source %s", self.source)
            return {"total": 0, "skipped": 0, "downloaded": 0, "failed": 0, "pending": 0}

        entries = []
        for index, uniq_id in enumerate(uniq_ids):
            url = build_url(self.root_url, uniq_id, self.fetch_mode)
            entries.append((uniq_id, url, self._filename_for(uniq_id, url, index)))

        processed_path = os.path.join(self.storagedir, "processed.csv")
        processed: Dict[str, Dict[str, str]] = {}
        if os.path.exists(processed_path):
            processed = load_processed_files_list(processed_path)

        def is_done(url: str) -> bool:
            row = processed.get(url)
            if row is None:
                return False
            # rows written by <=1.0.x have no status column; treat as done
            return row.get("status") in (None, "", "200")

        pending = [e for e in entries if not is_done(e[1])]
        stats = {
            "total": len(entries),
            "skipped": len(entries) - len(pending),
        }

        if limit is not None and limit >= 0:
            pending = pending[:limit]

        if dry_run:
            logger.info("Dry run: %d of %d files would be downloaded", len(pending), len(entries))
            for _, url, _ in pending:
                logger.info("Would download %s", url)
            stats["pending"] = len(pending)
            return stats

        stats["downloaded"] = 0
        stats["failed"] = 0

        list_file = self._open_processed_csv(processed_path)
        writer = csv.writer(list_file, delimiter=",")
        storage = self._build_storage()
        warc_file, warc_writer = self._open_warc()
        try:

            def handle(record: Dict[str, Any], content: Optional[bytes]) -> None:
                filename = record["filename"]
                if content is not None:
                    filename, ext = self._apply_ext(filename, record["disp_name"])
                    record["filename"] = filename
                    record["ext"] = ext
                    storage.store(filename, content)
                    if warc_writer is not None:
                        self._write_warc_record(warc_writer, record, content)
                    stats["downloaded"] += 1
                    logger.info(
                        "Stored %s (%d bytes, sha256=%s)",
                        filename,
                        record["filesize"],
                        record["sha256"][:12],
                    )
                else:
                    stats["failed"] += 1
                    logger.warning(
                        "Failed %s: %s", record["url"], record.get("error", record["status"])
                    )
                writer.writerow(
                    [
                        record["url"],
                        record["filename"],
                        record["mime"] or "",
                        record["ext"] or "",
                        record["disp_name"] or "",
                        record["filesize"],
                        record["status"],
                        record["sha256"],
                    ]
                )
                list_file.flush()

            done = 0
            if self.workers > 1:
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    futures = [
                        (url, pool.submit(self._fetch_safe, url, filename))
                        for _, url, filename in pending
                    ]
                    for url, future in futures:
                        record, content = future.result()
                        handle(record, content)
                        done += 1
                        if done % 50 == 0:
                            logger.info("Processed %d/%d files", done, len(pending))
            else:
                for _, url, filename in pending:
                    record, content = self._fetch_safe(url, filename)
                    handle(record, content)
                    done += 1
                    if done % 50 == 0:
                        logger.info("Processed %d/%d files", done, len(pending))
        finally:
            storage.close()
            list_file.close()
            if warc_file is not None:
                warc_file.flush()
                warc_file.close()

        logger.info(
            "Finished: %d total, %d skipped (already downloaded), " "%d downloaded, %d failed",
            stats["total"],
            stats["skipped"],
            stats["downloaded"],
            stats["failed"],
        )
        return stats

    def _open_processed_csv(self, path: str):
        """Open processed.csv for appending, upgrading legacy headers."""
        if not os.path.exists(path):
            list_file = open(path, "w", encoding="utf-8", newline="")
            csv.writer(list_file).writerow(PROCESSED_FIELDS)
            return list_file
        with open(path, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        if not rows or rows[0] != PROCESSED_FIELDS:
            # Upgrade a legacy 6-column report to the current format
            records = []
            if rows:
                header = rows[0]
                for row in rows[1:]:
                    if not row:
                        continue
                    record = dict(zip(header, row))
                    records.append(
                        [
                            record.get("url", ""),
                            record.get("filename", ""),
                            record.get("mime", ""),
                            record.get("ext", ""),
                            record.get("disp_name", ""),
                            record.get("filesize", ""),
                            record.get("status", ""),
                            record.get("sha256", ""),
                        ]
                    )
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(PROCESSED_FIELDS)
                writer.writerows(records)
        return open(path, "a", encoding="utf-8", newline="")
