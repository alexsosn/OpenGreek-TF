"""RED-first adversarial GitHub concurrency scenarios from PR #35/#36 (#37)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

import opengreek_tf.dev_claim as protocol
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
        if path.endswith("&page=1"):
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


def test_own_open_pr_exemption_requires_matching_authenticated_actor() -> None:
    linked = {"number": 38, "title": "Implement (#37)", "state": "open",
              "body": "Implements #37", "head": {"ref": "dev/37-owner"},
              "user": {"login": "alice"}}
    assert assess(37, "open", [linked], [], NOW,
                  actor="alice", own_pr_number=38).allowed
    assert not assess(37, "open", [linked], [], NOW,
                      actor="mallory", own_pr_number=38).allowed
    assert not assess(37, "open", [linked], [], NOW).allowed


def test_public_claim_token_cannot_impersonate_other_github_actor() -> None:
    claim = _comment(50, "not-a-secret", user="alice")
    assert assess(37, "open", [], [claim], NOW,
                  token="not-a-secret", actor="alice").allowed
    assert not assess(37, "open", [], [claim], NOW,
                      token="not-a-secret", actor="mallory").allowed


def test_another_active_pr_still_blocks_even_with_own_pr_exemption() -> None:
    ours = {"number": 38, "title": "Implement (#37)", "state": "open",
            "head": {"ref": "dev/37-ours"}, "user": {"login": "alice"}}
    other = {"number": 39, "title": "Implement (#37)", "state": "open",
             "head": {"ref": "dev/37-theirs"}, "user": {"login": "bob"}}
    blocked = assess(37, "open", [ours, other], [], NOW,
                     actor="alice", own_pr_number=38)
    assert not blocked.allowed
    assert blocked.active_pr_numbers == (39,)


@pytest.mark.parametrize("racing_worker", [False, True])
def test_cli_rechecks_posted_claim_and_relinquishes_if_race_lost(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    racing_worker: bool,
) -> None:
    class FakeAPI:
        def __init__(self, repo: str, token: str | None = None) -> None:
            assert repo == "alexsosn/OpenGreek-TF" and token == "fake-test-token"
            self.posted_body: str | None = None
            self.released: list[str] = []

        def snapshot(
            self, issue: int
        ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
            assert issue == 37
            comments: list[dict[str, Any]] = []
            if self.posted_body:
                created = datetime.now(UTC)
                if racing_worker:
                    comments.append({
                        "id": 20,
                        "created_at": created.isoformat(),
                        "user": {"login": "bob"},
                        "body": claim_body(37, "rival-token",
                                           created + timedelta(minutes=10)),
                    })
                comments.append({
                    "id": 21,
                    "created_at": created.isoformat(),
                    "user": {"login": "alice"},
                    "body": self.posted_body,
                })
            return "open", [], comments

        def get(self, path: str) -> dict[str, str]:
            assert path == "/user"
            return {"login": "alice"}

        def post(self, path: str, payload: dict[str, Any]) -> dict[str, int]:
            assert path == "/issues/37/comments"
            assert isinstance(payload["body"], str)
            self.posted_body = payload["body"]
            return {"id": 21}

        def patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            assert path == "/issues/comments/21"
            self.released.append(path)
            return payload

    api = FakeAPI("alexsosn/OpenGreek-TF", "fake-test-token")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-test-token")
    monkeypatch.setattr(protocol, "GithubAPI", lambda repo, token: api)
    code = protocol.main(["claim", "--issue", "37"])
    report = json.loads(capsys.readouterr().out)
    assert code == (2 if racing_worker else 0)
    assert report["allowed"] is (not racing_worker)
    assert len(api.released) == int(racing_worker)
    if not racing_worker:
        assert report["your_token"]


def test_release_succeeds_even_when_own_pr_remains_open(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Relinquishing one's comment is independent of an own open PR."""
    class FakeAPI:
        def __init__(self, repo: str, token: str | None = None) -> None:
            self.released = False

        def snapshot(
            self, issue: int
        ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
            pr = {"number": 38, "state": "open", "title": "Implement (#37)",
                  "head": {"ref": "dev/37-owned"}, "user": {"login": "alice"}}
            created = datetime.now(UTC) - timedelta(minutes=1)
            comment = {
                "id": 55, "created_at": created.isoformat(),
                "user": {"login": "alice"},
                "body": claim_body(37, "lease-owner",
                                   created + timedelta(minutes=30)),
            }
            return "open", [pr], [] if self.released else [comment]

        def get(self, path: str) -> dict[str, str]:
            assert path == "/user"
            return {"login": "alice"}

        def patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            assert path == "/issues/comments/55"
            self.released = True
            return payload

    fake = FakeAPI("alexsosn/OpenGreek-TF")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-test-token")
    monkeypatch.setattr(protocol, "GithubAPI", lambda repo, token: fake)
    code = protocol.main(["release", "--issue", "37", "--token", "lease-owner"])
    report = json.loads(capsys.readouterr().out)
    assert fake.released
    assert code == 0
    assert report["released"] is True
    assert report["remaining_preflight"]["allowed"] is False
