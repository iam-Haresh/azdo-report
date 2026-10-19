from __future__ import annotations

from azdo_analyzer.normalize import make_context
from azdo_analyzer.normalize.classic_build import normalize_classic_build
from azdo_analyzer.normalize.classic_release import normalize_classic_release
from azdo_analyzer.rawdata import load_org, load_project
from azdo_analyzer.cache import RawStore
from tests.fixtures.sample_data import PROJECT, PID


def _context(cfg, provider):
    store = RawStore(cfg.raw_dir)
    org, raw = load_org(store), load_project(store, PROJECT, PID)
    return make_context(org, raw, web_base=cfg.azdo.collection_url, provider=provider, deep=True), raw


def test_classic_build_expands_nested_task_groups(sample_cfg, provider):
    ctx, raw = _context(sample_cfg, provider)
    pipeline = normalize_classic_build(raw.build_definitions_full[12], ctx)
    steps = pipeline.all_steps()
    tasks = [s.task for s in steps]
    assert tasks[:6] == ["NuGetToolInstaller@1", "NuGetCommand@2", "VSBuild@1", "VSTest@2", "WhiteSource@21", "DownloadSecureFile@1"]
    # Publish web -> CopyFiles, PublishBuildArtifacts, nested Stamp version -> PowerShell
    assert tasks[6:] == ["CopyFiles@2", "PublishBuildArtifacts@1", "PowerShell@2"]
    assert steps[-1].via_task_group == ["Publish web", "Stamp version"]
    # task-group input substitution: $(ArtifactName) -> drop
    assert steps[7].inputs["ArtifactName"] == "drop"
    assert next(s for s in steps if s.task == "WhiteSource@21").source == "extension"
    assert next(s for s in steps if s.task == "VSBuild@1").windows_only


def test_classic_build_triggers_variables_and_resources(sample_cfg, provider):
    ctx, raw = _context(sample_cfg, provider)
    pipeline = normalize_classic_build(raw.build_definitions_full[12], ctx)
    ci, schedule = pipeline.triggers
    assert ci.kind == "ci" and ci.branches_include == ["master"] and ci.paths_include == ["/src"] and ci.paths_exclude == ["/docs"] and ci.batch
    assert schedule.schedule.startswith("Mon,Tue,Wed,Thu,Fri 02:00")
    names = {v.name: v for v in pipeline.variables}
    assert names["ApiKey"].is_secret and names["ApiKey"].value is None
    assert not names["build.platform"].valid_gitlab_key and names["build.platform"].proposed_key == "BUILD_PLATFORM"
    secure = [r for r in pipeline.resources if r.kind == "secure_file"]
    assert [r.name for r in secure] == ["signing.pfx"]
    assert pipeline.stages[0].jobs[0].pool == "Windows-VS2022"
    assert pipeline.flags.get("oauth_token_access") is True


def test_classic_release_stages_approvals_gates(sample_cfg, provider):
    ctx, raw = _context(sample_cfg, provider)
    pipeline = normalize_classic_release(raw.release_definitions_full[5], ctx)
    assert [s.name for s in pipeline.stages] == ["DEV", "QA", "PROD"]
    dev, qa, prod = pipeline.stages
    assert dev.trigger == "after release" and dev.approvals == []
    assert qa.trigger == "after DEV (succeeded)" and qa.depends_on == ["DEV"]
    assert qa.approvals[0].approvers == ["[Contoso Retail]\\QA Leads [group]"]
    assert [g.task for g in qa.gates] == ["InvokeRESTAPI@1"]
    assert qa.queue_policy == "1 at a time, latest only"
    pre, post = prod.approvals
    assert pre.approvers == ["Alice Admin", "Bob Boss"] and pre.required_count == 2 and pre.creator_can_approve is False
    assert post.when == "post"
    assert [j.kind for j in prod.jobs] == ["server", "deployment_group"]
    assert prod.jobs[1].deployment_group == "web-prod-servers"
    assert dev.jobs[0].tags == ["web"]
    connections = {r.name for r in pipeline.resources if r.kind == "service_connection"}
    assert "servicenow-generic" in connections  # referenced by the QA gate
    assert pipeline.artifacts[0].source_name == "legacy-web-CI" and pipeline.artifacts[0].is_primary
    assert [r.name for r in pipeline.variable_groups] == ["legacy-kv"]
    assert pipeline.retention == {"days": 30, "releases": 3, "retain_build": True}
