"""RED-first GitHub merge-safety regressions from the real PR #35/#36 collision."""

from __future__ import annotations

import json
from typing import Any

import pytest

import opengreek_tf.dev_gate as gate_module
from opengreek_tf.dev_claim import GithubAPI
from opengreek_tf.dev_gate import (
    MergeGateError,
    evaluate_merge_gate,
    fetch_runs,
)

HEAD = "a" * 40
BASE = "b" * 40
REPO = "alexsosn/OpenGreek-TF"
ISSUE = 37
PR = 42


def _pr() -> dict[str, Any]:
    return {
        "number": PR,
        "state": "open",
        "draft": False,
        "mergeable": True,
        "title": "Check exact head on issue #37",
        "head": {
            "sha": HEAD, "ref": "dev/37-premerge-exact-head-gate",
            "repo": {"full_name": REPO},
        },
        "base": {
            "sha": BASE, "ref": "main",
            "repo": {"full_name": REPO},
        },
    }


def _main() -> dict[str, Any]:
    return {"name": "main", "commit": {"sha": BASE}}


def _run(
    name: str = "CI", *,
    head: str = HEAD,
    number: int = PR,
    conclusion: str | None = "success",
    status: str = "completed",
    run_id: int = 100,
    attempt: int = 1,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": name,
        "head_sha": head,
        "head_branch": "dev/37-premerge-exact-head-gate",
        "status": status,
        "conclusion": conclusion,
        "event": "pull_request",
        "run_attempt": attempt,
        "pull_requests": [{"number": number, "base": {"sha": BASE}, "head": {"sha": head}}],
    }


def _review(
    commit: str = HEAD, *, state: str = "COMMENTED", review_id: int = 500,
) -> dict[str, Any]:
    return {
        "id": review_id,
        "commit_id": commit,
        "state": state,
        "body": "Independent skeptical review grounded in actual diff, source data, "
                "reproducible test failures and workflow logs.",
    }


def _gate(
    *,
    pr: dict[str, Any] | None = None,
    main: dict[str, Any] | None = None,
    runs: list[dict[str, Any]] | None = None,
    reviews: list[dict[str, Any]] | None = None,
    required: tuple[str, ...] = ("CI", "Pinned strict source-stream census"),
) -> Any:
    return evaluate_merge_gate(
        PR, ISSUE, _pr() if pr is None else pr,
        _main() if main is None else main,
        [_run(), _run("Pinned strict source-stream census", run_id=101)]
        if runs is None else runs,
        [_review()] if reviews is None else reviews,
        repo=REPO,
        required_workflows=required,
    )


def test_green_only_with_exact_live_base_head_pr_ci_and_review() -> None:
    result = _gate()
    assert result.head_sha == HEAD
    assert result.base_sha == BASE
    assert result.pr_number == PR
    assert result.workflow_names == ("CI", "Pinned strict source-stream census")
    assert result.review_ids == (500,)


@pytest.mark.parametrize(
    "change",
    [
        {"commit": {"sha": "f" * 40}},
        {"commit": {"sha": ""}},
        {},
    ],
)
def test_main_advanced_while_pr_waited_for_ci_fails_closed(change: dict[str, Any]) -> None:
    with pytest.raises(MergeGateError, match="base|main"):
        _gate(main=change)


def test_old_green_runs_and_old_review_do_not_approve_new_head() -> None:
    changed = _pr()
    changed["head"]["sha"] = "f" * 40
    with pytest.raises(MergeGateError, match="CI|workflow|head"):
        _gate(pr=changed)


@pytest.mark.parametrize("state,conclusion", [
    ("queued", None), ("in_progress", None),
    ("completed", "failure"), ("completed", "cancelled"),
])
def test_unfinished_or_failed_newer_run_blocks_old_green(
    state: str, conclusion: str | None,
) -> None:
    runs = [_run(run_id=99), _run(run_id=100, status=state, conclusion=conclusion)]
    with pytest.raises(MergeGateError, match="CI|workflow"):
        _gate(runs=runs, required=("CI",))


def test_newer_rerun_attempt_supersedes_earlier_success() -> None:
    runs = [_run(run_id=88), _run(run_id=88, attempt=2, status="queued", conclusion=None)]
    with pytest.raises(MergeGateError):
        _gate(runs=runs, required=("CI",))


def test_missing_required_workflow_cannot_be_inferred_from_ci_success() -> None:
    with pytest.raises(MergeGateError, match="Pinned"):
        _gate(runs=[_run()])


def test_shared_sha_but_different_pr_is_not_proof() -> None:
    with pytest.raises(MergeGateError):
        _gate(runs=[_run(number=41)], required=("CI",))


