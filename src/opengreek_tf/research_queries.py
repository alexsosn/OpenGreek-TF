"""Source-faithful scholar-facing queries against native Text-Fabric.

The RED-stage API contract is deliberately unimplemented: tests must fail
on actual query semantics before production behavior is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class NativeResearchQueryError(ValueError):
    """Unsupported or unsafe native TF research query."""


@dataclass(frozen=True, slots=True)
class NativeResearchHit:
    kind: str
    source_file: str
    source_ordinal: int
    source_record_id: str
    source_seq: int
    text: str
    urn: str | None = None
    edition: str | None = None
    source: str | None = None
    license: str | None = None
    locus: str | None = None
    slug: str | None = None
    page: str | None = None


def search_native(
    destination: Path,
    *,
    kind: str,
    contains: str = "",
    urn: str | None = None,
    edition: str | None = None,
    source: str | None = None,
    max_results: int = 20,
) -> tuple[NativeResearchHit, ...]:
    raise NotImplementedError("RED: native Text-Fabric research queries not implemented")


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError("RED: native Text-Fabric CLI not implemented")


if __name__ == "__main__":
    raise SystemExit(main())
