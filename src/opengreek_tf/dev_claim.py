"""Fail-closed GitHub issue preflight and convergent advisory lease (#37).

This is NOT an atomic mutex. Recheck live PR/lease state before opening a PR,
before pushing substantive changes, and before merging.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

_MARKER = re.compile(r"^<!-- opengreek-dev-claim:v1 (\{.*\}) -->$", re.DOTALL)
_TOKEN = re.compile(r"[A-Za-z0-9-]{3,128}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MAX_LEASE_MINUTES = 60
MAX_PAGES = 20


class ClaimError(RuntimeError):
    """Unsafe or incomplete preflight; stop instead of treating failure as free."""


@dataclass(frozen=True)
class Claim:
    issue: int
    token: str
    author: str
    comment_id: int
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    active_pr_numbers: tuple[int, ...]
    winning_claim: Claim | None = None


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing GitHub timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("naive GitHub timestamp")
    return parsed.astimezone(UTC)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate claim field")
        result[key] = value
    return result


def claim_body(issue: int, token: str, expires_at: datetime) -> str:
    """Create a parseable machine comment; token is NOT an authorization secret."""
    if issue < 1 or not _TOKEN.fullmatch(token):
        raise ClaimError("invalid issue or advisory claim token")
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise ClaimError("claim expiration must have timezone")
    stamp = expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    data = json.dumps(
        {"issue": issue, "token": token, "expires": stamp},
        sort_keys=True, separators=(",", ":"),
    )
    return f"<!-- opengreek-dev-claim:v1 {data} -->"


def _parse_claim(comment: dict[str, Any], issue: int, now: datetime) -> Claim | None:
    body = comment.get("body")
    matched = _MARKER.fullmatch(body.strip()) if isinstance(body, str) else None
    if not matched:
        return None
    try:
        data = json.loads(
            matched.group(1), object_pairs_hook=_object_without_duplicate_keys
        )
        if not isinstance(data, dict) or set(data) != {"issue", "token", "expires"}:
            return None
        if type(data["issue"]) is not int or data["issue"] != issue:
            return None
        token = data["token"]
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            return None
        user = comment.get("user")
        author = user.get("login") if isinstance(user, dict) else None
        ident = comment.get("id")
        if not isinstance(author, str) or not author or type(ident) is not int:
            return None
        created = _datetime(comment.get("created_at"))
        expires = _datetime(data["expires"])
        # A claim cannot live forever, even when an edited comment says so.
        if created > now + timedelta(seconds=30):
            return None
        if not created < expires <= created + timedelta(minutes=MAX_LEASE_MINUTES):
            return None
        if expires <= now:
            return None
        return Claim(issue, token, author, ident, created, expires)
    except (ValueError, TypeError, KeyError):
        return None


def pr_implements_issue(pr: dict[str, Any], issue: int) -> bool:
    """Recognize direct work references, not every incidental issue mention."""
    if pr.get("state", "open") != "open":
        return False
    title = pr.get("title")
    body = pr.get("body")
    head = pr.get("head")
    branch = head.get("ref", "") if isinstance(head, dict) else ""
    if not isinstance(branch, str):
        branch = ""
    if re.match(rf"^(?:dev|feature|issue|fix|research)/{issue}(?:[-/]|$)", branch):
        return True
    if isinstance(title, str):
        if re.search(rf"\(#{issue}\)|^\s*#{issue}\b", title):
            return True
    for text in (title, body):
        if isinstance(text, str) and re.search(
            rf"\b(?:for|issue|implement(?:s|ation)?|fix(?:es|ed)?|"
            rf"close(?:s|d)?|resolve(?:s|d)?|working\s+on)\s*:?\s*#{issue}\b",
            text, flags=re.IGNORECASE,
        ):
            return True
    return False


def assess(
    issue: int,
    issue_state: str,
    prs: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    now: datetime,
    *,
    token: str | None = None,
    actor: str | None = None,
    own_pr_number: int | None = None,
) -> Decision:
    """Independently inspect complete live snapshots; oldest active comment wins."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ClaimError("preflight requires an aware current time")
    if issue < 1 or issue_state != "open":
        return Decision(False, "issue is not open", ())
    active_prs: set[int] = set()
    for pr in prs:
        if pr_implements_issue(pr, issue):
            number = pr.get("number")
            if type(number) is not int or number < 1:
                raise ClaimError("linked open PR missing valid number")
            owner = pr.get("user")
            author = owner.get("login") if isinstance(owner, dict) else None
            if (
                actor is not None
                and own_pr_number == number
                and actor == author
            ):
                continue
            active_prs.add(number)
    if active_prs:
        ids = tuple(sorted(active_prs))
        return Decision(False, f"active implementing PR(s): {ids}", ids)
    candidates = [
        claim for entry in comments
        if (claim := _parse_claim(entry, issue, now)) is not None
    ]
    if not candidates:
        return Decision(True, "unclaimed", ())
    winner = min(candidates, key=lambda c: (c.comment_id, c.created_at))
    if token is not None and token == winner.token and (
        actor is None or actor == winner.author
    ):
        return Decision(True, "current token holds advisory lease", (), winner)
    return Decision(False, f"claimed by {winner.author} (comment {winner.comment_id})",
                    (), winner)


