"""Shared default values for filegetter."""

DEFAULT_FIELD_SPLITTER = "."
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) " "Gecko/20100101 Firefox/101.0"
)
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 2
DEFAULT_DELAY = 0.0
DEFAULT_WORKERS = 1
FILE_SIZE_DOWNLOAD_LIMIT = 270_000_000

PROCESSED_FIELDS = [
    "url",
    "filename",
    "mime",
    "ext",
    "disp_name",
    "filesize",
    "status",
    "sha256",
]
