"""Archetype detection and pipeline fingerprints.

A repo's archetype has six dimensions: stacks, build tools, test & scan tools, deploy targets, artifacts and markers.
Each one can hold several values. The rules, and the named archetypes, are in rules/archetypes.yaml.
"""

from __future__ import annotations

import bisect
import fnmatch
import itertools
import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Iterable

from azdo_analyzer.collect.content import SKIP_DIRS
from azdo_analyzer.model import Pipeline
from azdo_analyzer.util import short_hash

# (rules section, condition key in `named:`, report title, short label)
DIMENSIONS: tuple[tuple[str, str, str, str], ...] = (
    ("stacks", "stack", "Stack", "stack"),
    ("build_tools", "build", "Build tools", "build"),
    ("quality_tools", "quality", "Test & scan tools", "test/scan"),
    ("deploy_targets", "deploy", "Deploy targets", "deploy"),
    ("artifacts", "artifact", "Artifacts", "artifact"),
    ("markers", "marker", "Markers", "marker"),
)
SECTIONS = tuple(d[0] for d in DIMENSIONS)
PIPELINE_SECTIONS = ("build_tools", "quality_tools", "deploy_targets", "artifacts")  # what one pipeline or release shows itself
TEMPLATE_STACK = "azdo-yaml-templates"
MAX_CONTENT_READS = 20  # files read per content check (shallowest first)
MAX_SCRIPT_FILES = 20  # repo script files searched because a pipeline calls them
MAX_EVIDENCE = 3
UNSET = "(unset)"

_COMMON_KEYS = {"label", "files", "content_regex", "match", "tasks", "task_inputs", "commands", "script_regex",
                "endpoint_types", "deployment_group", "markers", "replaces"}
_SECTION_KEYS = {
    "stacks": _COMMON_KEYS | {"fallback", "windows", "macos", "tools"},
    "build_tools": _COMMON_KEYS | {"stack"},
    "quality_tools": _COMMON_KEYS,
    "deploy_targets": _COMMON_KEYS,
    "artifacts": _COMMON_KEYS,
    "markers": {"label", "files", "content_regex", "match"},
}
_NAMED_KEYS = {"name", "template", "also_covers"} | {d[1] for d in DIMENSIONS}
_SCRIPT_FILE = re.compile(r"[\w.-]+\.(?:sh|bash|ps1|psm1|bat|cmd|py|groovy)\b")
_PROSE = re.compile(r"^\s*(?:#|//|::|rem\b|echo\b|printf\b|write-(?:host|output|verbose|information|warning|debug)\b)", re.I)
_CMD_PREFIX = r"(?:^|[\s;&|(`'\"/\\])"
_CMD_SUFFIX = r"(?=[\s;&|)`'\"]|$)"
_CMD_FLAGS = r"(?:\s+-{1,2}[\w.:=/@-]+(?:\s+[^-\s]\S*)??)*"
_CMD_EXE = r"(?:\.exe|\.cmd|\.bat|\.sh|\.ps1)?"
_TOKENS = re.compile(r"[\s,;]+")


class ArchetypeRulesError(ValueError):
    """rules/archetypes.yaml is not valid."""


# ----------------------------------------------------------------------------------------------- compiled rules
@dataclass
class FileSignal:
    patterns: list[str]
    regex: re.Pattern[str] | None = None


@dataclass
class Rule:
    section: str
    id: str
    label: str
    files: list[FileSignal] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    tasks: set[str] = field(default_factory=set)
    task_inputs: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    commands: re.Pattern[str] | None = None
    script: re.Pattern[str] | None = None
    endpoint_types: set[str] = field(default_factory=set)
    deployment_group: bool = False
    replaces: list[str] = field(default_factory=list)
    fallback: bool = False
    windows: bool = False
    macos: bool = False
    tools: list[str] = field(default_factory=list)
    stack: str | None = None


