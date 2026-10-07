"""Utility functions for nested dict access and safe filename handling."""

from typing import Any, List

_MISSING = object()


def get_dict_value(
    data: Any,
    key: str,
    as_array: bool = False,
    splitter: str = ".",
) -> Any:
    """Get value from a hierarchical dict/list structure using dot notation.

    Args:
        data: Dictionary or list of dictionaries to search.
        key: Key path, e.g. 'parent.child.value'.
        as_array: Return every matching value as a list instead of the
            first match.
        splitter: Character separating key path components.

    Returns:
        The value at the key path, a list of all matches (as_array=True),
        or None when nothing matches.
    """
    values = _collect(data, key.split(splitter))
    if as_array:
        return values
    return values[0] if values else None


def _collect(node: Any, parts: List[str]) -> List[Any]:
    if not parts:
        return [node]
    head, rest = parts[0], parts[1:]
    found: List[Any] = []
    for item in node if isinstance(node, list) else [node]:
        if isinstance(item, dict):
            child = item.get(head, _MISSING)
            if child is not _MISSING:
                found.extend(_collect(child, rest))
    return found


def sanitize_filename(name: str) -> str:
    """Normalize a URL path or identifier into a safe relative path.

    Strips leading slashes (so the result can never escape the storage
    root), drops '.' and '..' segments, and converts backslashes to
    forward slashes.
    """
    parts = str(name).replace("\\", "/").split("/")
    parts = [p for p in parts if p not in ("", ".", "..")]
    return "/".join(parts)
