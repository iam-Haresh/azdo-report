"""Repositories, branch stats, tags, open PRs, branch policies, TFVC detection."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext


def collect_repos(ctx: CollectContext, project: dict) -> list[dict]:
    c, p = ctx.client, project["name"]
    scope = p
    repos = ctx.fetch(
        (p, "repos.json"),
        lambda: c.get_list("git/repositories", {"includeHidden": "true"}, project=p),
        scope=scope,
        collector="repos",
        endpoint="git/repositories",
    ) or []

    def per_repo(repo: dict) -> None:
        rid = repo["id"]
        if repo.get("isDisabled") or not repo.get("defaultBranch"):
            return
        ctx.fetch(
            (p, "repo", rid, "branch_stats.json"),
            lambda: c.get_list(f"git/repositories/{rid}/stats/branches", project=p),
            scope=scope,
            collector="repos",
            endpoint="git/repositories/{id}/stats/branches",
        )
        ctx.fetch(
            (p, "repo", rid, "open_prs.json"),
            lambda: list(
                c.paged(
                    f"git/repositories/{rid}/pullrequests",
                    {"searchCriteria.status": "active"},
                    project=p,
                    mode="skip",
                    page_size=200,
                )
            ),
            scope=scope,
            collector="repos",
            endpoint="git/repositories/{id}/pullrequests",
        )
        if ctx.deep:
            ctx.fetch(
                (p, "repo", rid, "tags.json"),
                lambda: list(c.paged(f"git/repositories/{rid}/refs", {"filter": "tags/", "$top": 1000}, project=p)),
                scope=scope,
                collector="repos",
                endpoint="git/repositories/{id}/refs?filter=tags/",
            )

    ctx.progress(f"{p}: {len(repos)} repositories")
    ctx.pmap(per_repo, repos)

    ctx.fetch(
        (p, "policy_configurations.json"),
        lambda: list(c.paged("policy/configurations", project=p)),
        scope=scope,
        collector="repos",
        endpoint="policy/configurations",
    )
    ctx.fetch(
        (p, "tfvc_changesets.json"),
        lambda: c.get_list("tfvc/changesets", {"searchCriteria.itemPath": f"$/{p}", "$top": 1}, project=p),
        scope=scope,
        collector="repos",
        endpoint="tfvc/changesets",
    )
    return repos


def resolve_identities(ctx: CollectContext, project: str, identity_ids: set[str]) -> dict[str, Any]:
    """Best-effort: required-reviewer GUIDs -> display names (needs Identity (Read))."""
    c = ctx.client
    known: dict[str, Any] = ctx.store.read(project, "identities.json", default={}) or {}
    missing = sorted(i for i in identity_ids if i and i not in known)
    if not missing or c is None:
        return known
    for start in range(0, len(missing), 50):
        chunk = missing[start : start + 50]
        data = ctx.fetch(
            (project, "identities_batch", f"{start}.json"),
            lambda chunk=chunk: c.get_list("identities", {"identityIds": ",".join(chunk)}),
            scope=project,
            collector="repos",
            endpoint="identities",
        )
        for ident in data or []:
            if not isinstance(ident, dict) or not ident.get("id"):
                continue
            props = ident.get("properties") or {}
            account = (props.get("Account") or {}).get("$value") if isinstance(props.get("Account"), dict) else None
            known[ident["id"]] = {
                "displayName": ident.get("providerDisplayName") or ident.get("customDisplayName") or ident["id"],
                "account": account,
                "isGroup": bool(ident.get("isContainer")),
            }
    ctx.store.write(known, project, "identities.json")
    return known