@dataclass
class NamedEntry:
    index: int
    name: str
    template: str | None
    conditions: dict[str, list[str]]  # section -> required ids, or ["none"]
    also_covers: list[str] = field(default_factory=list)

    @property
    def stacks(self) -> list[str]:
        return self.conditions["stacks"]

    @property
    def generic(self) -> bool:
        return len(self.conditions) == 1

    def rank(self) -> tuple[int, int, int]:
        others = sum(len(v) for section, v in self.conditions.items() if section != "stacks")
        return (-len(self.stacks), -others, self.index)

    def matches(self, profile: RepoProfile) -> bool:
        for section, wanted in self.conditions.items():
            have = profile.values(section)
            if wanted == ["none"]:
                if have:
                    return False
            elif not all(w in have for w in wanted):
                return False
        return True


@dataclass
class ArchetypeRules:
    rules: dict[str, dict[str, Rule]]
    named: list[NamedEntry]

    def label(self, section: str, value: str) -> str:
        rule = self.rules[section].get(value)
        return rule.label if rule else value

    def ordered(self, section: str, values: Iterable[str]) -> list[str]:
        order = {rid: i for i, rid in enumerate(self.rules[section])}
        return sorted(set(values), key=lambda v: (order.get(v, len(order)), v))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _command_regex(phrase: str) -> str:
    """'kubectl apply' -> the command at a command position, flags allowed between the words."""
    words = phrase.split()
    body = re.escape(words[0]) + _CMD_EXE + "".join(_CMD_FLAGS + r"\s+" + re.escape(w) for w in words[1:])
    return _CMD_PREFIX + body + _CMD_SUFFIX


