"""Loads the editable YAML rule files under rules/."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from azdo_analyzer.util import gitlab_key

SEVERITY_ORDER = {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class Rules:
    task_mapping: dict[str, dict[str, Any]] = field(default_factory=dict)
    predefined_exact: dict[str, dict[str, Any]] = field(default_factory=dict)
    predefined_env: dict[str, dict[str, Any]] = field(default_factory=dict)
    predefined_prefix: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    scan: dict[str, Any] = field(default_factory=dict)
    archetypes: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    findings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def task_hint(self, ref: str | None) -> dict[str, Any] | None:
        if not ref:
            return None
        key = ref.lower()
        if key in self.task_mapping:
            return self.task_mapping[key]
        return self.task_mapping.get(key.split("@", 1)[0])

    def predefined_hint(self, name: str) -> dict[str, Any] | None:
        if "." in name:
            hit = self.predefined_exact.get(name.lower())
            if hit:
                return {"name": name, **hit}
            for dotted, _env, mapping in self.predefined_prefix:
                if name.lower().startswith(dotted):
                    return {"name": name, **mapping}
            return None
        hit = self.predefined_env.get(name.upper())
        if hit:
            return {"name": name, **hit}
        for _dotted, env, mapping in self.predefined_prefix:
            if name.upper().startswith(env):
                return {"name": name, **mapping}
        return None

    def finding(self, fid: str) -> dict[str, Any]:
        return self.findings.get(fid, {"severity": "info", "title": fid, "remediation": ""})


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Rules file missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_rules(folder: Path) -> Rules:
    rules = Rules()
    mapping = _read(folder / "task_mapping.yaml").get("tasks") or {}
    rules.task_mapping = {str(k).lower(): (v or {}) for k, v in mapping.items()}
    for name, value in (_read(folder / "predefined_vars.yaml").get("variables") or {}).items():
        value = value or {}
        if name.endswith(".*"):
            dotted = name[:-1].lower()
            rules.predefined_prefix.append((dotted, gitlab_key(name[:-2]) + "_", value))
        else:
            rules.predefined_exact[name.lower()] = value
            rules.predefined_env[gitlab_key(name)] = value
    rules.scan = _read(folder / "scan_patterns.yaml")
    rules.archetypes = _read(folder / "archetypes.yaml")
    rules.scoring = _read(folder / "scoring.yaml")
    rules.findings = _read(folder / "findings.yaml").get("findings") or {}
    return rules
