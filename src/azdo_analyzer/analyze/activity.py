"""Activity: run statistics, deployment history, repo freshness, pool concurrency."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from azdo_analyzer.util import branch_name, days_since, parse_dt, percentile


@dataclass
class RunStats:
    runs: int = 0
    succeeded: int = 0
    partially: int = 0
    failed: int = 0
    canceled: int = 0
    runs_90d: int = 0
    last_run: datetime | None = None
    last_success: datetime | None = None
    p50_minutes: float | None = None
    p95_minutes: float | None = None
    queue_p95_minutes: float | None = None
    reasons: dict[str, int] = field(default_factory=dict)
    branches: list[tuple[str, int]] = field(default_factory=list)

    @property
    def success_rate(self) -> float | None:
        done = self.succeeded + self.partially + self.failed
        return round(100.0 * (self.succeeded + self.partially) / done, 1) if done else None


@dataclass
class StageStats:
    deployments: int = 0
    succeeded: int = 0
    failed: int = 0
    last_deployed: datetime | None = None

    @property
    def success_rate(self) -> float | None:
        done = self.succeeded + self.failed
        return round(100.0 * self.succeeded / done, 1) if done else None


@dataclass
class RepoActivity:
    last_commit: datetime | None = None
    last_commit_any: datetime | None = None
    branches: int = 0
    stale_branches: int = 0
    tags: int = 0
    tag_samples: list[str] = field(default_factory=list)
    open_prs: int = 0
    oldest_pr_days: int | None = None
    branching_model: str = "unknown"
    branch_names: list[str] = field(default_factory=list)


def classify(last: datetime | None, now: datetime, active_days: int, dormant_days: int) -> str:
    if last is None:
        return "Never"
    age = days_since(last, now) or 0
    if age <= active_days:
        return "Active"
    if age <= dormant_days:
        return "Dormant"
    return "Dead"


def recommendation(status: str) -> str:
    return {"Active": "Migrate", "Dormant": "Review with owner", "Dead": "Archive / retire", "Never": "Archive / retire"}.get(status, "Review")


def build_stats(builds: list[dict], now: datetime) -> dict[int, RunStats]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for b in builds:
        did = (b.get("definition") or {}).get("id")
        if did is not None:
            grouped[int(did)].append(b)
    out: dict[int, RunStats] = {}
    cutoff = now - timedelta(days=90)
    for did, runs in grouped.items():
        stats = RunStats(runs=len(runs))
        durations, waits = [], []
        reasons: Counter[str] = Counter()
        branches: Counter[str] = Counter()
        for b in runs:
            result = b.get("result")
            if result == "succeeded":
                stats.succeeded += 1
            elif result == "partiallySucceeded":
                stats.partially += 1
            elif result == "failed":
                stats.failed += 1
            elif result == "canceled":
                stats.canceled += 1
            queued, started, finished = parse_dt(b.get("queueTime")), parse_dt(b.get("startTime")), parse_dt(b.get("finishTime"))
            if started and finished:
                durations.append((finished - started).total_seconds() / 60)
            if queued and started:
                waits.append((started - queued).total_seconds() / 60)
            when = finished or started or queued
            if when:
                if stats.last_run is None or when > stats.last_run:
                    stats.last_run = when
                if result in ("succeeded", "partiallySucceeded") and (stats.last_success is None or when > stats.last_success):
                    stats.last_success = when
                if when >= cutoff:
                    stats.runs_90d += 1
            reasons[b.get("reason") or "unknown"] += 1
            if b.get("sourceBranch"):
                branches[branch_name(b["sourceBranch"]) or b["sourceBranch"]] += 1
        stats.p50_minutes = _round(percentile(durations, 50))
        stats.p95_minutes = _round(percentile(durations, 95))
        stats.queue_p95_minutes = _round(percentile(waits, 95))
        stats.reasons = dict(reasons.most_common())
        stats.branches = branches.most_common(5)
        out[did] = stats
    return out


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def deployment_stats(deployments: list[dict]) -> tuple[dict[tuple[int, int], StageStats], dict[int, datetime]]:
    """(release definition id, definition environment id) -> stats, and last deployment per definition."""
    stages: dict[tuple[int, int], StageStats] = defaultdict(StageStats)
    last: dict[int, datetime] = {}
    for d in deployments:
        did = (d.get("releaseDefinition") or {}).get("id")
        env_id = d.get("definitionEnvironmentId")
        if did is None:
            continue
        when = parse_dt(d.get("completedOn")) or parse_dt(d.get("startedOn")) or parse_dt(d.get("queuedOn"))
        stats = stages[(int(did), int(env_id or 0))]
        stats.deployments += 1
        status = (d.get("deploymentStatus") or "").lower()
        if status in ("succeeded", "partiallysucceeded"):
            stats.succeeded += 1
        elif status == "failed":
            stats.failed += 1
        if when:
            if stats.last_deployed is None or when > stats.last_deployed:
                stats.last_deployed = when
            if int(did) not in last or when > last[int(did)]:
                last[int(did)] = when
    return dict(stages), last


def repo_activity(branch_stats: list[dict], tags: list[dict], prs: list[dict], default_branch: str | None,
                  now: datetime, dormant_days: int) -> RepoActivity:
    act = RepoActivity(branches=len(branch_stats), tags=len(tags), open_prs=len(prs))
    default = branch_name(default_branch)
    names = []
    for b in branch_stats:
        name = b.get("name")
        names.append(name)
        commit = b.get("commit") or {}
        when = parse_dt((commit.get("committer") or {}).get("date")) or parse_dt((commit.get("author") or {}).get("date"))
        if when:
            if act.last_commit_any is None or when > act.last_commit_any:
                act.last_commit_any = when
            if name == default or b.get("isBaseVersion"):
                act.last_commit = when if act.last_commit is None or when > act.last_commit else act.last_commit
            if (days_since(when, now) or 0) > dormant_days:
                act.stale_branches += 1
    if act.last_commit is None:
        act.last_commit = act.last_commit_any
    act.branch_names = [n for n in names if n]
    act.tag_samples = [branch_name(t.get("name")) or "" for t in tags[:5]]
    ages = [days_since(parse_dt(pr.get("creationDate")), now) for pr in prs]
    ages = [a for a in ages if a is not None]
    act.oldest_pr_days = max(ages) if ages else None
    act.branching_model = branching_model(act.branch_names)
    return act


def branching_model(names: list[str]) -> str:
    lowered = [n.lower() for n in names]
    has_develop = any(n in ("develop", "development", "dev") for n in lowered)
    releases = any(n.startswith("release/") or n.startswith("releases/") for n in lowered)
    hotfix = any(n.startswith("hotfix/") for n in lowered)
    if has_develop and (releases or hotfix):
        return "GitFlow"
    if has_develop:
        return "develop + main"
    if releases:
        return "trunk + release branches"
    if len(lowered) <= 1:
        return "single branch"
    return "trunk-based (+ feature branches)"


def pool_usage(builds: list[dict], window_days: int) -> dict[str, dict[str, float]]:
    """Per pool: runs, peak concurrent runs and build minutes per month (sweep-line)."""
    events: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    minutes: Counter[str] = Counter()
    runs: Counter[str] = Counter()
    for b in builds:
        queue = b.get("queue") or {}
        pool = queue.get("pool") or queue.get("name") or "unknown"
        start, end = parse_dt(b.get("startTime")), parse_dt(b.get("finishTime"))
        if not start or not end or end < start:
            continue
        events[pool].append((start, 1))
        events[pool].append((end, -1))
        minutes[pool] += (end - start).total_seconds() / 60
        runs[pool] += 1
    out = {}
    months = max(window_days / 30.0, 1.0)
    for pool, evs in events.items():
        evs.sort(key=lambda e: (e[0], e[1]))
        current = peak = 0
        for _, delta in evs:
            current += delta
            peak = max(peak, current)
        out[pool] = {"runs": runs[pool], "peak_concurrency": peak, "minutes_per_month": round(minutes[pool] / months, 1)}
    return out
