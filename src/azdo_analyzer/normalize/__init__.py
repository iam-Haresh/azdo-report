"""Normalize every build/YAML/release definition of a project into Pipeline objects."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from azdo_analyzer.cache import safe_name
from azdo_analyzer.collect.builds import latest_good_build_per_definition
from azdo_analyzer.model import Pipeline
from azdo_analyzer.normalize.catalog import TaskCatalog, TaskGroupIndex
from azdo_analyzer.normalize.classic_build import normalize_classic_build
from azdo_analyzer.normalize.classic_release import normalize_classic_release
from azdo_analyzer.normalize.common import NormContext
from azdo_analyzer.normalize.yaml_pipeline import normalize_yaml_pipeline, timeline_crosscheck
from azdo_analyzer.rawdata import OrgRaw, ProjectRaw

log = logging.getLogger("azdo_analyzer.normalize")


def make_context(org: OrgRaw, raw: ProjectRaw, *, web_base: str, provider: Any, deep: bool) -> NormContext:
    def by_int_id(items: list[dict]) -> dict[int, dict]:
        out = {}
        for item in items:
            try:
                out[int(item["id"])] = item
            except (KeyError, TypeError, ValueError):
                continue
        return out

    return NormContext(
        project=raw.name,
        project_id=raw.id,
        catalog=TaskCatalog(org.tasks),
        task_groups=TaskGroupIndex(raw.task_groups),
        web_base=web_base,
        repos_by_id={r["id"]: r for r in raw.repos},
        queues_by_id=by_int_id(raw.queues),
        deployment_groups_by_id=by_int_id(raw.deployment_groups),
        variable_groups_by_id=by_int_id(raw.variable_groups),
        endpoints=raw.endpoints,
        secure_files=raw.secure_files,
        file_provider=provider,
        deep=deep,
    )


def normalize_project(org: OrgRaw, raw: ProjectRaw, *, web_base: str, provider: Any, deep: bool) -> list[Pipeline]:
    ctx = make_context(org, raw, web_base=web_base, provider=provider, deep=deep)
    latest = latest_good_build_per_definition(raw.builds, raw.build_definitions)
    pipelines: list[Pipeline] = []
    for listed in raw.build_definitions:
        full = raw.build_definitions_full.get(int(listed["id"]))
        definition = full or listed
        try:
            if (definition.get("process") or {}).get("type") == 2:
                pipeline = normalize_yaml_pipeline(definition, ctx)
            else:
                pipeline = normalize_classic_build(definition, ctx)
        except Exception as exc:  # one odd definition must not stop the analysis
            log.exception("failed to normalize build definition %s", listed.get("id"))
            pipeline = Pipeline(key=f"build:{raw.name}:{listed['id']}", kind="classic_build", id=int(listed["id"]),
                                name=listed.get("name", "?"), project=raw.name, warnings=[f"normalization failed: {exc}"])
        if full is None:
            pipeline.depth = "inventory"
        timeline_crosscheck(pipeline, raw.timelines.get(latest.get(int(listed["id"]), -1)))
        pipelines.append(pipeline)
    for listed in raw.release_definitions:
        full = raw.release_definitions_full.get(int(listed["id"]))
        try:
            pipeline = normalize_classic_release(full or listed, ctx)
        except Exception as exc:
            log.exception("failed to normalize release definition %s", listed.get("id"))
            pipeline = Pipeline(key=f"release:{raw.name}:{listed['id']}", kind="classic_release", id=int(listed["id"]),
                                name=listed.get("name", "?"), project=raw.name, warnings=[f"normalization failed: {exc}"])
        if full is None:
            pipeline.depth = "inventory"
        pipelines.append(pipeline)
    return pipelines


def save_model(model_dir: Path, project: str, pipelines: list[Pipeline]) -> Path:
    folder = model_dir / safe_name(project)
    (folder / "pipelines").mkdir(parents=True, exist_ok=True)
    for pipeline in pipelines:
        target = folder / "pipelines" / f"{safe_name(pipeline.key.replace(':', '_'))}.json"
        target.write_text(json.dumps(pipeline.to_dict(), indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return folder