class GithubAPI:
    """Minimal GitHub REST transport that never treats partial reads as success."""

    def __init__(self, repo: str, token: str | None = None) -> None:
        if not _REPO.fullmatch(repo):
            raise ClaimError("repository must be in owner/name format")
        self.repo = repo
        self.token = token

    def _call(
        self, method: str, path: str, payload: dict[str, Any] | None = None,
    ) -> object:
        if not path.startswith("/") or "://" in path or ".." in path:
            raise ClaimError("invalid GitHub API path")
        api_path = path if path == "/user" else f"/repos/{self.repo}{path}"
        url = f"https://api.github.com{api_path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "OpenGreek-TF-issue-preflight",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if method != "GET" and not self.token:
            raise ClaimError("GITHUB_TOKEN required for writes")
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        try:
            with urlopen(Request(url, data=data, headers=headers, method=method),
                         timeout=20) as response:
                value: object = json.load(response)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise ClaimError(f"GitHub API {method} {path} failed: {exc}") from exc
        if not isinstance(value, (list, dict)):
            raise ClaimError(f"unexpected GitHub API payload for {path}")
        return value

    def get(self, path: str) -> Any:
        return self._call("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._call("POST", path, payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self._call("PATCH", path, payload)

    def pages(self, path: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            sep = "&" if "?" in path else "?"
            value: object = self.get(f"{path}{sep}per_page=100&page={page}")
            if not isinstance(value, list):
                raise ClaimError("GitHub list response is incomplete or malformed")
            if len(value) > 100 or any(not isinstance(item, dict) for item in value):
                raise ClaimError("invalid GitHub paginated item")
            rows.extend(cast(list[dict[str, Any]], value))
            if len(value) < 100:
                return rows
        raise ClaimError("GitHub list exceeds safe pagination limit")

    def snapshot(
        self, issue: int
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        details: object = self.get(f"/issues/{issue}")
        if not isinstance(details, dict) or details.get("state") not in ("open", "closed"):
            raise ClaimError("GitHub issue state cannot be verified")
        state = details["state"]
        prs = self.pages("/pulls?state=open")
        comments = self.pages(f"/issues/{issue}/comments")
        return cast(str, state), prs, comments


def _emit(decision: Decision, token: str | None = None) -> None:
    info: dict[str, Any] = {
        "allowed": decision.allowed, "reason": decision.reason,
        "active_pr_numbers": decision.active_pr_numbers,
    }
    if decision.winning_claim:
        c = decision.winning_claim
        info["claim"] = {
            "author": c.author, "comment_id": c.comment_id,
            "expires_at": c.expires_at.isoformat(),
        }
    if token is not None and decision.allowed:
        info["your_token"] = token
    print(json.dumps(info, sort_keys=True))


def _actor(api: GithubAPI) -> str:
    if not api.token:
        raise ClaimError("GITHUB_TOKEN required to authenticate claim owner")
    user: object = api.get("/user")
    if not isinstance(user, dict) or not isinstance(user.get("login"), str):
        raise ClaimError("authenticated GitHub actor not verified")
    return cast(str, user["login"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "claim", "release"))
    parser.add_argument("--repo", default="alexsosn/OpenGreek-TF")
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--token", help="previously issued advisory lease token")
    parser.add_argument("--own-pr", type=int,
                        help="exempt only this PR, if its author is the verified actor")
    parser.add_argument("--lease-minutes", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        api = GithubAPI(args.repo, os.environ.get("GITHUB_TOKEN"))
        now = datetime.now(UTC)
        state, prs, comments = api.snapshot(args.issue)
        if args.action == "release":
            if not args.token:
                raise ClaimError("release requires --token")
            releasing_actor = _actor(api)
            own = [
                c for item in comments
                if (c := _parse_claim(item, args.issue, now)) is not None
                and c.token == args.token and c.author == releasing_actor
            ]
            if len(own) != 1:
                raise ClaimError("no unique live claim owned by authenticated actor")
            api.patch(
                f"/issues/comments/{own[0].comment_id}",
                {"body": f"<!-- opengreek-dev-claim:released #{args.issue} -->"},
            )
            state, prs, comments = api.snapshot(args.issue)
            check_time = datetime.now(UTC)
            if any(
                (remaining := _parse_claim(item, args.issue, check_time)) is not None
                and remaining.token == args.token
                and remaining.author == releasing_actor
                for item in comments
            ):
                raise ClaimError("GitHub still reports the released lease as active")
            result = assess(args.issue, state, prs, comments, check_time)
            print(json.dumps({
                "released": True,
                "comment_id": own[0].comment_id,
                "remaining_preflight": {
                    "allowed": result.allowed,
                    "reason": result.reason,
                    "active_pr_numbers": result.active_pr_numbers,
                },
            }, sort_keys=True))
            return 0

        actor = _actor(api) if args.token or args.own_pr is not None else None
        decision = assess(args.issue, state, prs, comments, now,
                          token=args.token, actor=actor,
                          own_pr_number=args.own_pr)
        if args.action == "check":
            _emit(decision)
            return 0 if decision.allowed else 2
        if args.lease_minutes < 1 or args.lease_minutes > MAX_LEASE_MINUTES:
            raise ClaimError("lease minutes must be between 1 and 60")
        if not decision.allowed:
            _emit(decision)
            return 2
        if decision.winning_claim and args.token == decision.winning_claim.token:
            _actor(api)
            _emit(decision, args.token)
            return 0
        _actor(api)
        new_token: str = str(uuid4())
        body = claim_body(args.issue, new_token, now + timedelta(minutes=args.lease_minutes))
        posted: object = api.post(f"/issues/{args.issue}/comments", {"body": body})
        if not isinstance(posted, dict) or type(posted.get("id")) is not int:
            raise ClaimError("GitHub did not confirm the new lease comment")
        state, prs, comments = api.snapshot(args.issue)
        decision = assess(args.issue, state, prs, comments, datetime.now(UTC),
                          token=new_token, actor=actor, own_pr_number=args.own_pr)
        if not decision.allowed or not decision.winning_claim or (
            decision.winning_claim.comment_id != posted["id"]
        ):
            # Never leave a losing claim in place to block later workers.
            api.patch(
                f"/issues/comments/{posted['id']}",
                {"body": f"<!-- opengreek-dev-claim:lost-race #{args.issue} -->"},
            )
            _emit(decision)
            return 2
        _emit(decision, new_token)
        return 0
    except ClaimError as exc:
        print(f"preflight cannot proceed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
