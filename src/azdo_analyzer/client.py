"""Read-only REST client for Azure DevOps Server / Services.

Safety properties:
* Only GET requests can be sent (checked in ``request`` and again in an httpx
  request hook), so the tool cannot modify anything even if the PAT is broader.
* The PAT and its Base64 form are redacted from every log line and exception.
"""

from __future__ import annotations

import base64
import logging
import random
import re
import threading
import time
from collections import Counter
from typing import Any, Callable, Iterator
from urllib.parse import quote

import httpx

log = logging.getLogger("azdo_analyzer.http")

_GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_NUM_SEGMENT = re.compile(r"(?<=/)\d+(?=/|$)")
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class ReadOnlyViolation(RuntimeError):
    """Raised when anything other than a GET request is attempted."""


class AzdoHttpError(RuntimeError):
    def __init__(self, status: int, url: str, message: str, type_key: str | None = None):
        super().__init__(f"HTTP {status} for {url}: {message}")
        self.status = status
        self.url = url
        self.message = message
        self.type_key = type_key


class Redactor:
    def __init__(self, secrets: list[str]):
        self._secrets = sorted({s for s in secrets if s and len(s) >= 4}, key=len, reverse=True)

    def __call__(self, text: Any) -> str:
        out = str(text)
        for secret in self._secrets:
            out = out.replace(secret, "***")
        return out


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs secrets from fully formatted messages."""

    def __init__(self, redactor: Redactor):
        super().__init__()
        self._redactor = redactor

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        record.msg = self._redactor(message)
        record.args = None
        return True


def _route_key(path: str) -> str:
    route = path.split("?", 1)[0]
    route = _GUID_RE.sub("{id}", route)
    return _NUM_SEGMENT.sub("{id}", route)


def _error_details(resp: httpx.Response) -> tuple[str, str | None]:
    try:
        body = resp.json()
    except ValueError:
        text = resp.text.strip()
        return (text[:300] or resp.reason_phrase), None
    if isinstance(body, dict):
        return str(body.get("message") or body)[:500], body.get("typeKey")
    return str(body)[:300], None


class AzdoClient:
    def __init__(
        self,
        collection_url: str,
        pat: str,
        *,
        api_version: str = "7.0",
        verify: bool | str = True,
        timeout: float = 60.0,
        max_retries: int = 5,
        concurrency: int = 6,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not collection_url:
            raise ValueError("collection_url is required (e.g. https://azdo.example.com/DefaultCollection)")
        self.base = collection_url.rstrip("/")
        token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
        self.redact = Redactor([pat, token])
        self.api_version = api_version
        self.max_retries = max_retries
        self._sleep = sleep
        self._preview_routes: dict[str, str] = {}
        self._lock = threading.Lock()
        self.stats: Counter[str] = Counter()
        self._http = httpx.Client(
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "User-Agent": "azdo-analyzer/0.1 (read-only)",
            },
            verify=verify,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
            event_hooks={"request": [self._guard]},
        )

    # ------------------------------------------------------------------ guards
    @staticmethod
    def _guard(request: httpx.Request) -> None:
        if request.method.upper() != "GET":
            raise ReadOnlyViolation(f"Refusing {request.method} {request.url.path}: azdo-analyzer is read-only")

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "AzdoClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -------------------------------------------------------------- low level
    def url(self, path: str, project: str | None = None) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        prefix = f"{self.base}/{quote(project, safe='')}" if project else self.base
        return f"{prefix}/_apis/{path.lstrip('/')}"

    def request(self, method: str, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        if method.upper() != "GET":
            raise ReadOnlyViolation(f"Refusing {method} {url}: azdo-analyzer is read-only")
        attempt = 0
        while True:
            started = time.monotonic()
            try:
                resp = self._http.get(url, params=params)
            except ReadOnlyViolation:
                raise
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise AzdoHttpError(0, self.redact(url), self.redact(f"{type(exc).__name__}: {exc}")) from None
                self._backoff(attempt, None)
                attempt += 1
                continue
            elapsed = (time.monotonic() - started) * 1000
            self.stats["requests"] += 1
            log.debug("GET %s -> %s (%.0f ms)", self.redact(resp.request.url), resp.status_code, elapsed)
            if resp.status_code in _RETRY_STATUSES and attempt < self.max_retries:
                self.stats[f"retry_{resp.status_code}"] += 1
                self._backoff(attempt, resp.headers.get("Retry-After"))
                attempt += 1
                continue
            return resp

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay: float
        try:
            delay = float(retry_after) if retry_after is not None else -1
        except ValueError:
            delay = -1
        if delay < 0:
            delay = min(60.0, 2.0**attempt) + random.uniform(0, 0.5)
        self._sleep(delay)

    # ------------------------------------------------------------- high level
    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        project: str | None = None,
        api_version: str | None = None,
    ) -> httpx.Response:
        """GET an ``_apis`` path; falls back to ``-preview`` for preview-only routes."""
        url = self.url(path, project)
        route = _route_key(path)
        version = api_version or self._preview_routes.get(route) or self.api_version
        query = dict(params or {})
        query["api-version"] = version
        resp = self.request("GET", url, query)
        if resp.status_code == 400 and "-preview" not in version:
            message, type_key = _error_details(resp)
            if type_key == "VssInvalidPreviewVersionException" or "preview flag must be supplied" in message.lower():
                version = f"{version}-preview"
                with self._lock:
                    self._preview_routes[route] = version
                query["api-version"] = version
                resp = self.request("GET", url, query)
        self._raise_for_status(resp, url)
        return resp

    def _raise_for_status(self, resp: httpx.Response, url: str) -> None:
        content_type = resp.headers.get("content-type", "")
        if resp.status_code < 300 and "html" in content_type.lower():
            # AZDO answers some unauthenticated calls with 203 + an HTML sign-in page.
            raise AzdoHttpError(401, self.redact(url), "Received an HTML page instead of JSON (PAT invalid or expired?)")
        if 300 <= resp.status_code < 400:
            raise AzdoHttpError(
                resp.status_code, self.redact(url), f"Redirected to {resp.headers.get('location', '?')} (check collection_url)"
            )
        if resp.status_code >= 400:
            message, type_key = _error_details(resp)
            raise AzdoHttpError(resp.status_code, self.redact(url), self.redact(message), type_key)

    def get_json(self, path: str, params: dict[str, Any] | None = None, **kw: Any) -> Any:
        return self.get(path, params, **kw).json()

    def get_list(self, path: str, params: dict[str, Any] | None = None, **kw: Any) -> list:
        data = self.get_json(path, params, **kw)
        if isinstance(data, dict):
            value = data.get("value")
            return value if isinstance(value, list) else [data]
        return data if isinstance(data, list) else []

    def paged(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        project: str | None = None,
        api_version: str | None = None,
        mode: str = "token",
        page_size: int = 200,
        max_pages: int = 10_000,
    ) -> Iterator[dict]:
        """Iterate a list endpoint using continuation tokens or $top/$skip."""
        base = dict(params or {})
        if mode == "token":
            token: str | None = None
            for _ in range(max_pages):
                query = dict(base)
                if token:
                    query["continuationToken"] = token
                resp = self.get(path, query, project=project, api_version=api_version)
                data = resp.json()
                items = data.get("value", []) if isinstance(data, dict) else data
                yield from items or []
                new_token = resp.headers.get("x-ms-continuationtoken")
                if not new_token or new_token == token or not items:
                    return
                token = new_token
        elif mode == "skip":
            skip = 0
            for _ in range(max_pages):
                query = dict(base, **{"$top": page_size, "$skip": skip})
                data = self.get_json(path, query, project=project, api_version=api_version)
                items = data.get("value", []) if isinstance(data, dict) else data
                yield from items or []
                if len(items or []) < page_size:
                    return
                skip += page_size
        else:
            raise ValueError(f"unknown paging mode {mode!r}")

    # ---------------------------------------------------------------- doctor
    def detect_api_version(self, candidates: tuple[str, ...] = ("7.1", "7.0", "6.0", "5.1")) -> str:
        """Return the newest API version the server accepts."""
        last_error: AzdoHttpError | None = None
        for version in candidates:
            try:
                self.get("projects", {"$top": 1}, api_version=version)
                return version
            except AzdoHttpError as exc:
                last_error = exc
                if exc.status == 400 and (
                    exc.type_key == "VssVersionOutOfRangeException" or "out of range" in exc.message.lower()
                ):
                    continue
                raise
        raise last_error or AzdoHttpError(0, self.base, "no API version accepted")

    def connection_data(self) -> dict:
        """Who is the PAT authenticated as (connectionData has no api-version)."""
        url = self.url("connectionData")
        resp = self.request("GET", url, None)
        self._raise_for_status(resp, url)
        return resp.json()
