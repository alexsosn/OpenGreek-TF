"""Streaming census of control codepoints in audited Open Greek text rows.

This is an evidence-gathering tool for issue #29, not a Text-Fabric serializer.
It scans *values*, including nested objects and arrays, without normalizing
Unicode or storing the source records. It never reinterprets string fields.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from itertools import chain
from pathlib import Path

from .record_stream import FieldArray, FieldObject, FieldValue, ParsedRecord, iter_family

FAMILIES = ("primary", "secondary", "paratext")


@dataclass(frozen=True, slots=True)
class ControlLocation:
    """Location of one unsupported control codepoint in the source value."""

    family: str
    relative_file: str
    ordinal: int
    field_path: str
    offset: int
    codepoint: str


@dataclass(frozen=True, slots=True)
class ControlCensus:
    """Exact aggregate counts and a bounded set of diagnostic locations."""

    records_by_family: dict[str, int]
    occurrences_by_codepoint: dict[str, int]
    crlf_pairs: int
    affected_rows: int
    samples: tuple[ControlLocation, ...]

    def as_report(self) -> dict[str, object]:
        """A deterministic JSON-safe report, containing no source text."""
        return asdict(self)


def _string_values(value: FieldValue, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, FieldArray):
        for index, item in enumerate(value.items):
            yield from _string_values(item, f"{path}[{index}]")
    elif isinstance(value, FieldObject):
        for name, item in value.items:
            yield from _string_values(item, f"{path}.{name}")


def _unsafe_control(codepoint: int) -> bool:
    """C0 except TAB/LF, plus DEL. CR requires a native TF proof."""
    return (codepoint < 32 and codepoint not in (9, 10)) or codepoint == 127


def count_controls(
    records: Iterable[ParsedRecord], *, sample_limit: int = 20,
    on_occurrence: Callable[[ControlLocation], None] | None = None
) -> ControlCensus:
    """Count controls in every nested string, preserving source/field offsets.

    Only the limited number of samples and small aggregate counters are kept.
    CRLF is counted as a CR at its own codepoint offset and as one CRLF pair.
    One physical source row with multiple controls counts once as affected.
    """

    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    records_by_family: Counter[str] = Counter()
    occurrences: Counter[str] = Counter()
    affected_rows = 0
    crlf_pairs = 0
    samples: list[ControlLocation] = []

    for record in records:
        records_by_family[record.family] += 1
        affected = False
        for name, value in record.fields.items:
            for field_path, source_text in _string_values(value, name):
                for offset, character in enumerate(source_text):
                    code = ord(character)
                    if not _unsafe_control(code):
                        continue
                    affected = True
                    codepoint = f"U+{code:04X}"
                    occurrences[codepoint] += 1
                    if character == "\r" and source_text[offset + 1:offset + 2] == "\n":
                        crlf_pairs += 1
                    if len(samples) < sample_limit or on_occurrence is not None:
                        location = ControlLocation(
                            family=record.family,
                            relative_file=record.relative_file,
                            ordinal=record.ordinal,
                            field_path=field_path,
                            offset=offset,
                            codepoint=codepoint,
                        )
                        if len(samples) < sample_limit:
                            samples.append(location)
                        if on_occurrence is not None:
                            on_occurrence(location)
        if affected:
            affected_rows += 1

    return ControlCensus(
        records_by_family=dict(sorted(records_by_family.items())),
        occurrences_by_codepoint=dict(sorted(occurrences.items())),
        crlf_pairs=crlf_pairs,
        affected_rows=affected_rows,
        samples=tuple(samples),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Scan a *local* pinned checkout; acquisition/verification is external."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="already acquired source checkout")
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument(
        "--locations-output", type=Path,
        help="optional streamed JSONL of every control location",
    )
    args = parser.parse_args(argv)
    rows = chain.from_iterable(iter_family(args.source, family) for family in FAMILIES)
    if args.locations_output is not None:
        with args.locations_output.open("w", encoding="utf-8") as output:
            def record_location(location: ControlLocation) -> None:
                output.write(json.dumps(asdict(location), sort_keys=True) + "\n")

            result = count_controls(
                rows, sample_limit=args.sample_limit, on_occurrence=record_location
            )
    else:
        result = count_controls(rows, sample_limit=args.sample_limit)
    print(json.dumps(result.as_report(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
