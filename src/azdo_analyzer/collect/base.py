"""Collector plumbing: cached fetch, coverage recording and parallel map."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, TypeVar

from azdo_analyzer.cache import RawStore
from azdo_analyzer.client import AzdoClient, AzdoHttpError
from azdo_analyzer.config import Config
from azdo_analyzer.util import iso, utcnow

log = logging.getLogger("azdo_analyzer.collect")
T = TypeVar("T")
R = TypeVar("R")

_STATUS_RANK = {"OK": 0, "CACHED": 0, "NOT_FOUND": 1, "SKIPPED": 1, "MISSING_OFFLINE": 2, "FORBIDDEN": 3, "ERROR": 4}


@dataclass
class CoverageEntry:
    scope: str
    collector: str
    endpoint: str
    status: str = "OK"
    calls: int = 0
    failed: int = 0
    items: int = 0
    message: str = ""


class Coverage:
    """Tracks which endpoints worked, per scope, so permission gaps are visible."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], CoverageEntry] = {}
        self._lock = threading.Lock()

    def record(self, scope: str, collector: str, endpoint: str, status: str, items: int = 0, message: str = "") -> None:
        key = (scope, collector, endpoint)
        with self._lock:
            entry = self._entries.setdefault(key, CoverageEntry(scope, collector, endpoint, status="OK"))
            entry.calls += 1
            entry.items += items
            if status not in ("OK", "CACHED", "NOT_FOUND", "SKIPPED"):
                entry.failed += 1
            if _STATUS_RANK.get(status, 4) > _STATUS_RANK.get(entry.status, 0) or entry.calls == 1:
                entry.status = status
                if message:
                    entry.message = message

    def entries(self, scope: str | None = None) -> list[CoverageEntry]:
        with self._lock:
            values = list(self._entries.values())
        return [e for e in values if scope is None or e.scope == scope]

    def to_list(self, scope: str | None = None) -> list[dict[str, Any]]:
        return [asdict(e) for e in self.entries(scope)]

    @classmethod
    def from_list(cls, rows: Iterable[dict[str, Any]]) -> "Coverage":
        cov = cls()
        for row in rows or []:
            entry = CoverageEntry(**row)
            cov._entries[(entry.scope, entry.collector, entry.endpoint)] = entry
        return cov


@dataclass
class CollectContext:
    client: AzdoClient | None
    store: RawStore
    cfg: Config
    coverage: Coverage
    refresh: bool = False
    deep: bool = False
    now: datetime = field(default_factory=utcnow)
    progress: Callable[[str], None] = lambda msg: None

    @property
    def online(self) -> bool:
        return self.client is not None

    def fetch(
        self,
        parts: tuple[Any, ...],
        fn: Callable[[], Any],
        *,
        scope: str,
        collector: str,
        endpoint: str,
    ) -> Any:
        """Return cached JSON, or call ``fn`` and cache the result.

        401/403/404 and other API errors are recorded in coverage and yield None.
        404 is cached as a marker so empty/deleted resources are not re-queried.
        """
        if not self.refresh and self.store.has(*parts):
            if self.store.is_missing_marker(*parts):
                self.coverage.record(scope, collector, endpoint, "NOT_FOUND")
                return None
            data = self.store.read(*parts)
            self.coverage.record(scope, collector, endpoint, "CACHED", _count(data))
            return data
        if self.client is None:
            self.coverage.record(scope, collector, endpoint, "MISSING_OFFLINE")
            return None
        try:
            data = fn()
        except AzdoHttpError as exc:
            status = {401: "FORBIDDEN", 403: "FORBIDDEN", 404: "NOT_FOUND"}.get(exc.status, "ERROR")
            if status == "NOT_FOUND":
                self.store.write(RawStore.MISSING, *parts)
            log.info("%s %s: %s", collector, endpoint, exc)
            self.coverage.record(scope, collector, endpoint, status, message=exc.message[:300])
            return None
        self.store.write(data, *parts)
        self.coverage.record(scope, collector, endpoint, "OK", _count(data))
        return data

    def pmap(self, fn: Callable[[T], R], items: Iterable[T], workers: int | None = None) -> list[R]:
        items = list(items)
        if not items:
            return []
        workers = max(1, workers or self.cfg.azdo.concurrency)
        if workers == 1 or len(items) == 1:
            return [fn(item) for item in items]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, items))

    def history_start(self) -> str:
        from datetime import timedelta

        return iso(self.now - timedelta(days=self.cfg.collection.history_days))


def _count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    return 0 if data is None else 1


def write_meta(store: RawStore, scope: str, **values: Any) -> None:
    meta = store.read(scope, "_meta.json", default={}) or {}
    meta.update(values)
    store.write(meta, scope, "_meta.json")