def compile_archetypes(raw: dict[str, Any]) -> ArchetypeRules:
    """Validate rules/archetypes.yaml and compile its patterns. Raises ArchetypeRulesError."""

    def fail(where: str, problem: str) -> None:
        raise ArchetypeRulesError(f"archetypes.yaml: {where}: {problem}")

    def strings(value: Any, where: str) -> list[str]:
        items = _as_list(value)
        if any(isinstance(i, (dict, list)) for i in items):
            fail(where, "expected a list of names")
        return [str(i) for i in items]

    def regex(pattern: Any, where: str) -> re.Pattern[str] | None:
        if pattern in (None, ""):
            return None
        try:
            return re.compile(str(pattern), re.I | re.M)
        except re.error as exc:
            fail(where, f"invalid regex: {exc}")
        return None

    def compile_rule(section: str, rid: str, spec: Any) -> Rule:
        where = f"{section}.{rid}"
        if not isinstance(spec, dict):
            fail(where, "expected a mapping of keys (label, files, tasks, ...)")
        unknown = set(spec) - _SECTION_KEYS[section]
        if unknown:
            fail(where, f"unknown key(s) {sorted(unknown)}; allowed here: {', '.join(sorted(_SECTION_KEYS[section]))}")
        rule = Rule(section=section, id=rid, label=str(spec.get("label") or rid))
        if spec.get("files"):
            rule.files.append(FileSignal(strings(spec["files"], f"{where}.files"), regex(spec.get("content_regex"), f"{where}.content_regex")))
        elif spec.get("content_regex"):
            fail(where, "content_regex needs files")
        for j, alt in enumerate(_as_list(spec.get("match"))):
            if not isinstance(alt, dict) or not alt.get("files") or set(alt) - {"files", "content_regex"}:
                fail(f"{where}.match[{j}]", "each alternative is {files: [...], content_regex: '...'} (content_regex optional)")
            rule.files.append(FileSignal(strings(alt["files"], f"{where}.match[{j}].files"), regex(alt.get("content_regex"), f"{where}.match[{j}]")))
        rule.markers = strings(spec.get("markers"), f"{where}.markers")
        rule.tasks = {t.lower() for t in strings(spec.get("tasks"), f"{where}.tasks")}
        task_inputs = spec.get("task_inputs") or {}
        if not isinstance(task_inputs, dict):
            fail(f"{where}.task_inputs", "expected {Task: {input: [values]}}")
        for task, inputs in task_inputs.items():
            if not isinstance(inputs, dict):
                fail(f"{where}.task_inputs.{task}", "expected {input: [values]}")
            rule.task_inputs[str(task).lower()] = {str(k).lower(): [str(v).lower() for v in _as_list(vals)] for k, vals in inputs.items()}
        commands = strings(spec.get("commands"), f"{where}.commands")
        if any(not c.strip() for c in commands):
            fail(f"{where}.commands", "empty command")
        if commands:
            rule.commands = re.compile("|".join(_command_regex(c) for c in commands), re.I | re.M)
        rule.script = regex(spec.get("script_regex"), f"{where}.script_regex")
        rule.endpoint_types = {e.lower() for e in strings(spec.get("endpoint_types"), f"{where}.endpoint_types")}
        rule.deployment_group = bool(spec.get("deployment_group"))
        rule.replaces = strings(spec.get("replaces"), f"{where}.replaces")
        rule.fallback, rule.windows, rule.macos = bool(spec.get("fallback")), bool(spec.get("windows")), bool(spec.get("macos"))
        rule.tools = strings(spec.get("tools"), f"{where}.tools")
        rule.stack = str(spec["stack"]) if spec.get("stack") else None
        return rule

    if not isinstance(raw, dict):
        fail("top level", "expected a mapping")
    unknown_sections = set(raw) - set(SECTIONS) - {"named"}
    if unknown_sections:
        fail("top level", f"unknown section(s) {sorted(unknown_sections)}. The file format changed: start from the "
                          f"rules/archetypes.yaml shipped with the tool")
    rules: dict[str, dict[str, Rule]] = {}
    for section in SECTIONS:
        body = raw.get(section) or {}
        if not isinstance(body, dict):
            fail(section, "expected a mapping of id -> rule. The file format changed: start from the rules/archetypes.yaml "
                          "shipped with the tool")
        rules[section] = {str(rid): compile_rule(section, str(rid), spec or {}) for rid, spec in body.items()}

    for section, items in rules.items():
        for rule in items.values():
            where = f"{section}.{rule.id}"
            for other in rule.replaces:
                if other not in items:
                    fail(f"{where}.replaces", f"unknown {section} id {other!r}")
            for marker in rule.markers:
                if marker not in rules["markers"]:
                    fail(f"{where}.markers", f"unknown marker {marker!r}")
            for tool in rule.tools:
                if tool not in rules["build_tools"]:
                    fail(f"{where}.tools", f"unknown build tool {tool!r}")
            if rule.stack and rule.stack not in rules["stacks"]:
                fail(f"{where}.stack", f"unknown stack {rule.stack!r}")

    named: list[NamedEntry] = []
    for i, spec in enumerate(_as_list(raw.get("named"))):
        where = f"named[{i}]"
        if not isinstance(spec, dict):
            fail(where, "expected a mapping")
        unknown = set(spec) - _NAMED_KEYS
        if unknown:
            fail(where, f"unknown key(s) {sorted(unknown)}; allowed: {', '.join(sorted(_NAMED_KEYS))}")
        if not spec.get("name"):
            fail(where, "name is required")
        where = f"named[{i}] ({spec['name']})"
        if not spec.get("stack"):
            fail(where, "stack is required")
        conditions: dict[str, list[str]] = {}
        for section, key, _, _ in DIMENSIONS:
            if key not in spec:
                continue
            values = [str(v) for v in _as_list(spec[key])]
            if values == ["none"] and section != "stacks":
                conditions[section] = values
                continue
            for value in values:
                if value not in rules[section]:
                    fail(f"{where}.{key}", f"unknown {section} id {value!r}")
            conditions[section] = values
        also = [str(v) for v in _as_list(spec.get("also_covers"))]
        for value in also:
            if value not in rules["stacks"]:
                fail(f"{where}.also_covers", f"unknown stack {value!r}")
        named.append(NamedEntry(i, str(spec["name"]), str(spec["template"]) if spec.get("template") else None, conditions, also))
    return ArchetypeRules(rules, named)


# ------------------------------------------------------------------------------------------------- repo profile
@dataclass
class RepoProfile:
    stacks: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)
    quality_tools: list[str] = field(default_factory=list)
    deploy_targets: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    windows: bool = False
    macos: bool = False
    names: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    evidence: dict[str, list[str]] = field(default_factory=dict)  # "section:value" -> why it was found
    source: str = "files"  # files | pipelines | none

    def values(self, section: str) -> list[str]:
        return getattr(self, section)

    @property
    def stack(self) -> str:
        return ", ".join(self.stacks) or "unknown"

    @property
    def build_tool(self) -> str:
        return ", ".join(self.build_tools) or "none"

    @property
    def deploy(self) -> str:
        return ", ".join(self.deploy_targets) or "none"

    @property
    def artifact(self) -> str:
        return ", ".join(self.artifacts) or "none"

    @property
    def key(self) -> str:
        return f"{self.stack} | {self.build_tool} | {self.deploy} | {self.artifact}"

    @property
    def name(self) -> str:
        return ", ".join(self.names) or "custom"

    @property
    def template(self) -> str | None:
        return ", ".join(self.templates) or None


