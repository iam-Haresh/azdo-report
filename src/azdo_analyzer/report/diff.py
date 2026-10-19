"""Run-to-run drift: pipelines/repos added, removed or changed since the previous run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from azdo_analyzer.analyze import AnalysisResult
from azdo_analyzer.cache import safe_name
from azdo_analyzer.util import short_hash

_VOLATILE_FLAGS = {"timeline_checked", "timeline_only_tasks", "static_only_tasks", "agents_seen"}


def _fingerprint(data: dict[str, Any]) -> str:
    clean = dict(data)
    clean["flags"] = {k: v for k, v in (clean.get("flags") or {}).items() if k not in _VOLATILE_FLAGS}
    return short_hash(json.dumps(clean, sort_keys=True, default=str))


def current_index(result: AnalysisResult) -> dict[str, dict[str, Any]]:
    out = {}
    for project in result.projects:
        pipelines = {r.pipeline.key: {"name": r.pipeline.name, "kind": r.pipeline.kind, "hash": _fingerprint(r.pipeline.to_dict())}
                     for r in project.pipelines.values()}
        repos = {r.repo["id"]: {"name": r.name} for r in project.repos}
        out[project.name] = {"pipelines": pipelines, "repos": repos}
    return out


def write_diff(result: AnalysisResult, model_dir: Path, target: Path) -> Path:
    lines = ["# Changes since the previous run", ""]
    index = current_index(result)
    for project, current in index.items():
        path = model_dir / safe_name(project) / "index.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        lines.append(f"## {project}")
        lines.append("")
        if previous is None:
            lines += ["_First run for this project - nothing to compare._", ""]
        else:
            changes = []
            for kind in ("pipelines", "repos"):
                old, new = previous.get(kind, {}), current[kind]
                for key in sorted(set(new) - set(old)):
                    changes.append(f"- **added** {kind[:-1]}: {new[key]['name']}")
                for key in sorted(set(old) - set(new)):
                    changes.append(f"- **removed** {kind[:-1]}: {old[key]['name']}")
                if kind == "pipelines":
                    for key in sorted(set(old) & set(new)):
                        if old[key].get("hash") != new[key].get("hash"):
                            changes.append(f"- **changed** pipeline: {new[key]['name']}")
            lines += changes or ["_No changes._"]
            lines.append("")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=1), encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
