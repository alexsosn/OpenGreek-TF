"""Advisory exact-head premerge proof gate for autonomous development (#37).

Read-only evidence preflight, not an atomic lock or an automatic merge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .dev_claim import ClaimError, GithubAPI, _actor, assess, pr_implements_issue

_SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_RUN_PAGES = 20


class MergeGateError(RuntimeError):
    """Cannot establish exact-head review, CI and unchanged base evidence."""


@dataclass(frozen=True)
class MergeGateResult:
    pr_number: int
    head_sha: str
    base_sha: str
    workflow_names: tuple[str, ...]
    review_ids: tuple[int, ...]


def _sha(value: object) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise MergeGateError("missing full immutable Git SHA")
    return value


def _obj(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MergeGateError(f"invalid {label}")
    return value


def _pr_id_matches(
    run: dict[str, Any], pr_number: int, head_sha: str, base_sha: str,
) -> bool:
    prs: object = run.get("pull_requests")
    if not isinstance(prs, list):
        raise MergeGateError("workflow run missing PR association data")
    for entry in prs:
        candidate = _obj(entry, "workflow PR association")
        if candidate.get("number") != pr_number:
            continue
        head = _obj(candidate.get("head"), "workflow PR head")
        base = _obj(candidate.get("base"), "workflow PR base")
        if head.get("sha") != head_sha or base.get("sha") != base_sha:
            return False
        return True
    return False


def evaluate_merge_gate(
    pr_number: int,
    issue_number: int,
    pr: dict[str, Any],
    main: dict[str, Any],
    runs: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    *,
    repo: str,
    required_workflows: tuple[str, ...],
) -> MergeGateResult:
    """Check independent, complete GitHub snapshots without ever merging."""
    if (
        pr_number < 1
        or issue_number < 1
        or not required_workflows
        or any(not n.strip() for n in required_workflows)
        or len(set(required_workflows)) != len(required_workflows)
    ):
        raise MergeGateError("invalid gate input or missing required workflow")
    if (
        pr.get("number") != pr_number
        or pr.get("state") != "open"
        or pr.get("draft") is not False
        or pr.get("mergeable") is not True
        or not pr_implements_issue(pr, issue_number)
    ):
        raise MergeGateError("PR closed, draft, conflicting or unrelated to issue")
    head = _obj(pr.get("head"), "PR head")
    base = _obj(pr.get("base"), "PR base")
    head_sha = _sha(head.get("sha"))
    base_sha = _sha(base.get("sha"))
    if (
        _obj(head.get("repo"), "PR head repository").get("full_name") != repo
        or _obj(base.get("repo"), "PR base repository").get("full_name") != repo
        or base.get("ref") != "main"
        or main.get("name") != "main"
    ):
        raise MergeGateError("PR does not target the expected main repository")
    live_base = _sha(_obj(main.get("commit"), "main commit").get("sha"))
    if base_sha != live_base:
        raise MergeGateError("PR base is stale relative to current main")
    successful_workflows: list[str] = []
    for workflow in required_workflows:
        candidates: list[dict[str, Any]] = []
        for run in runs:
            if not isinstance(run, dict):
                raise MergeGateError("invalid workflow result record")
            if (
                run.get("name") == workflow
                and run.get("head_sha") == head_sha
                and run.get("event") == "pull_request"
                and _pr_id_matches(run, pr_number, head_sha, base_sha)
            ):
                candidates.append(run)
        if not candidates:
            raise MergeGateError(f"missing matching exact-head workflow {workflow}")
        for run in candidates:
            if type(run.get("id")) is not int or type(run.get("run_attempt")) is not int:
                raise MergeGateError(f"malformed workflow metadata: {workflow}")
        latest = max(candidates, key=lambda r: (r["id"], r["run_attempt"]))
        if latest.get("status") != "completed" or latest.get("conclusion") != "success":
            raise MergeGateError(f"required workflow not green on latest run: {workflow}")
        successful_workflows.append(workflow)
    fresh: list[int] = []
    for review in reviews:
        if not isinstance(review, dict):
            raise MergeGateError("invalid review record")
        if review.get("commit_id") != head_sha:
            continue
        state = review.get("state")
        if state == "CHANGES_REQUESTED":
            raise MergeGateError("review requests changes on current PR head")
        if state in {"COMMENTED", "APPROVED"}:
            rid, body = review.get("id"), review.get("body")
            if type(rid) is int and isinstance(body, str) and len(body.strip()) >= 60:
                fresh.append(rid)
    if not fresh:
        raise MergeGateError("missing substantive review on exact PR head")
    return MergeGateResult(
        pr_number, head_sha, base_sha, tuple(successful_workflows),
        tuple(sorted(set(fresh))),
    )


def fetch_runs(api: GithubAPI, head_sha: str) -> list[dict[str, Any]]:
    """Retrieve every exact-head run, rejecting inconsistent/paged API data."""
    _sha(head_sha)
    rows: list[dict[str, Any]] = []
    total: int | None = None
    for page in range(1, MAX_RUN_PAGES + 1):
        response = _obj(
            api.get(f"/actions/runs?head_sha={head_sha}&per_page=100&page={page}"),
            "workflow runs response",
        )
        count, part = response.get("total_count"), response.get("workflow_runs")
        if (
            type(count) is not int
            or count < 0
            or count > MAX_RUN_PAGES * 100
            or not isinstance(part, list)
            or len(part) > 100
            or any(not isinstance(item, dict) for item in part)
        ):
            raise MergeGateError("incomplete or malformed paginated workflow list")
        if total is None:
            total = count
        elif total != count:
            raise MergeGateError("workflow run list changed during pagination")
        rows.extend(part)
        if len(rows) > count:
            raise MergeGateError("workflow response exceeds stated total")
        if len(rows) == count:
            identifiers = [(item.get("id"), item.get("run_attempt")) for item in rows]
            if len(set(identifiers)) != len(identifiers):
                raise MergeGateError("repeated workflow results across pages")
            return rows
        if len(part) != 100:
            raise MergeGateError("truncated workflow run pagination")
    raise MergeGateError("workflow pagination exceeds supported safety limit")


def _stable(
    before: dict[str, Any], after: dict[str, Any],
    earlier_main: dict[str, Any], later_main: dict[str, Any],
) -> bool:
    for side in ("head", "base"):
        if _obj(before.get(side), f"original PR {side}").get("sha") != _obj(
            after.get(side), f"latest PR {side}"
        ).get("sha"):
            return False
    if earlier_main != later_main:
        return False
    return (
        before.get("state") == after.get("state")
        and before.get("draft") == after.get("draft")
        and before.get("mergeable") == after.get("mergeable")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="alexsosn/OpenGreek-TF")
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--token", help="existing winning advisory issue claim token")
    parser.add_argument(
        "--require-workflow", action="append", required=True,
        help="exact required Actions workflow display name; repeat for all gates",
    )
    args = parser.parse_args(argv)
    try:
        api = GithubAPI(args.repo, os.environ.get("GITHUB_TOKEN"))
        actor = _actor(api)
        state, prs, comments = api.snapshot(args.issue)
        check = assess(
            args.issue, state, prs, comments, datetime.now(UTC),
            token=args.token, actor=actor, own_pr_number=args.pr,
        )
        if not check.allowed:
            raise MergeGateError(f"issue/PR is actively owned by another agent: {check.reason}")
        first: object = api.get(f"/pulls/{args.pr}")
        main_branch: object = api.get("/branches/main")
        pr = _obj(first, "PR")
        base = _obj(main_branch, "main branch")
        head_sha = _sha(_obj(pr.get("head"), "PR head").get("sha"))
        runs = fetch_runs(api, head_sha)
        reviews = api.pages(f"/pulls/{args.pr}/reviews")
        result = evaluate_merge_gate(
            args.pr, args.issue, pr, base, runs, reviews,
            repo=args.repo, required_workflows=tuple(args.require_workflow),
        )
        second = _obj(api.get(f"/pulls/{args.pr}"), "final PR")
        later_main = _obj(api.get("/branches/main"), "final main branch")
        state, prs, comments = api.snapshot(args.issue)
        latest = assess(
            args.issue, state, prs, comments, datetime.now(UTC),
            token=args.token, actor=actor, own_pr_number=args.pr,
        )
        if not latest.allowed or not _stable(pr, second, base, later_main):
            raise MergeGateError("PR/main/claim state changed during gate")
        print(json.dumps({
            "allowed": True,
            "head_sha": result.head_sha,
            "base_sha": result.base_sha,
            "required_workflows": result.workflow_names,
            "review_ids": result.review_ids,
            "warning": "advisory only; merge must still enforce expected_head_sha",
        }, sort_keys=True))
        return 0
    except MergeGateError as exc:
        print(f"merge blocked: {exc}", file=sys.stderr)
        return 2
    except ClaimError as exc:
        print(f"merge check API failed closed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