@lru_cache(maxsize=4096)
def _glob(pattern: str) -> re.Pattern[str]:
    return re.compile(fnmatch.translate(pattern))


class FileIndex:
    """Case-insensitive file-name matching over a repo listing, fast enough for very large repos."""

    def __init__(self, files: Iterable[str]):
        self.paths = sorted({f.strip("/") for f in files if f and not _skipped(f)}, key=lambda p: (p.count("/"), p.lower()))
        self._lower = {p: p.lower() for p in self.paths}
        self._by_name: dict[str, list[str]] = defaultdict(list)
        for path in self.paths:
            self._by_name[posixpath.basename(self._lower[path])].append(path)
        self._names = sorted(self._by_name)
        self._by_ext: dict[str, list[str]] = defaultdict(list)
        for name in self._names:
            if "." in name:
                self._by_ext[name.rsplit(".", 1)[1]].append(name)
        self._cache: dict[str, list[str]] = {}

    def match(self, pattern: str) -> list[str]:
        pat = pattern.lower().strip("/")
        if pat not in self._cache:
            self._cache[pat] = self._path_match(pat) if "/" in pat else [p for n in self._name_match(pat) for p in self._by_name[n]]
        return self._cache[pat]

    def _name_match(self, pat: str) -> list[str]:
        """Unique lower-case file names matching a name pattern."""
        if not _has_wildcard(pat):
            return [pat] if pat in self._by_name else []
        if pat.startswith("*") and not _has_wildcard(pat[1:]) and "." in pat[1:]:  # *.csproj, *.template.yaml
            suffix = pat[1:]
            return [n for n in self._by_ext.get(suffix.rsplit(".", 1)[1], []) if n.endswith(suffix)]
        rx = _glob(pat)
        prefix = re.split(r"[*?\[]", pat, maxsplit=1)[0]
        if prefix:  # docker-compose*.yml, Dockerfile.*: scan only the names with that prefix
            start = bisect.bisect_left(self._names, prefix)
            candidates = itertools.takewhile(lambda n: n.startswith(prefix), self._names[start:])
        else:
            candidates = iter(self._names)
        return [n for n in candidates if rx.match(n)]

    def _path_match(self, pat: str) -> list[str]:
        rx = _glob(pat)
        last = pat.rsplit("/", 1)[1]
        simple = not _has_wildcard(last) or (last.startswith("*") and not _has_wildcard(last[1:]))
        if simple and last != "*":  # the file name must match the last part of the pattern: test only those paths
            candidates = [p for n in self._name_match(last) for p in self._by_name[n]]
        else:
            candidates = self.paths
        return [p for p in candidates if rx.match(self._lower[p])]

    def match_any(self, patterns: Iterable[str]) -> list[str]:
        seen: dict[str, None] = {}
        for pattern in patterns:
            for path in self.match(pattern):
                seen.setdefault(path)
        return sorted(seen, key=lambda p: (p.count("/"), p.lower()))


def _has_wildcard(pattern: str) -> bool:
    return any(c in pattern for c in "*?[")


def _skipped(path: str) -> bool:
    return any(part.lower() in SKIP_DIRS for part in path.strip("/").split("/")[:-1])


@dataclass
class _Source:
    """One pipeline (or a repo script that a pipeline calls) reduced to what the rules look at."""

    label: str
    text: str = ""  # inline scripts and task inputs
    commands_text: str = ""  # the same without echo / Write-Host lines and comments
    tasks: dict[str, str] = field(default_factory=dict)  # lower-case name -> "Name@major"
    inputs: list[tuple[str, str, dict[str, str]]] = field(default_factory=list)  # (name, ref, inputs)
    endpoint_types: set[str] = field(default_factory=set)
    deployment_group: bool = False


