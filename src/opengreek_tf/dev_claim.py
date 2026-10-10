"""Advisory GitHub issue preflight and short-lived claim lease (#37).

The GitHub issue-comment protocol is convergent, not an atomic mutex.
See docs/research/issue-claims.md for explicit race windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


class ClaimError(RuntimeError):
    """A preflight or GitHub API failure: do not proceed with development."""


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


def pr_implements_issue(pr: dict[str, Any], issue: int) -> bool:
    raise NotImplementedError


def assess(
    issue: int,
    issue_state: str,
    prs: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    now: datetime,
    *,
    token: str | None = None,
) -> Decision:
    raise NotImplementedError


def claim_body(issue: int, token: str, expires_at: datetime) -> str:
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
