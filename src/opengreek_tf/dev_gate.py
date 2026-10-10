"""Advisory exact-head premerge proof gate for autonomous development (#37)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dev_claim import GithubAPI


class MergeGateError(RuntimeError):
    """Cannot establish safe review/CI/base evidence for this pull request."""


@dataclass(frozen=True)
class MergeGateResult:
    pr_number: int
    head_sha: str
    base_sha: str
    workflow_names: tuple[str, ...]
    review_ids: tuple[int, ...]


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
    raise NotImplementedError


def fetch_runs(api: GithubAPI, head_sha: str) -> list[dict[str, Any]]:
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
