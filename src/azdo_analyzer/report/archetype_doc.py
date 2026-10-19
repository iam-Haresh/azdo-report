"""Renders docs/reports/archetype-values.md from rules/archetypes.yaml.

Regenerate after editing the rules:  python -m azdo_analyzer.report.archetype_doc
"""

from __future__ import annotations

import sys
from typing import Any

import yaml

from azdo_analyzer.analyze.archetype import DIMENSIONS, compile_archetypes
from azdo_analyzer.config import PROJECT_ROOT

DOC_PATH = PROJECT_ROOT / "docs" / "reports" / "archetype-values.md"
RULES_PATH = PROJECT_ROOT / "rules" / "archetypes.yaml"
MAX_REGEX = 200

INTRO = """\
# Archetype values

[Report guide](README.md) › Archetype values

Every value the tool can report in the Stack, Build tools, Test & scan tools, Deploy targets, Artifacts and Markers columns,
how each one is found, and the named archetypes with their proposed templates. How the values combine into the archetype
key is explained in [Concepts](concepts.md#archetype-key).

This page is generated from `rules/archetypes.yaml`. After editing the rules, regenerate it with
`python -m azdo_analyzer.report.archetype_doc`.

**Found from** lists the signals. Any one of them is enough:
- *files*: file names anywhere in the repo (deep runs), not case-sensitive. "with content check" means one of those files
  must also contain the regex shown.
- *tasks*, *task inputs*: tasks in the build pipelines and classic releases that use the repo.
- *commands*, *script regex*: inline scripts and task inputs of those pipelines, and repo scripts they call by name.
- *connection type*: a service connection of that type is used. *markers*: a marker below was found.
"""


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _code(values: list[Any], limit: int = 12) -> str:
    items = [f"`{v}`" for v in values[:limit]]
    if len(values) > limit:
        items.append(f"… (+{len(values) - limit})")
    return ", ".join(items)


def _regex(pattern: str | None) -> str:
    if not pattern:
        return ""
    return f" with content check `{pattern}`" if len(pattern) <= MAX_REGEX else " with content check"


def _found_from(spec: dict[str, Any]) -> str:
    parts = []
    if spec.get("files"):
        parts.append("files " + _code(spec["files"]) + _regex(spec.get("content_regex")))
    for alt in spec.get("match") or []:
        parts.append("files " + _code(alt["files"]) + _regex(alt.get("content_regex")))
    if spec.get("markers"):
        parts.append("markers " + _code(spec["markers"]))
    if spec.get("tasks"):
        parts.append("tasks " + _code(spec["tasks"]))
    for task, inputs in (spec.get("task_inputs") or {}).items():
        conditions = "; ".join(f"{k} = {' / '.join(str(v) for v in (vals if isinstance(vals, list) else [vals]))}" for k, vals in inputs.items())
        parts.append(f"task `{task}` with {conditions}")
    if spec.get("commands"):
        parts.append("commands " + _code(spec["commands"]))
    if spec.get("script_regex"):
        regex = spec["script_regex"]
        parts.append(f"script regex `{regex}`" if len(regex) <= MAX_REGEX else "a script regex")
    if spec.get("endpoint_types"):
        parts.append("connection type " + _code(spec["endpoint_types"]))
    if spec.get("deployment_group"):
        parts.append("deployment-group jobs")
    return "; ".join(parts) or "set by the tool"


def _notes(section: str, spec: dict[str, Any]) -> str:
    notes = []
    if spec.get("windows"):
        notes.append("Windows runner")
    if spec.get("macos"):
        notes.append("macOS runner")
    if spec.get("fallback"):
        notes.append("only when no other stack is found")
    if spec.get("replaces"):
        notes.append("replaces " + _code(spec["replaces"]))
    if spec.get("tools"):
        notes.append("built with " + ", ".join(spec["tools"]) + f" (assumed: {spec['tools'][0]})")
    if spec.get("stack"):
        notes.append(f"stack without repo files: `{spec['stack']}`")
    return "; ".join(notes)


def render(raw: dict[str, Any]) -> str:
    compile_archetypes(raw)  # validate first
    lines = [INTRO]
    for section, _, title, _ in DIMENSIONS:
        items = raw.get(section) or {}
        lines += [f"## {title}", "", f"{len(items)} values.", "", "| Value | What it is | Found from | Notes |", "|---|---|---|---|"]
        for rid, spec in items.items():
            spec = spec or {}
            lines.append(f"| `{rid}` | {_cell(str(spec.get('label') or rid))} | {_cell(_found_from(spec))} | {_cell(_notes(section, spec))} |")
        lines.append("")
    named = raw.get("named") or []
    lines += ["## Named archetypes", "",
              f"{len(named)} entries, in rule order. A condition lists ids that must all be present; `none` means that dimension is empty.",
              "How a repo's names are chosen: [Concepts](concepts.md#named-archetypes).", "",
              "| Name | Proposed template | Conditions |", "|---|---|---|"]
    keys = [(key, title) for _, key, title, _ in DIMENSIONS]
    for entry in named:
        conditions = []
        for key, title in keys:
            if key in entry:
                values = entry[key] if isinstance(entry[key], list) else [entry[key]]
                conditions.append(f"{title}: " + " + ".join(f"`{v}`" for v in values))
        if entry.get("also_covers"):
            conditions.append("also covers " + ", ".join(f"`{v}`" for v in entry["also_covers"]))
        template = f"`{entry['template']}`" if entry.get("template") else ""
        lines.append(f"| {_cell(entry['name'])} | {template} | {_cell('; '.join(conditions))} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    raw = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    DOC_PATH.write_text(render(raw), encoding="utf-8")
    print(f"wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