def _commands_text(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _PROSE.match(line))


def _pipeline_source(pipeline: Pipeline, endpoint_types: dict[str, str]) -> _Source:
    kind = "release" if pipeline.kind == "classic_release" else "pipeline"
    src = _Source(label=f"{kind} {pipeline.name}")
    lines: list[str] = []
    for step in pipeline.all_steps():
        inputs = step.inputs or {}
        if step.task:
            name = step.task.split("@", 1)[0].lower()
            src.tasks.setdefault(name, step.task)
            src.inputs.append((name, step.task, {str(k).lower(): "" if v is None else str(v) for k, v in inputs.items()}))
        if step.script:
            lines.append(step.script)
        lines.extend(v for v in inputs.values() if isinstance(v, str))
    src.text = "\n".join(lines)
    src.commands_text = _commands_text(src.text)
    src.endpoint_types = {endpoint_types.get(r.id or "", "") for r in pipeline.refs("service_connection")} - {""}
    src.deployment_group = any(job.kind == "deployment_group" for job in pipeline.all_jobs())
    return src


def _script_file_sources(index: FileIndex, read: Callable[[str], str | None], sources: list[_Source]) -> list[_Source]:
    """Repo script files that a pipeline calls by name, e.g. ./ci/deploy.sh."""
    called: dict[str, str] = {}
    for src in sources:
        for name in _SCRIPT_FILE.findall(src.text.lower()):
            called.setdefault(name, src.label)
    out: list[_Source] = []
    for path in index.paths:
        caller = called.get(posixpath.basename(path).lower())
        if caller is None:
            continue
        text = read(path)
        if text:
            out.append(_Source(label=f"{path} (called by {caller})", text=text, commands_text=_commands_text(text)))
        if len(out) >= MAX_SCRIPT_FILES:
            break
    return out


