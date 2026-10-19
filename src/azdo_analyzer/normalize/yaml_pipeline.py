"""YAML pipelines: best-effort template resolution and model extraction.

Resolution rules (deliberately simple and predictable):
* ``template:`` references are inlined: local paths relative to the including
  file, ``path@alias`` via ``resources.repositories`` (fetched at the pinned ref).
* Literal ``${{ parameters.x }}`` values (defaults or passed values) are substituted.
* ``${{ if }}`` / ``${{ else }}`` branches are all kept (union) and the pipeline is
  flagged as having dynamic templates; ``${{ each }}`` over literal lists is unrolled.
* UI-defined variables and trigger overrides on the definition are merged in,
  because they are invisible in the YAML file.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Any

import yaml

from azdo_analyzer.model import Job, Pipeline, ResourceRef, Stage, Step, Trigger, Variable
from azdo_analyzer.normalize.classic_build import base_pipeline
from azdo_analyzer.normalize.common import NormContext, parse_build_triggers, step_resource_refs, variables_from_dict
from azdo_analyzer.util import as_list, branch_name, first_line

_EXPR_KEY = re.compile(r"^\s*\$\{\{\s*(if|elseif|else|each)\b(.*?)\}\}\s*$", re.S)
_PARAM = re.compile(r"\$\{\{\s*parameters(?:\.([A-Za-z0-9_-]+)|\[\s*['\"]([^'\"]+)['\"]\s*\])\s*\}\}")
_WHOLE_PARAM = re.compile(r"^\s*\$\{\{\s*parameters(?:\.([A-Za-z0-9_-]+)|\[\s*['\"]([^'\"]+)['\"]\s*\])\s*\}\}\s*$")
_EACH = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+?)\s*$")
_SIMPLE_PARAM = re.compile(r"^\s*parameters(?:\.([A-Za-z0-9_-]+)|\[\s*['\"]([^'\"]+)['\"]\s*\])\s*$")
_SCRIPT_KINDS = ("script", "bash", "pwsh", "powershell")
_SCRIPT_TASKS = {"script": "CmdLine@2", "bash": "Bash@3", "pwsh": "PowerShell@2", "powershell": "PowerShell@2"}
_CHECKOUT_TASK_IDS = {"6d15af64-176c-496d-b583-fd2ae21d4df4"}


class _Loader(yaml.SafeLoader):
    """YAML 1.2-style booleans: keeps keys such as ``on:`` (deployment hooks) as strings."""


_Loader.yaml_implicit_resolvers = {
    key: [r for r in resolvers if r[0] != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def load_yaml(text: str) -> Any:
    return yaml.load(text, Loader=_Loader)  # noqa: S506 - SafeLoader subclass


@dataclass
class RepoLoc:
    project: str
    repo: str
    ref: str | None = None

    def label(self) -> str:
        return f"{self.repo}@{branch_name(self.ref) or 'default'}"


def param_defaults(decl: Any) -> dict[str, Any]:
    if isinstance(decl, list):
        return {str(p["name"]): p.get("default") for p in decl if isinstance(p, dict) and "name" in p}
    if isinstance(decl, dict):
        return {str(k): v for k, v in decl.items()}
    return {}


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _attr(value: Any, attr: str | None) -> Any:
    if attr is None:
        return value
    return value.get(attr) if isinstance(value, dict) else None


def _template_items(doc: dict) -> list:
    for key in ("stages", "jobs", "steps", "variables"):
        if key in doc:
            value = doc[key]
            if key == "variables" and isinstance(value, dict):
                return [{"name": k, "value": v} for k, v in value.items()]
            return value if isinstance(value, list) else [value]
    return []


class YamlResolver:
    MAX_FILES = 100
    MAX_DEPTH = 20

    def __init__(self, provider: Any, root: RepoLoc):
        self.provider = provider
        self.root = root
        self.aliases: dict[str, RepoLoc] = {"self": root}
        self.external_repos: list[dict] = []
        self.files: list[str] = []
        self.templates: list[str] = []
        self.template_aliases: set[str] = set()
        self.unresolved: list[str] = []
        self.dynamic = False
        self.extends: str | None = None

    # ------------------------------------------------------------ loading
    def load(self, loc: RepoLoc, path: str) -> Any:
        if len(self.files) >= self.MAX_FILES:
            self.unresolved.append(f"file limit reached before {path}")
            return None
        text = self.provider.get(loc.project, loc.repo, loc.ref, path) if self.provider else None
        if text is None:
            self.unresolved.append(f"{loc.label()}:{path}")
            return None
        try:
            doc = load_yaml(text)
        except yaml.YAMLError as exc:
            self.unresolved.append(f"{loc.label()}:{path} (YAML error: {first_line(str(exc), 120)})")
            return None
        self.files.append(f"{loc.label()}:{path}")
        return doc

    def _register_repos(self, doc: dict) -> None:
        for r in ((doc.get("resources") or {}).get("repositories") or []):
            if not isinstance(r, dict) or not r.get("repository"):
                continue
            rtype = str(r.get("type") or "git").lower()
            if rtype == "git":
                name = str(r.get("name") or "")
                project, _, repo = name.rpartition("/")
                self.aliases[str(r["repository"])] = RepoLoc(project or self.root.project, repo or name, r.get("ref"))
            else:
                self.external_repos.append(
                    {"alias": r["repository"], "type": rtype, "name": r.get("name"), "endpoint": r.get("endpoint"), "ref": r.get("ref")}
                )

    def resolve(self, path: str) -> tuple[dict, dict]:
        """Return (root document, expanded body with templates inlined)."""
        path = path.lstrip("/")
        root_doc = self.load(self.root, path)
        if not isinstance(root_doc, dict):
            return {}, {}
        self._register_repos(root_doc)
        params = param_defaults(root_doc.get("parameters"))
        root_dir = posixpath.dirname(path)
        if "extends" in root_doc and isinstance(root_doc.get("extends"), dict):
            ext = root_doc["extends"]
            self.extends = ext.get("template")
            body = self.include(ext.get("template"), ext.get("parameters") or {}, self.root, root_dir, params, 0) if ext.get("template") else None
            body = body if isinstance(body, dict) else {}
            for key in ("variables", "pool"):
                if key in root_doc and key not in body:
                    body[key] = self.expand(root_doc[key], self.root, root_dir, params, 0)
        else:
            source = {k: v for k, v in root_doc.items() if k not in ("parameters", "resources", "trigger", "pr", "schedules", "name")}
            body = self.expand(source, self.root, root_dir, params, 0)
        return root_doc, body if isinstance(body, dict) else {}

    # ---------------------------------------------------------- expansion
    def subst(self, text: str, params: dict[str, Any], loops: dict[str, Any] | None = None) -> Any:
        if "${{" not in text:
            return text
        whole = _WHOLE_PARAM.match(text)
        if whole:
            name = whole.group(1) or whole.group(2)
            if params.get(name) is not None:
                return params[name]
        for var, val in (loops or {}).items():
            m = re.match(r"^\s*\$\{\{\s*" + re.escape(var) + r"(?:\.([A-Za-z0-9_]+))?\s*\}\}\s*$", text)
            if m and _attr(val, m.group(1)) is not None:
                return _attr(val, m.group(1))

        def param_repl(match: re.Match) -> str:
            value = params.get(match.group(1) or match.group(2))
            return match.group(0) if value is None or isinstance(value, (dict, list)) else _scalar(value)

        out = _PARAM.sub(param_repl, text)
        for var, val in (loops or {}).items():
            pattern = re.compile(r"\$\{\{\s*" + re.escape(var) + r"(?:\.([A-Za-z0-9_]+))?\s*\}\}")

            def loop_repl(match: re.Match, val: Any = val) -> str:
                value = _attr(val, match.group(1))
                return match.group(0) if value is None or isinstance(value, (dict, list)) else _scalar(value)

            out = pattern.sub(loop_repl, out)
        return out

    def _eval_simple(self, expr: str, params: dict[str, Any], loops: dict[str, Any] | None) -> Any:
        m = _SIMPLE_PARAM.match(expr)
        if m:
            return params.get(m.group(1) or m.group(2))
        name, _, attr = expr.strip().partition(".")
        if loops and name in loops:
            return _attr(loops[name], attr or None)
        return None

    def _directive(self, key: str, value: Any, loc: RepoLoc, cur_dir: str, params: dict, depth: int,
                   loops: dict | None, in_list: bool) -> list:
        match = _EXPR_KEY.match(key)
        kind, expr = match.group(1), match.group(2).strip()
        if kind == "each":
            each = _EACH.match(expr)
            collection = self._eval_simple(each.group(2), params, loops) if each else None
            if isinstance(collection, (list, dict)):
                items = [{"key": k, "value": v} for k, v in collection.items()] if isinstance(collection, dict) else collection
                results: list = []
                for item in items:
                    scoped = dict(loops or {})
                    scoped[each.group(1)] = item
                    expanded = self.expand(value, loc, cur_dir, params, depth, scoped)
                    results.extend(expanded if in_list and isinstance(expanded, list) else [expanded])
                return results
        self.dynamic = True
        expanded = self.expand(value, loc, cur_dir, params, depth, loops)
        if in_list:
            return expanded if isinstance(expanded, list) else [expanded]
        return [expanded]

    def expand(self, node: Any, loc: RepoLoc, cur_dir: str, params: dict, depth: int, loops: dict | None = None) -> Any:
        if isinstance(node, str):
            return self.subst(node, params, loops)
        if isinstance(node, list):
            out: list = []
            for item in node:
                if isinstance(item, dict) and len(item) == 1:
                    key = next(iter(item))
                    if isinstance(key, str) and _EXPR_KEY.match(key):
                        out.extend(self._directive(key, item[key], loc, cur_dir, params, depth, loops, in_list=True))
                        continue
                if isinstance(item, dict) and isinstance(item.get("template"), str) and set(item) <= {"template", "parameters"}:
                    included = self.include(item["template"], item.get("parameters") or {}, loc, cur_dir, params, depth, loops)
                    if included is None:
                        out.append({"__unresolved_template__": self.subst(item["template"], params, loops)})
                    else:
                        out.extend(_template_items(included))
                    continue
                out.append(self.expand(item, loc, cur_dir, params, depth, loops))
            return out
        if isinstance(node, dict):
            result: dict = {}
            for key, value in node.items():
                if isinstance(key, str) and _EXPR_KEY.match(key):
                    for piece in self._directive(key, value, loc, cur_dir, params, depth, loops, in_list=False):
                        if isinstance(piece, dict):
                            result.update(piece)
                    continue
                new_key = self.subst(key, params, loops) if isinstance(key, str) else key
                if not isinstance(new_key, (str, int, float, bool)):
                    new_key = str(new_key)
                result[new_key] = self.expand(value, loc, cur_dir, params, depth, loops)
            return result
        return node

    def include(self, ref: Any, passed: Any, loc: RepoLoc, cur_dir: str, outer: dict, depth: int, loops: dict | None = None) -> dict | None:
        if depth >= self.MAX_DEPTH:
            self.unresolved.append(f"template nesting limit at {ref}")
            return None
        ref = self.subst(str(ref), outer, loops)
        if not isinstance(ref, str) or "${{" in ref or "$(" in ref:
            self.dynamic = True
            self.unresolved.append(f"dynamic template path {ref}")
            return None
        path, _, alias = ref.partition("@")
        if alias:
            target = self.aliases.get(alias)
            if target is None:
                self.unresolved.append(f"unknown repository alias '{alias}' ({path})")
                return None
            base = ""
            if alias != "self":
                self.template_aliases.add(alias)
        else:
            target, base = loc, cur_dir
        full = posixpath.normpath(path.lstrip("/") if path.startswith("/") or not base else posixpath.join(base, path))
        doc = self.load(target, full)
        if not isinstance(doc, dict):
            return None
        self.templates.append(f"{full}@{alias}" if alias else full)
        passed_values = self.expand(passed, loc, cur_dir, outer, depth, loops) if passed else {}
        params = param_defaults(doc.get("parameters"))
        if isinstance(passed_values, dict):
            params.update(passed_values)
        body = {k: v for k, v in doc.items() if k != "parameters"}
        expanded = self.expand(body, target, posixpath.dirname(full), params, depth + 1, None)
        return expanded if isinstance(expanded, dict) else None


# ---------------------------------------------------------------- model
def _branches(node: Any) -> tuple[list[str], list[str]]:
    if isinstance(node, dict):
        return [str(b) for b in as_list(node.get("include"))], [str(b) for b in as_list(node.get("exclude"))]
    return [str(b) for b in as_list(node)], []


def yaml_triggers(doc: dict, repo_type: str | None) -> list[Trigger]:
    out: list[Trigger] = []
    trigger = doc.get("trigger", "__absent__")
    if trigger in ("__absent__", None):
        out.append(Trigger("ci", "yaml", ["*"], detail={"implicit": True}))
    elif isinstance(trigger, list):
        out.append(Trigger("ci", "yaml", [str(b) for b in trigger]))
    elif isinstance(trigger, dict):
        bi, be = _branches(trigger.get("branches"))
        pi, pe = _branches(trigger.get("paths"))
        ti, _ = _branches(trigger.get("tags"))
        out.append(Trigger("ci", "yaml", bi or (["*"] if not ti else []), be, pi, pe, batch=bool(trigger.get("batch")), detail={"tags": ti} if ti else {}))
    pr = doc.get("pr", "__absent__")
    if pr not in ("__absent__", None, "none"):
        if isinstance(pr, dict):
            bi, be = _branches(pr.get("branches"))
            pi, pe = _branches(pr.get("paths"))
        else:
            bi, be, pi, pe = [str(b) for b in as_list(pr)], [], [], []
        detail = {"ignored": "Azure Repos ignores 'pr:'; PR validation comes from branch policies"} if repo_type == "TfsGit" else {}
        out.append(Trigger("pr", "yaml", bi, be, pi, pe, detail=detail))
    for s in doc.get("schedules") or []:
        if not isinstance(s, dict):
            continue
        bi, be = _branches(s.get("branches"))
        out.append(Trigger("schedule", "yaml", bi, be, schedule=f"cron '{s.get('cron')}'" + (" (always)" if s.get("always") else ""),
                           detail={"displayName": s.get("displayName")}))
    resources = doc.get("resources") or {}
    for rp in resources.get("pipelines") or []:
        if not isinstance(rp, dict):
            continue
        trig = rp.get("trigger")
        if trig in (None, False, "none"):
            continue
        bi, be = _branches(trig.get("branches")) if isinstance(trig, dict) else ([], [])
        out.append(Trigger("pipeline", "yaml", bi, be, source=rp.get("source"),
                           detail={"alias": rp.get("pipeline"), "project": rp.get("project"),
                                   "stages": trig.get("stages") if isinstance(trig, dict) else None}))
    for rr in resources.get("repositories") or []:
        if isinstance(rr, dict) and rr.get("trigger") not in (None, "none", False):
            bi, be = _branches((rr.get("trigger") or {}).get("branches") if isinstance(rr.get("trigger"), dict) else rr.get("trigger"))
            out.append(Trigger("ci", "yaml", bi, be, source=f"repository {rr.get('name')}"))
    for wh in resources.get("webhooks") or []:
        if isinstance(wh, dict):
            out.append(Trigger("webhook", "yaml", source=wh.get("webhook") or wh.get("connection")))
    return out


def parse_variables(node: Any, scope: str, source: str) -> tuple[list[Variable], list[str]]:
    variables: list[Variable] = []
    groups: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            variables.append(Variable(str(k), None if v is None else str(v), scope=scope, source=source))
    elif isinstance(node, list):
        for item in node:
            if not isinstance(item, dict):
                continue
            if "group" in item:
                groups.append(str(item["group"]))
            elif "name" in item:
                value = item.get("value")
                variables.append(Variable(str(item["name"]), None if value is None else str(value), scope=scope, source=source))
    return variables, groups


def parse_pool(node: Any) -> tuple[str | None, str | None, list[str], bool] | None:
    if node is None:
        return None
    if isinstance(node, str):
        return (None if node == "server" else node), None, [], node == "server"
    if isinstance(node, dict):
        name = node.get("name")
        return name, node.get("vmImage"), [str(d) for d in as_list(node.get("demands"))], name == "server"
    return None


def parse_steps(items: Any, ctx: NormContext, origin: str | None = None) -> list[Step]:
    out: list[Step] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        common: dict[str, Any] = {
            "condition": item.get("condition"),
            "continue_on_error": bool(item.get("continueOnError")),
            "timeout": item.get("timeoutInMinutes"),
            "retries": item.get("retryCountOnTaskFailure"),
            "env": item.get("env") or {},
            "enabled": item.get("enabled", True) is not False,
            "origin": origin,
        }
        if "task" in item:
            info = ctx.catalog.resolve_ref(str(item["task"]))
            out.append(Step(name=item.get("displayName") or info.friendly or info.name, kind="task", task=info.ref, task_id=info.id,
                            task_version=str(item["task"]).partition("@")[2] or None, source=info.source, extension=info.extension,
                            inputs=dict(item.get("inputs") or {}), windows_only=info.windows_only, **common))
        elif any(k in item for k in _SCRIPT_KINDS):
            key = next(k for k in _SCRIPT_KINDS if k in item)
            body = "" if item[key] is None else str(item[key])
            extras = {k: item[k] for k in ("workingDirectory", "failOnStderr", "errorActionPreference", "targetType") if k in item}
            out.append(Step(name=item.get("displayName") or first_line(body) or key, kind="script", task=key, script=body,
                            source="yaml", inputs=extras, **common))
        elif "checkout" in item:
            opts = {k: item[k] for k in ("checkout", "submodules", "lfs", "fetchDepth", "clean", "path", "persistCredentials", "fetchTags") if k in item}
            out.append(Step(name=f"checkout {item['checkout']}", kind="checkout", task="checkout", source="yaml", inputs=opts, **common))
        elif "download" in item or "downloadBuild" in item:
            key = "download" if "download" in item else "downloadBuild"
            out.append(Step(name=f"{key} {item[key]}", kind="download", task=key, source="yaml",
                            inputs={k: v for k, v in item.items() if k != "displayName"}, **common))
        elif "publish" in item:
            out.append(Step(name=f"publish {item['publish']}", kind="publish", task="publish", source="yaml",
                            inputs={k: v for k, v in item.items() if k != "displayName"}, **common))
        elif "__unresolved_template__" in item or "template" in item:
            ref = item.get("__unresolved_template__") or item.get("template")
            out.append(Step(name=f"unresolved template {ref}", kind="template", source="unknown", **common))
        else:
            key = str(next(iter(item)))
            out.append(Step(name=key, kind="other", task=key, source="yaml", inputs={k: v for k, v in item.items() if k != "displayName"}, **common))
    return out


def _environment_name(env: Any) -> str | None:
    if isinstance(env, str):
        return env
    if isinstance(env, dict):
        return env.get("name")
    return None


def build_job(src: dict, inherited: tuple | None, ctx: NormContext, pipeline: Pipeline) -> tuple[Job | None, list[Variable], list[str]]:
    if "__unresolved_template__" in src:
        pipeline.warnings.append(f"job template not resolved: {src['__unresolved_template__']}")
        return Job(name=f"unresolved template {src['__unresolved_template__']}", steps=[Step(name="unresolved template", kind="template", source="unknown")]), [], []
    if "deployment" in src:
        kind, name = "deployment", str(src["deployment"])
    elif "job" in src:
        kind, name = "agent", str(src["job"])
    else:
        return None, [], []
    pool = parse_pool(src.get("pool")) if "pool" in src else inherited
    pool_name, vm_image, demands, server = pool if pool else (None, None, [], False)
    job = Job(name=name, kind="server" if server and kind != "deployment" else kind, pool=pool_name, vm_image=vm_image,
              demands=list(demands), condition=src.get("condition"), depends_on=[str(x) for x in as_list(src.get("dependsOn"))],
              timeout=src.get("timeoutInMinutes"), continue_on_error=bool(src.get("continueOnError")))
    container = src.get("container")
    if container:
        job.container = container if isinstance(container, str) else str((container or {}).get("image") or container)
    services = src.get("services")
    if isinstance(services, dict):
        job.services = [str(v.get("image") if isinstance(v, dict) else v) for v in services.values()]
    variables, groups = parse_variables(src.get("variables"), f"job:{name}", "yaml")
    if kind == "deployment":
        job.environment = _environment_name(src.get("environment"))
        strategy = src.get("strategy") or {}
        steps: list[Step] = []
        for sname in ("runOnce", "rolling", "canary"):
            if isinstance(strategy, dict) and sname in strategy:
                hooks = strategy[sname] or {}
                job.strategy = {"type": sname, **{k: hooks[k] for k in ("maxParallel", "increments") if k in hooks}}
                for hook in ("preDeploy", "deploy", "routeTraffic", "postRouteTraffic"):
                    steps += parse_steps((hooks.get(hook) or {}).get("steps"), ctx, origin=hook)
                on = hooks.get("on") or {}
                for hook in ("failure", "success"):
                    steps += parse_steps((on.get(hook) or {}).get("steps"), ctx, origin=f"on.{hook}")
        job.steps = steps
    else:
        strategy = src.get("strategy")
        if isinstance(strategy, dict) and ("matrix" in strategy or "parallel" in strategy):
            matrix = strategy.get("matrix")
            job.strategy = {"type": "matrix" if "matrix" in strategy else "parallel",
                            "size": len(matrix) if isinstance(matrix, dict) else strategy.get("parallel"),
                            "max_parallel": strategy.get("maxParallel")}
        job.steps = parse_steps(src.get("steps"), ctx)
    return job, variables, groups


def normalize_yaml_pipeline(d: dict, ctx: NormContext) -> Pipeline:
    pipeline = base_pipeline(d, ctx, "yaml")
    pipeline.yaml_path = (d.get("process") or {}).get("yamlFilename")
    ui_variables = variables_from_dict(d.get("variables"), "pipeline-ui", "definition (UI)")
    ui_triggers = parse_build_triggers(d.get("triggers"), yaml_pipeline=True)
    if ui_variables:
        pipeline.flags["ui_variables"] = len(ui_variables)
    if ui_triggers:
        pipeline.flags["ui_trigger_override"] = sorted({t.kind for t in ui_triggers})
    repo = d.get("repository") or {}

    if not ctx.deep or ctx.file_provider is None:
        pipeline.depth = "inventory"
        pipeline.variables = ui_variables
        pipeline.triggers = ui_triggers
        return pipeline
    if repo.get("type") not in (None, "TfsGit"):
        pipeline.warnings.append(f"YAML stored in a {repo.get('type')} repository - template resolution skipped")
        pipeline.variables, pipeline.triggers = ui_variables, ui_triggers
        pipeline.flags["yaml_unresolved"] = True
        return pipeline

    root = RepoLoc(project=pipeline.repo_project or ctx.project, repo=repo.get("name") or repo.get("id") or "", ref=None)
    resolver = YamlResolver(ctx.file_provider, root)
    doc, body = resolver.resolve(pipeline.yaml_path or "azure-pipelines.yml")
    if not doc:
        pipeline.warnings.append(f"YAML file '{pipeline.yaml_path}' not found or unreadable")
        pipeline.flags["yaml_unresolved"] = True
        pipeline.variables, pipeline.triggers = ui_variables, ui_triggers
        return pipeline

    triggers = yaml_triggers(doc, repo.get("type"))
    ui_kinds = {t.kind for t in ui_triggers}
    pipeline.triggers = [t for t in triggers if t.kind not in ui_kinds] + ui_triggers

    params = doc.get("parameters")
    if isinstance(params, list):
        pipeline.parameters = [
            {"name": p.get("name"), "type": p.get("type"), "default": p.get("default"), "values": p.get("values")}
            for p in params if isinstance(p, dict)
        ]

    root_vars, root_groups = parse_variables(body.get("variables"), "pipeline", "yaml")
    pipeline.variables = ui_variables + root_vars
    group_names: list[tuple[str, str]] = [(g, "pipeline") for g in root_groups]

    default_pool = parse_pool(body.get("pool"))
    stages_src = body.get("stages")
    if stages_src is None:
        jobs_src = body.get("jobs")
        if jobs_src is None:
            job = {"job": "__default", "steps": body.get("steps") or []}
            for key in ("container", "services", "strategy", "workspace", "timeoutInMinutes"):
                if key in body:
                    job[key] = body[key]
            jobs_src = [job]
        stages_src = [{"stage": "__default", "jobs": jobs_src}]

    for index, st in enumerate(stages_src or []):
        if not isinstance(st, dict):
            continue
        if "__unresolved_template__" in st:
            pipeline.warnings.append(f"stage template not resolved: {st['__unresolved_template__']}")
            continue
        name = str(st.get("stage") or st.get("displayName") or f"stage{index + 1}")
        stage = Stage(name=name, rank=index, depends_on=[str(x) for x in as_list(st.get("dependsOn"))], condition=st.get("condition"))
        stage.variables, stage.variable_groups = parse_variables(st.get("variables"), f"stage:{name}", "yaml")
        group_names += [(g, f"stage {name}") for g in stage.variable_groups]
        stage_pool = parse_pool(st.get("pool")) or default_pool
        for job_src in st.get("jobs") or []:
            if not isinstance(job_src, dict):
                continue
            job, job_vars, job_groups = build_job(job_src, stage_pool, ctx, pipeline)
            if job is None:
                continue
            stage.jobs.append(job)
            stage.variables.extend(job_vars)
            group_names += [(g, f"job {job.name}") for g in job_groups]
            if job.kind == "deployment":
                stage.is_deploy = True
                stage.environment = stage.environment or job.environment
        pipeline.stages.append(stage)

    # ------------------------------------------------------------ resources
    by_name = {str(v.get("name", "")).lower(): v for v in ctx.variable_groups_by_id.values()}
    for gname, where in group_names:
        group = by_name.get(gname.lower())
        pipeline.variable_groups.append(ResourceRef("variable_group", gname, str(group["id"]) if group else None, ctx.project, detail=where, resolved=group is not None))
    pipeline.resources = step_resource_refs(pipeline.all_steps(enabled_only=False), ctx)
    for job in pipeline.all_jobs():
        if job.pool:
            pipeline.resources.append(ResourceRef("queue", job.pool, None, ctx.project, detail=job.name))
        if job.environment:
            pipeline.resources.append(ResourceRef("environment", job.environment.split(".")[0], None, ctx.project, detail=job.name))
    resources = doc.get("resources") or {}
    for container in resources.get("containers") or []:
        if isinstance(container, dict):
            pipeline.resources.append(ResourceRef("container", str(container.get("image") or container.get("container")), None, None, detail=container.get("container")))
            endpoint = container.get("endpoint")
            ep = ctx.match_endpoint(str(endpoint)) if endpoint else None
            if ep:
                pipeline.resources.append(ResourceRef("service_connection", ep.get("name"), ep.get("id"), ctx.project, detail=f"container {container.get('container')}"))
    for rp in resources.get("pipelines") or []:
        if isinstance(rp, dict):
            pipeline.resources.append(ResourceRef("pipeline", str(rp.get("source")), None, rp.get("project") or ctx.project, detail=f"resources.pipelines {rp.get('pipeline')}"))
    checkouts = [s.inputs.get("checkout") for s in pipeline.all_steps(enabled_only=False) if s.kind == "checkout"]
    for alias, loc in resolver.aliases.items():
        if alias == "self":
            continue
        role = "template_repo" if alias in resolver.template_aliases else "repository"
        detail = "templates" if role == "template_repo" else ("checkout" if alias in checkouts else "declared")
        pipeline.resources.append(ResourceRef(role, f"{loc.project}/{loc.repo}", None, loc.project, detail=f"{detail} @{branch_name(loc.ref) or 'default'}"))
    for ext in resolver.external_repos:
        pipeline.resources.append(ResourceRef("repository", str(ext.get("name")), None, None, detail=f"{ext.get('type')} via {ext.get('endpoint')}"))
        ep = ctx.match_endpoint(str(ext.get("endpoint"))) if ext.get("endpoint") else None
        if ep:
            pipeline.resources.append(ResourceRef("service_connection", ep.get("name"), ep.get("id"), ctx.project, detail=f"repository {ext.get('alias')}"))

    self_checkout = next((s.inputs for s in pipeline.all_steps(enabled_only=False) if s.kind == "checkout" and s.inputs.get("checkout") == "self"), {})
    other = [c for c in checkouts if c not in ("self", "none", None)]
    pipeline.checkout = {
        "submodules": self_checkout.get("submodules"),
        "lfs": self_checkout.get("lfs"),
        "fetch_depth": self_checkout.get("fetchDepth"),
        "clean": self_checkout.get("clean"),
        "multi_repo": other,
        "none": "none" in checkouts,
    }
    pipeline.templates = resolver.templates
    pipeline.flags.update(
        {
            "template_files": len(resolver.files),
            "dynamic_templates": resolver.dynamic,
            "unresolved_templates": resolver.unresolved,
            "extends": resolver.extends,
        }
    )
    return pipeline


def timeline_crosscheck(pipeline: Pipeline, records: list[dict] | None) -> None:
    """Compare statically found tasks with tasks that actually ran in the latest good run."""
    if not records:
        return
    executed = set()
    for r in records:
        task = r.get("task") or {}
        if r.get("type") != "Task" or not task.get("name") or str(task.get("id", "")).lower() in _CHECKOUT_TASK_IDS:
            continue
        major = str(task.get("version") or "").split(".")[0]
        executed.add(f"{task['name']}@{major}" if major.isdigit() else task["name"])
    static = set(pipeline.task_refs(enabled_only=False))
    static |= {_SCRIPT_TASKS[s.task] for s in pipeline.all_steps(enabled_only=False) if s.kind == "script" and s.task in _SCRIPT_TASKS}
    pipeline.flags["timeline_checked"] = True
    pipeline.flags["timeline_only_tasks"] = sorted(executed - static)
    pipeline.flags["static_only_tasks"] = sorted(static - executed)
    workers = sorted({r.get("workerName") for r in records if r.get("workerName")})
    if workers:
        pipeline.flags["agents_seen"] = workers
