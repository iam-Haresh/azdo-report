"""Small helpers shared across collectors, normalizers and reports."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Any, Iterable

_ISO = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$")
_GITLAB_KEY = re.compile(r"^[A-Za-z0-9_]+$")
_GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: Any) -> datetime | None:
    """Parse AZDO timestamps (7-digit fractions, 'Z', '0001-01-01' sentinels)."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    match = _ISO.match(text)
    if match:
        text = match.group(1) + (match.group(2) or "")[:7] + match.group(3)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.year <= 1:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def days_since(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    return max(0, (now - dt).days)


def percentile(values: Iterable[float | None], pct: float) -> float | None:
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    k = (len(data) - 1) * pct / 100
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return data[int(k)]
    return data[lo] + (data[hi] - data[lo]) * (k - lo)


def slugify(name: str) -> str:
    """GitLab-compatible path segment (letters, digits, '_', '-', '.')."""
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).lower()
    slug = re.sub(r"-{2,}", "-", slug).strip("-_.")
    if slug.endswith(".git") or slug.endswith(".atom"):
        slug = slug.rsplit(".", 1)[0] + "-repo"
    return slug or "unnamed"


def short_hash(*parts: Any) -> str:
    digest = hashlib.sha1("\x1f".join(str(p) for p in parts).encode("utf-8"))
    return digest.hexdigest()[:10]


def is_valid_gitlab_key(name: str) -> bool:
    return bool(_GITLAB_KEY.match(name or ""))


def gitlab_key(name: str) -> str:
    """Proposed GitLab CI/CD variable key.

    Uses the same transformation AZDO applies when exposing variables as
    environment variables (upper-case, non-alphanumerics -> '_'), so scripts that
    read the environment keep working.
    """
    return re.sub(r"[^A-Za-z0-9_]", "_", name or "").upper()


def is_guid(value: Any) -> bool:
    return isinstance(value, str) and bool(_GUID.match(value.strip()))


def branch_name(ref: str | None) -> str | None:
    if not ref:
        return None
    for prefix in ("refs/heads/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def first_line(text: str | None, limit: int = 80) -> str:
    if not text:
        return ""
    line = text.strip().splitlines()[0] if text.strip() else ""
    return line if len(line) <= limit else line[: limit - 1] + "…"


def compact(values: Iterable[Any], limit: int = 8, sep: str = ", ") -> str:
    """Join unique values preserving order, truncating long lists."""
    seen: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.append(text)
    if len(seen) > limit:
        return sep.join(seen[:limit]) + f"{sep}… (+{len(seen) - limit})"
    return sep.join(seen)


def minutes(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds / 60.0, 1)