def _snippet(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _line_at(text: str, m: re.Match[str]) -> str:
    """The script line holding a match, shortened around it."""
    pos = m.start() + len(m.group(0)) - len(m.group(0).lstrip())  # the command prefix may have matched the line break
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", m.end())
    line = text[start:end if end != -1 else len(text)].strip()
    if len(line) > 80:
        offset = max(0, m.start() - start - 20)
        line = ("…" if offset else "") + line[offset:offset + 79].strip()
    return _snippet(line, 80)


def _input_hit(spec: dict[str, list[str]], inputs: dict[str, str]) -> str | None:
    for key, wanted in spec.items():
        value = inputs.get(key, "").strip()
        low = value.lower()
        if not low:
            if UNSET in wanted:
                return f"{key} not set"
            continue
        tokens = set(_TOKENS.split(low))
        if any(w != UNSET and (w == low or w in tokens) for w in wanted):
            return f"{key}={_snippet(value, 40)}"
    return None


class _Detector:
    def __init__(self, files: list[str] | FileIndex, read: Callable[[str], str | None], pipelines: list[Pipeline],
                 endpoint_types: dict[str, str]):
        self.index = files if isinstance(files, FileIndex) else FileIndex(files)
        self._read = read
        self._texts: dict[str, str | None] = {}
        self.sources = [_pipeline_source(p, endpoint_types) for p in pipelines]
        self.sources += _script_file_sources(self.index, self.read, self.sources)

    def read(self, path: str) -> str | None:
        if path not in self._texts:
            self._texts[path] = self._read(path)
        return self._texts[path]

    def evidence(self, rule: Rule, markers: list[str]) -> list[str]:
        found = [e for e in (self._files(rule), self._markers(rule, markers), self._pipelines(rule)) if e]
        return found[:MAX_EVIDENCE]

    def _files(self, rule: Rule) -> str | None:
        for signal in rule.files:
            hits = self.index.match_any(signal.patterns)
            if not hits:
                continue
            if signal.regex is None:
                return hits[0]
            for path in hits[:MAX_CONTENT_READS]:
                text = self.read(path)
                m = signal.regex.search(text) if text else None
                if m:
                    return f"{path} ({_snippet(m.group(0))})"
        return None

    @staticmethod
    def _markers(rule: Rule, markers: list[str]) -> str | None:
        hit = next((m for m in rule.markers if m in markers), None)
        return f"marker {hit}" if hit else None

    def _pipelines(self, rule: Rule) -> str | None:
        for src in self.sources:
            for name, ref in src.tasks.items():
                if name in rule.tasks:
                    return f"task {ref} in {src.label}"
            if rule.task_inputs:
                for name, ref, inputs in src.inputs:
                    spec = rule.task_inputs.get(name)
                    hit = _input_hit(spec, inputs) if spec else None
                    if hit:
                        return f"task {ref} {hit} in {src.label}"
            common = sorted(rule.endpoint_types & src.endpoint_types)
            if common:
                return f"{common[0]} service connection in {src.label}"
            if rule.deployment_group and src.deployment_group:
                return f"deployment-group job in {src.label}"
            if rule.commands is not None:
                m = rule.commands.search(src.commands_text)
                if m:
                    return f"'{_line_at(src.commands_text, m)}' in {src.label}"
            if rule.script is not None:
                m = rule.script.search(src.text)
                if m:
                    return f"'{_line_at(src.text, m)}' in {src.label}"
        return None


def _resolve(ar: ArchetypeRules, section: str, found: Iterable[str]) -> list[str]:
    """Apply `replaces` and (stacks) `fallback`; return the ids in rule order."""
    rules = ar.rules[section]
    found = ar.ordered(section, found)
    replaced = {r for f in found for r in rules[f].replaces}
    kept = [f for f in found if f not in replaced]
    if section == "stacks" and any(not rules[f].fallback for f in kept):
        kept = [f for f in kept if not rules[f].fallback]
    return kept


def profile_repo(
    files: list[str] | FileIndex,
    read: Callable[[str], str | None],
    pipelines: list[Pipeline],
    endpoint_types: dict[str, str],
    rules: Any,
) -> RepoProfile:
    """Classify a repo from its files (when available) and the pipelines/releases that use it."""
    ar: ArchetypeRules = rules.archetype_rules
    det = _Detector(files, read, pipelines, endpoint_types)
    profile = RepoProfile(source="files" if det.index.paths else ("pipelines" if pipelines else "none"))
    found: dict[str, dict[str, list[str]]] = {}

    def detect(section: str) -> dict[str, list[str]]:
        hits: dict[str, list[str]] = {}
        for rid, rule in ar.rules[section].items():
            evidence = det.evidence(rule, profile.markers)
            if evidence:
                hits[rid] = evidence
        found[section] = hits
        return hits

    profile.markers = _resolve(ar, "markers", detect("markers"))
    stacks = detect("stacks")
    tools = detect("build_tools")
    if not any(not ar.rules["stacks"][s].fallback for s in _resolve(ar, "stacks", stacks)):
        for tool in ar.ordered("build_tools", tools):  # no files to go by: infer the stack from the build tools
            stack = ar.rules["build_tools"][tool].stack
            if stack:
                stacks.setdefault(stack, []).append(f"inferred from build tool {tool}")
    profile.stacks = _resolve(ar, "stacks", stacks)
    for stack in profile.stacks:
        candidates = ar.rules["stacks"][stack].tools
        if candidates and not any(t in tools for t in candidates):
            tools.setdefault(candidates[0], []).append(f"assumed for stack {stack}: no build step for it found")
    profile.build_tools = _resolve(ar, "build_tools", tools)
    for section in ("quality_tools", "deploy_targets", "artifacts"):
        setattr(profile, section, _resolve(ar, section, detect(section)))
    for section in SECTIONS:
        for value in profile.values(section):
            profile.evidence[f"{section}:{value}"] = found[section][value]
    stack_rules = [ar.rules["stacks"][s] for s in profile.stacks]
    profile.windows = any(r.windows for r in stack_rules)
    profile.macos = any(r.macos for r in stack_rules)
    assign_names(profile, ar)
    return profile


def profile_pipeline(
    pipeline: Pipeline,
    endpoint_types: dict[str, str],
    rules: Any,
    files: list[str] | FileIndex | None = None,
    read: Callable[[str], str | None] | None = None,
) -> RepoProfile:
    """What one build pipeline or release does, from its own tasks, task inputs, scripts, connections and jobs.

    Repo scripts it calls by name are searched when the repo's files are given. Stacks and markers describe repos,
    so they stay empty here; repo file signals (lock files, Dockerfile, ...) are not used either.
    """
    ar: ArchetypeRules = rules.archetype_rules
    det = _Detector(files if files is not None else [], read or (lambda rel: None), [pipeline], endpoint_types)
    profile = RepoProfile(source="pipelines")
    for section in PIPELINE_SECTIONS:
        hits = {rid: [found] for rid, rule in ar.rules[section].items() if (found := det._pipelines(rule))}
        setattr(profile, section, _resolve(ar, section, hits))
        for value in profile.values(section):
            profile.evidence[f"{section}:{value}"] = hits[value]
    return profile


def mark_template_repo(profile: RepoProfile, ar: ArchetypeRules) -> bool:
    """A repo that only holds YAML templates for other pipelines (no own stack): give it the template-repo stack."""
    if any(not ar.rules["stacks"][s].fallback for s in profile.stacks):
        return False
    profile.stacks = [TEMPLATE_STACK]
    profile.evidence = {k: v for k, v in profile.evidence.items() if not k.startswith("stacks:")}
    profile.evidence[f"stacks:{TEMPLATE_STACK}"] = ["used for YAML templates or checkouts by other pipelines"]
    profile.windows = profile.macos = False
    assign_names(profile, ar)
    return True


def assign_names(profile: RepoProfile, ar: ArchetypeRules) -> None:
    """For each stack, the most specific matching `named:` entry (see the comments in archetypes.yaml)."""
    matched = [e for e in ar.named if e.matches(profile)]
    claimed = {s for e in matched for s in e.also_covers if s in profile.stacks}
    matched = [e for e in matched if not (e.generic and set(e.stacks) <= claimed)]
    covered: set[str] = set()
    chosen: list[NamedEntry] = []
    for entry in sorted(matched, key=NamedEntry.rank):
        if covered & set(entry.stacks):
            continue
        chosen.append(entry)
        covered.update(entry.stacks)
    order = {s: i for i, s in enumerate(profile.stacks)}
    chosen.sort(key=lambda e: min(order.get(s, len(order)) for s in e.stacks))
    profile.names = [e.name for e in chosen]
    profile.templates = list(dict.fromkeys(e.template for e in chosen if e.template))


# ------------------------------------------------------------------------------------------ pipeline clones
_BOILERPLATE = {"checkout", "download", "publish"}


def fingerprint(pipeline: Pipeline) -> str | None:
    refs = [s.task for s in pipeline.all_steps() if s.task and s.task not in _BOILERPLATE]
    if len(refs) < 2:
        return None
    return short_hash(pipeline.kind, *refs)


def clone_clusters(pipelines: list[Pipeline], threshold: float = 0.8) -> list[dict[str, Any]]:
    """Exact clones (same fingerprint) and near clones (Jaccard on task sets >= threshold)."""
    exact: dict[str, list[Pipeline]] = defaultdict(list)
    for p in pipelines:
        fp = fingerprint(p)
        if fp:
            exact[fp].append(p)
    clusters = [
        {"type": "identical", "fingerprint": fp, "pipelines": [f"{p.project}/{p.name}" for p in items], "tasks": " > ".join(items[0].task_refs())}
        for fp, items in exact.items()
        if len(items) > 1
    ]
    singles = [items[0] for items in exact.values() if len(items) == 1]
    sets = [(p, set(p.task_refs())) for p in singles]
    used: set[str] = set()
    for i, (p, s) in enumerate(sets):
        if p.key in used or not s:
            continue
        group = [p]
        for q, t in sets[i + 1:]:
            if q.key in used or not t or p.kind != q.kind:
                continue
            if len(s & t) / len(s | t) >= threshold:
                group.append(q)
                used.add(q.key)
        if len(group) > 1:
            used.add(p.key)
            clusters.append({"type": f"similar (>= {int(threshold * 100)}%)", "fingerprint": fingerprint(p),
                             "pipelines": [f"{x.project}/{x.name}" for x in group], "tasks": " > ".join(p.task_refs())})
    return clusters