def test_missing_pr_association_is_fail_closed() -> None:
    run = _run()
    run["pull_requests"] = []
    with pytest.raises(MergeGateError):
        _gate(runs=[run], required=("CI",))


@pytest.mark.parametrize("state", ["CHANGES_REQUESTED", "DISMISSED"])
def test_unusable_review_cannot_approve_even_when_ci_green(state: str) -> None:
    with pytest.raises(MergeGateError, match="review"):
        _gate(reviews=[_review(state=state)])


def test_review_of_previous_head_and_changes_requested_block() -> None:
    with pytest.raises(MergeGateError, match="review"):
        _gate(reviews=[_review(commit="f" * 40)])
    with pytest.raises(MergeGateError, match="review"):
        _gate(reviews=[_review(), _review(state="CHANGES_REQUESTED", review_id=501)])


@pytest.mark.parametrize("patch", [
    {"state": "closed"}, {"draft": True}, {"mergeable": False},
    {"title": "Unrelated issue #20"},
])
def test_closed_draft_conflicted_or_unrelated_pr_cannot_pass(patch: dict[str, Any]) -> None:
    pr = _pr()
    pr.update(patch)
    with pytest.raises(MergeGateError):
        _gate(pr=pr)


def test_paginated_workflow_runs_and_incomplete_response_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = GithubAPI(REPO)
    calls: list[str] = []

    def get(path: str) -> Any:
        calls.append(path)
        if path.endswith("&page=1"):
            return {
                "total_count": 101,
                "workflow_runs": [_run(run_id=n + 1) for n in range(100)],
            }
        if path.endswith("&page=2"):
            return {"total_count": 101, "workflow_runs": [_run(run_id=101)]}
        raise AssertionError(path)

    monkeypatch.setattr(api, "get", get)
    items = fetch_runs(api, HEAD)
    assert len(items) == 101
    assert len(calls) == 2
    monkeypatch.setattr(api, "get", lambda _: {"total_count": 101})
    with pytest.raises(MergeGateError):
        fetch_runs(api, HEAD)


def test_inconsistent_pagination_counts_cannot_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = GithubAPI(REPO)
    monkeypatch.setattr(
        api, "get",
        lambda _: {"total_count": 101, "workflow_runs": [_run()]},
    )
    with pytest.raises(MergeGateError):
        fetch_runs(api, HEAD)


def test_ci_on_same_head_against_previous_base_is_not_current_green() -> None:
    run = _run()
    run["pull_requests"][0]["base"]["sha"] = "f" * 40
    with pytest.raises(MergeGateError, match="base|CI"):
        _gate(runs=[run], required=("CI",))


@pytest.mark.parametrize("race", ["none", "base-advanced", "new-pr"])
def test_cli_rechecks_live_state_after_ci_review_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    race: str,
) -> None:
    """The CLI must not report success if main or issue ownership moves."""
    class FakeAPI:
        token = "fixture-token"

        def __init__(self) -> None:
            self.base_calls = 0
            self.snapshot_calls = 0

        def snapshot(
            self, issue: int
        ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
            assert issue == ISSUE
            self.snapshot_calls += 1
            ours = {
                "number": PR,
                "state": "open",
                "title": "Implement issue #37",
                "head": {"ref": "dev/37-premerge"},
                "user": {"login": "alice"},
            }
            other = {
                "number": 43,
                "state": "open",
                "title": "Implement issue #37",
                "head": {"ref": "dev/37-racing"},
                "user": {"login": "bob"},
            }
            return "open", [ours, other] if (
                race == "new-pr" and self.snapshot_calls == 2
            ) else [ours], []

        def get(self, path: str) -> Any:
            if path == "/user":
                return {"login": "alice"}
            if path == f"/pulls/{PR}":
                return _pr()
            if path == "/branches/main":
                self.base_calls += 1
                return (
                    {"name": "main", "commit": {"sha": "f" * 40}}
                    if race == "base-advanced" and self.base_calls == 2
                    else _main()
                )
            if path.startswith("/actions/runs?head_sha="):
                return {"total_count": 1, "workflow_runs": [_run()]}
            raise AssertionError(path)

        def pages(self, path: str) -> list[dict[str, Any]]:
            assert path == f"/pulls/{PR}/reviews"
            return [_review()]

    fake = FakeAPI()
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    monkeypatch.setattr(
        gate_module, "GithubAPI", lambda repo, token: fake,
    )
    code = gate_module.main([
        "--issue", str(ISSUE), "--pr", str(PR),
        "--require-workflow", "CI",
    ])
    output = capsys.readouterr()
    if race == "none":
        assert code == 0
        assert json.loads(output.out)["head_sha"] == HEAD
    else:
        assert code == 2
        assert output.out == ""
        assert "merge blocked" in output.err
    assert fake.snapshot_calls == 2
