"""RED-first adversarial GitHub concurrency scenarios from PR #35/#36 (#37)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from opengreek_tf.dev_claim import (
    ClaimError,
    GithubAPI,
    assess,
    claim_body,
    pr_implements_issue,
)

NOW = datetime(2026, 10, 10, 16, 50, tzinfo=UTC)


def _comment(
    ident: int, token: str, *, minutes_ago: int = 3,
    lease_minutes: int = 30, user: str = "alice", issue: int = 37,
) -> dict[str, Any]:
    created = NOW - timedelta(minutes=minutes_ago)
    return {
        "id": ident,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "user": {"login": user},
        "body": claim_body(issue, token, created + timedelta(minutes=lease_minutes)),
    }


@pytest.mark.parametrize(
    ("title", "body", "branch", "wanted"),
    [
        ("Preserve facts (#33)", "", "dev/any", True),
        ("Feature", "Closes #33", "random", True),
        ("Feature", "Implementation for #33", "random", True),
        ("Feature", "", "dev/33-lossless", True),
        ("Feature", "", "feature/33/claim", True),
        ("Feature", "Related to #33", "feature/330", False),
        ("Feature", "Potential follow-up #33", "dev/333-more", False),
        ("Feature", "Closes #330", "random", False),
        ("Feature", "See also #3", "random", False),
    ],
)
def test_pr_linkage_is_exact_and_not_incidental(
    title: str, body: str, branch: str, wanted: bool,
) -> None:
    pr = {"number": 35, "title": title, "body": body,
          "head": {"ref": branch}, "state": "open"}
    assert pr_implements_issue(pr, 33) is wanted


def test_existing_open_pr_blocks_even_if_claim_expired_or_ci_queued() -> None:
    linked = {"number": 35, "title": "feat(#37)", "body": "closes #37",
              "head": {"ref": "dev/37-claim"}, "draft": True}
    result = assess(37, "open", [linked], [], NOW)
    assert result.allowed is False
    assert result.active_pr_numbers == (35,)
    assert "PR" in result.reason


def test_racing_workers_converge_on_oldest_live_comment() -> None:
    first = _comment(100, "aaa", user="worker-a")
    second = _comment(101, "bbb", user="worker-b")
    for comments in ([second, first], [first, second]):
        winner = assess(37, "open", [], comments, NOW, token="aaa")
        loser = assess(37, "open", [], comments, NOW, token="bbb")
        assert winner.allowed
        assert winner.winning_claim and winner.winning_claim.comment_id == 100
        assert not loser.allowed
        assert loser.winning_claim and loser.winning_claim.author == "worker-a"


def test_stale_claim_expires_without_privileged_cleanup() -> None:
    stale = _comment(100, "stale", minutes_ago=62, lease_minutes=120)
    fresh = _comment(101, "fresh", minutes_ago=5, lease_minutes=20)
    result = assess(37, "open", [], [stale, fresh], NOW, token="fresh")
    assert result.allowed
    assert result.winning_claim and result.winning_claim.comment_id == 101


def test_invalid_or_forged_comment_does_not_grant_ownership() -> None:
    bogus = _comment(1, "not-a-uuid")
    bogus["user"] = {}
    result = assess(37, "open", [], [bogus], NOW, token="not-a-uuid")
    assert not result.winning_claim
    assert not result.allowed or result.reason == "unclaimed"


def test_other_issue_or_inactive_claim_cannot_block() -> None:
    wrong = _comment(1, "another", issue=38)
    old = _comment(2, "expired", minutes_ago=45, lease_minutes=10)
    assert assess(37, "open", [], [wrong, old], NOW).allowed
    assert not assess(37, "closed", [], [], NOW).allowed


def test_no_token_cannot_steal_existing_claim() -> None:
    winner = _comment(2, "first")
    result = assess(37, "open", [], [winner], NOW)
    assert not result.allowed
    assert result.winning_claim and result.winning_claim.author == "alice"


def test_closed_pr_does_not_block_and_unrelated_parent_issue_does_not_block() -> None:
    prs = [
        {"number": 35, "title": "Done (#37)", "state": "closed",
         "head": {"ref": "feature/37-old"}},
        {"number": 36, "title": "Research for #3", "state": "open",
         "head": {"ref": "feature/3-other"}, "body": "Related to #37"},
    ]
    assert assess(37, "open", prs, [], NOW).allowed


def test_full_pages_and_page_overflow_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    api = GithubAPI("alexsosn/OpenGreek-TF")
    seen: list[str] = []

    def fake_get(path: str) -> Any:
        seen.append(path)
        if "page=1" in path:
            return [{"id": n} for n in range(100)]
        return [{"id": 999}]

    monkeypatch.setattr(api, "get", fake_get)
    rows = api.pages("/issues/37/comments")
    assert len(rows) == 101
    assert len(seen) == 2
    monkeypatch.setattr(api, "get", lambda _: {"message": "rate limited"})
    with pytest.raises(ClaimError):
        api.pages("/issues/37/comments")


def test_snapshot_fetches_issue_and_all_open_prs_and_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = GithubAPI("alexsosn/OpenGreek-TF")
    def fake_get(path: str) -> Any:
        if path == "/issues/37":
            return {"state": "open"}
        if "pulls?" in path:
            return [{"number": 35, "title": "Related to #37",
                     "head": {"ref": "unrelated"}}]
        if "comments?" in path:
            return []
        raise AssertionError(path)

    monkeypatch.setattr(api, "get", fake_get)
    state, prs, comments = api.snapshot(37)
    assert state == "open" and len(prs) == 1 and comments == []
