"""Read-only evidence probe for non-unique source locus labels.

This deliberately measures row occurrences, not citation equivalence. It hashes
passage text without copying text into a diagnostic report.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class LocusProbeError(RuntimeError):
    """Malformed source row or unreadable probe input."""


@dataclass(slots=True)
class _Group:
    count: int = 0
    text_hashes: set[str] = field(default_factory=set)
    pages: set[str] = field(default_factory=set)
    editions: set[str] = field(default_factory=set)
    witnesses: set[str] = field(default_factory=set)
    positions: list[int] = field(default_factory=list)

    def add(self, row: dict[str, Any], position: int) -> None:
        self.count += 1
        self.text_hashes.add(hashlib.sha256(row["text"].encode("utf-8")).hexdigest())
        for key, target in (
            ("page", self.pages),
            ("edition", self.editions),
            ("witness", self.witnesses),
        ):
            value = row.get(key)
            if value is not None:
                target.add(str(value))
        if len(self.positions) < 8:
            self.positions.append(position)

    def render(self, locus: str) -> dict[str, Any]:
        return {
            "locus": locus,
            "count": self.count,
            "same_text": len(self.text_hashes) == 1,
            "distinct_text_hashes": len(self.text_hashes),
            "pages": sorted(self.pages),
            "editions": sorted(self.editions),
            "witnesses": sorted(self.witnesses),
            "positions": self.positions,
        }


def analyze_loci(source: str | Path, *, max_groups: int = 20) -> dict[str, Any]:
    """Classify repeated literal locus labels in an ordered JSONL source file."""
    if max_groups < 0:
        raise ValueError("max_groups must be non-negative")

    path = Path(source)
    groups: dict[str, _Group] = {}
    rows = 0
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise LocusProbeError(
                        f"blank JSONL row at {path}:{line_number}"
                    )
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LocusProbeError(
                        f"invalid JSON at {path}:{line_number}"
                    ) from exc
                if not isinstance(row, dict):
                    raise LocusProbeError(
                        f"JSONL row is not an object at {path}:{line_number}"
                    )
                locus, value = row.get("locus"), row.get("text")
                if not isinstance(locus, str):
                    raise LocusProbeError(
                        f"invalid locus at {path}:{line_number}"
                    )
                if not isinstance(value, str):
                    raise LocusProbeError(
                        f"invalid text at {path}:{line_number}"
                    )
                rows += 1
                groups.setdefault(locus, _Group()).add(row, rows)
    except (OSError, UnicodeError) as exc:
        raise LocusProbeError(f"cannot read source JSONL: {path}") from exc

    collisions = {locus: group for locus, group in groups.items() if group.count > 1}
    top = sorted(collisions.items(), key=lambda kv: (-kv[1].count, kv[0]))
    return {
        "file": path.name,
        "rows": rows,
        "distinct_loci": len(groups),
        "collision_groups": len(collisions),
        "repeated_occurrences": sum(g.count - 1 for g in collisions.values()),
        "colliding_rows": sum(g.count for g in collisions.values()),
        "same_text_groups": sum(len(g.text_hashes) == 1 for g in collisions.values()),
        "different_text_groups": sum(len(g.text_hashes) > 1 for g in collisions.values()),
        "different_page_groups": sum(len(g.pages) > 1 for g in collisions.values()),
        "different_edition_groups": sum(len(g.editions) > 1 for g in collisions.values()),
        "different_witness_groups": sum(len(g.witnesses) > 1 for g in collisions.values()),
        "top_groups": [g.render(locus) for locus, g in top[:max_groups]],
    }
