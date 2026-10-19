"""Content scan: AZDO-specific constructs in repo files and inline pipeline scripts."""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlsplit

from azdo_analyzer.collect.content import RepoContent
from azdo_analyzer.model import Pipeline
from azdo_analyzer.rules import Rules

_FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", re.I | re.M)
_TFM = re.compile(r"<TargetFramework(?:Version|s)?>([^<]+)<", re.I)
_SUBMODULE = re.compile(r"^\s*(path|url)\s*=\s*(.+?)\s*$", re.M)


@dataclass
class ScanHit:
    pattern: str
    file: str
    line: int
    match: str
    hint: str | None = None


@dataclass
class RepoScan:
    source: str = "none"
    files_total: int = 0
    files_scanned: int = 0
    hits: list[ScanHit] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    feeds: list[dict[str, str]] = field(default_factory=list)
    registries: list[dict[str, str]] = field(default_factory=list)
    base_images: list[dict[str, str]] = field(default_factory=list)
    submodules: list[dict[str, str]] = field(default_factory=list)
    lfs_patterns: list[str] = field(default_factory=list)
    pr_templates: list[str] = field(default_factory=list)
    target_frameworks: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def hits_for(self, pattern: str) -> list[ScanHit]:
        return [h for h in self.hits if h.pattern == pattern]


class Scanner:
    def __init__(self, rules: Rules, server_url: str):
        cfg = rules.scan
        self.rules = rules
        self.max_bytes = int(cfg.get("max_file_kb", 512)) * 1024
        self.max_hits = int(cfg.get("max_hits_per_pattern", 50))
        self.skip_ext = tuple(e.lower() for e in cfg.get("skip_extensions") or [])
        self.skip_files = {f.lower() for f in cfg.get("skip_files") or []}
        self.patterns: list[tuple[str, re.Pattern]] = [(p["id"], re.compile(p["regex"])) for p in cfg.get("patterns") or []]
        host = urlsplit(server_url).hostname if server_url else None
        if host:
            self.patterns.append(("AZDO_URL", re.compile(r"(?i)https?://" + re.escape(host) + r"[^\s'\"<>()\]]*")))
        self.feed_files = {f.lower() for f in cfg.get("feed_files") or []}
        self.feed_re = re.compile(cfg.get("feed_url_regex") or r"/_packaging/([^/\s]+)")
        self.registry_re = re.compile(cfg.get("registry_url_regex") or r"$^")
        self.pr_templates = [p.lower() for p in cfg.get("pr_template_paths") or []]

    # -------------------------------------------------------------- text
    def scan_text(self, text: str, where: str, counts: Counter, hits: list[ScanHit]) -> None:
        seen_urls: set[tuple[str, str]] = set()
        for pid, regex in self.patterns:
            for match in regex.finditer(text):
                value = match.group(1) if regex.groups else match.group(0)
                hint = None
                if pid in ("PREDEFINED_VAR", "PREDEFINED_ENV"):
                    mapped = self.rules.predefined_hint(value)
                    if mapped is None and pid == "PREDEFINED_ENV":
                        continue
                    hint = mapped.get("gitlab") if mapped else None
                if pid == "AZDO_URL":
                    if (where, value) in seen_urls:
                        continue
                    seen_urls.add((where, value))
                counts[pid] += 1
                if counts[pid] <= self.max_hits:
                    line = text.count("\n", 0, match.start()) + 1
                    hits.append(ScanHit(pid, where, line, value[:200], hint))

    # -------------------------------------------------------------- repo
    def scan_repo(self, content: RepoContent) -> RepoScan:
        result = RepoScan(source=content.source)
        if not content.available:
            return result
        files = content.files()
        result.files = files
        result.files_total = len(files)
        counts: Counter[str] = Counter()
        lowered = {f.lower(): f for f in files}
        for template in self.pr_templates:
            if template.endswith("/"):
                result.pr_templates += [f for low, f in lowered.items() if low.startswith(template)]
            elif template in lowered:
                result.pr_templates.append(lowered[template])
        full_scan = content.source == "clone"
        for rel in files:
            name = posixpath.basename(rel).lower()
            interesting = (
                name in self.feed_files
                or name in (".gitmodules", ".gitattributes")
                or name.startswith("dockerfile")
                or name.endswith(".csproj")
                or name.endswith(".vbproj")
            )
            if not full_scan and not interesting:
                continue
            if name in self.skip_files or name.endswith(self.skip_ext):
                continue
            text = content.read(rel, self.max_bytes)
            if text is None or "\x00" in text[:8192]:
                continue
            result.files_scanned += 1
            self.scan_text(text, rel, counts, result.hits)
            if name in self.feed_files:
                for m in self.feed_re.finditer(text):
                    result.feeds.append({"file": rel, "feed": m.group(1), "url": m.group(0)})
                for m in self.registry_re.finditer(text):
                    if "/_packaging/" not in m.group(0):
                        result.registries.append({"file": rel, "url": m.group(0)})
            if name.startswith("dockerfile") or name.endswith(".dockerfile"):
                for m in _FROM.finditer(text):
                    image = m.group(1)
                    if image.lower() != "scratch" and not image.startswith("$"):
                        result.base_images.append({"file": rel, "image": image})
            if name == ".gitmodules":
                pending: dict[str, str] = {}
                for key, value in _SUBMODULE.findall(text):
                    pending[key] = value
                    if "path" in pending and "url" in pending:
                        result.submodules.append(dict(pending))
                        pending = {}
            if name == ".gitattributes":
                result.lfs_patterns += [line.split()[0] for line in text.splitlines() if "filter=lfs" in line and line.split()]
            if name.endswith(".csproj") or name.endswith(".vbproj"):
                result.target_frameworks += [t.strip() for m in _TFM.findall(text) for t in m.split(";") if t.strip()]
        result.counts = dict(counts)
        result.target_frameworks = sorted(set(result.target_frameworks))
        return result

    # ---------------------------------------------------------- pipeline
    def scan_pipeline(self, pipeline: Pipeline) -> tuple[dict[str, int], list[ScanHit]]:
        """Inline scripts and task inputs of a normalized pipeline."""
        counts: Counter[str] = Counter()
        hits: list[ScanHit] = []
        for stage in pipeline.stages:
            for job in stage.jobs:
                for step in job.steps:
                    where = f"{pipeline.name} / {stage.name} / {step.name}"
                    for text in _step_texts(step):
                        self.scan_text(text, where, counts, hits)
        return dict(counts), hits


def _step_texts(step: Any) -> Iterable[str]:
    if step.script:
        yield step.script
    for value in (step.inputs or {}).values():
        if isinstance(value, str) and len(value) > 3:
            yield value
    for value in (step.env or {}).values():
        if isinstance(value, str):
            yield value
