"""On-disk JSON cache for raw API responses (enables --offline re-runs)."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(value: Any) -> str:
    text = _UNSAFE.sub("_", str(value)).strip().rstrip(".")
    return text or "_"


class RawStore:
    """``out/raw/<scope>/...`` JSON files. ``scope`` is ``_org`` or a project name."""

    MISSING = {"__status__": 404}

    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.Lock()

    def path(self, *parts: Any) -> Path:
        return self.root.joinpath(*(safe_name(p) for p in parts))

    def has(self, *parts: Any) -> bool:
        return self.path(*parts).exists()

    def read(self, *parts: Any, default: Any = None) -> Any:
        target = self.path(*parts)
        if not target.exists():
            return default
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("__status__") == 404:
            return default
        return data

    def is_missing_marker(self, *parts: Any) -> bool:
        target = self.path(*parts)
        if not target.exists():
            return False
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            return False
        return isinstance(data, dict) and data.get("__status__") == 404

    def write(self, data: Any, *parts: Any) -> Path:
        target = self.path(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False), encoding="utf-8")
        os.replace(tmp, target)
        return target

    def scopes(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and p.name != "_org")
