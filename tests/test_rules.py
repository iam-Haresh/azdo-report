from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from azdo_analyzer.analyze.activity import branching_model, build_stats, classify, pool_usage
from azdo_analyzer.analyze.archetype import clone_clusters, fingerprint
from azdo_analyzer.analyze.facts import PipelineFacts
from azdo_analyzer.analyze.findings import variable_issues
from azdo_analyzer.analyze.scan import Scanner
from azdo_analyzer.analyze.scoring import score_pipeline
from azdo_analyzer.model import Job, Pipeline, Stage, Step, Variable
from azdo_analyzer.util import gitlab_key, is_valid_gitlab_key, parse_dt, slugify

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _pipeline(kind: str, tasks: list[str], stages: int = 1, key: str = "k") -> Pipeline:
    steps = [Step(name=t, kind="task", task=t) for t in tasks]
    return Pipeline(key=key, kind=kind, id=1, name=key, project="P",
                    stages=[Stage(name=f"s{i}", is_deploy=kind == "classic_release", jobs=[Job(name="j", steps=list(steps))]) for i in range(stages)])


def test_scoring_matches_checklist_baseline(rules):
    yaml = _pipeline("yaml", ["Maven@3"])
    assert score_pipeline(yaml, PipelineFacts(key="k"), rules).level == "Low"
    classic = _pipeline("classic_build", ["Maven@3"])
    assert score_pipeline(classic, PipelineFacts(key="k"), rules).level == "Medium"
    release = _pipeline("classic_release", ["IISWebAppDeploymentOnMachineGroup@0"], stages=3)
    facts = PipelineFacts(key="k", deploy_stages=3, approvals=["PROD (pre)"])
    score = score_pipeline(release, facts, rules)
    assert score.level == "High" and score.points == 4 + 3 + 2


def test_scoring_caps(rules):
    facts = PipelineFacts(key="k", unmapped_tasks=[f"T{i}@1" for i in range(20)])
    score = score_pipeline(_pipeline("yaml", []), facts, rules)
    assert score.points == 2 * 8  # capped at 8 unmapped tasks


def test_gitlab_keys():
    assert is_valid_gitlab_key("BUILD_ID") and not is_valid_gitlab_key("Build.Id") and not is_valid_gitlab_key("db-password")
    assert gitlab_key("Build.Configuration") == "BUILD_CONFIGURATION"
    invalid, plaintext, secrets = variable_issues(
        [Variable("db-password", "x"), Variable("ApiKey", None, True), Variable("NEXUS_PASSWORD", "y"), Variable("PWD_REF", "$(Other)")],
        rules_pattern := r"(?i)(pass(word)?|pwd|api[_.-]?key)")
    assert invalid == ["db-password"] and plaintext == ["NEXUS_PASSWORD", "db-password"] and secrets == 1


def test_scanner_patterns(rules):
    scanner = Scanner(rules, "https://tfs.corp.example/DefaultCollection")
    text = "\n".join([
        'echo "##vso[task.setvariable variable=X]1"',
        "curl -H \"Bearer $(System.AccessToken)\" https://tfs.corp.example/DefaultCollection/_apis/projects",
        "cd $(Build.SourcesDirectory) && echo $BUILD_BUILDID $BUILD_DIR",
    ])
    counts, hits = Counter(), []
    scanner.scan_text(text, "x.sh", counts, hits)
    assert counts["VSO_LOGGING_CMD"] == 1 and counts["ACCESS_TOKEN"] == 1
    assert counts["AZDO_URL"] >= 1
    predefined = {h.match: h.hint for h in hits if h.pattern.startswith("PREDEFINED")}
    assert predefined["Build.SourcesDirectory"] == "CI_PROJECT_DIR"
    assert predefined["BUILD_BUILDID"] == "CI_PIPELINE_ID"
    assert "BUILD_DIR" not in predefined  # unknown env vars are not reported
    assert next(h for h in hits if h.pattern == "VSO_LOGGING_CMD").line == 1


def test_fingerprints_and_clones():
    a = _pipeline("classic_build", ["NuGetCommand@2", "VSBuild@1", "VSTest@2"], key="a")
    b = _pipeline("classic_build", ["NuGetCommand@2", "VSBuild@1", "VSTest@2"], key="b")
    c = _pipeline("classic_build", ["VSBuild@1", "NuGetCommand@2", "VSTest@2"], key="c")
    assert fingerprint(a) == fingerprint(b) != fingerprint(c)
    clusters = clone_clusters([a, b, c])
    assert clusters[0]["type"] == "identical" and len(clusters[0]["pipelines"]) == 2


def test_activity_helpers():
    builds = [
        {"definition": {"id": 1}, "result": "succeeded", "queueTime": "2026-09-01T09:58:00Z", "startTime": "2026-09-01T10:00:00Z",
         "finishTime": "2026-09-01T10:10:00Z", "reason": "manual", "sourceBranch": "refs/heads/main", "queue": {"pool": "A"}},
        {"definition": {"id": 1}, "result": "failed", "startTime": "2026-09-01T10:05:00Z", "finishTime": "2026-09-01T10:20:00Z",
         "reason": "individualCI", "sourceBranch": "refs/heads/dev", "queue": {"pool": "A"}},
    ]
    stats = build_stats(builds, NOW)[1]
    assert stats.runs == 2 and stats.success_rate == 50.0 and stats.p50_minutes == 12.5
    assert stats.last_run == parse_dt("2026-09-01T10:20:00Z")
    assert pool_usage(builds, 180)["A"]["peak_concurrency"] == 2
    assert classify(parse_dt("2026-09-01T00:00:00Z"), NOW, 90, 365) == "Active"
    assert classify(parse_dt("2025-01-01T00:00:00Z"), NOW, 90, 365) == "Dead"
    assert classify(None, NOW, 90, 365) == "Never"
    assert branching_model(["main", "develop", "release/1.0"]) == "GitFlow"
    assert branching_model(["main", "feature/a"]) == "trunk-based (+ feature branches)"


def test_misc_utils():
    assert slugify("Data Scripts") == "data-scripts"
    assert slugify("My.Repo.git") == "my.repo-repo"
    assert parse_dt("2026-09-01T10:00:00.1234567Z") == datetime(2026, 9, 1, 10, 0, 0, 123456, tzinfo=timezone.utc)
    assert parse_dt("0001-01-01T00:00:00") is None
