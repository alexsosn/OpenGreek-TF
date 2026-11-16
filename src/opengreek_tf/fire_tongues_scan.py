"""Exhaustive lexical proximity scan of all pinned Open Greek text families.

This generates a recall-oriented candidate list, NOT a chronological verdict.
Usage: python scripts/scan_fire_tongues.py upstream --output results
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

from .source import verify_source

FAMILIES = {
    "primary": ("corpus", 3909, 1_970_947),
    "secondary": ("corpus_secondary", 533, 307_085),
    "paratext": ("paratext", 5, 15_958),
}
WINDOW = 160
TONGUE = re.compile(r"γλωσσ|γλωττ")
# Core fire lexemes; expanded stems intentionally over-retrieve.
FIRE = re.compile(r"πυρ|φλογ|φλεγ|φλεξ|φλοξ|καιο|καιε|καιει|καυ|αιθ|εμπρησ")
CORE = ("πυρ", "φλογ", "φλεγ", "φλεξ", "φλοξ")


class Pair(TypedDict):
    tongue_offset: int
    fire_offset: int
    distance: int
    fire_root: str
    tier: str



def fold(text: str) -> str:
    """Case- and accent-insensitive Greek, preserving original source text elsewhere."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text).casefold()
        if not unicodedata.combining(ch)
    )


def matches_normalized(normalized: str, window: int = WINDOW) -> list[Pair]:
    """Every tongue/fire pair within the given normalized-character distance."""
    tongues = list(TONGUE.finditer(normalized))
    fires = list(FIRE.finditer(normalized))
    fire_positions = [f.start() for f in fires]
    found: list[Pair] = []
    for t in tongues:
        left = bisect.bisect_left(fire_positions, t.start() - window)
        right = bisect.bisect_right(fire_positions, t.start() + window)
        for f in fires[left:right]:
            found.append({
                "tongue_offset": t.start(),
                "fire_offset": f.start(),
                "distance": abs(t.start() - f.start()),
                "fire_root": f.group(),
                "tier": "core" if f.group().startswith(CORE) else "expanded",
            })
    return found


def matches(text: str, window: int = WINDOW) -> list[Pair]:
    """Public helper for unnormalized Greek source text."""
    return matches_normalized(fold(text), window)


def nearest_distant(normalized: str) -> Pair | None:
    """Keep a work in the inventory even if its terms are >WINDOW apart."""
    tongues = list(TONGUE.finditer(normalized))
    fires = list(FIRE.finditer(normalized))
    if not tongues or not fires:
        return None
    positions = [f.start() for f in fires]
    closest: Pair | None = None
    for tongue in tongues:
        index = bisect.bisect_left(positions, tongue.start())
        for neighbor in (index - 1, index):
            if 0 <= neighbor < len(fires):
                fire = fires[neighbor]
                distance = abs(tongue.start() - fire.start())
                if closest is None or distance < closest["distance"]:
                    closest = {
                        "tongue_offset": tongue.start(),
                        "fire_offset": fire.start(),
                        "distance": distance,
                        "fire_root": fire.group(),
                        "tier": "core" if fire.group().startswith(CORE) else "expanded",
                    }
    return closest


def source_positions(text: str) -> list[int]:
    """Map folded character offsets to indices in the unmodified source string.

    This is built only for passages with lexical candidates, not for every row
    in the two-million-record source inventory.
    """
    positions: list[int] = []
    for index, char in enumerate(text):
        positions.extend([index] * len(fold(char)))
    return positions


def raw_context(
    text: str, offset: int, positions: list[int], length: int = 420,
) -> str:
    """Extract original Unicode near an offset in the folded source string."""
    source_offset = positions[offset]
    start = max(0, source_offset - 140)
    return text[start:start + length]


def unmatched_distant(
    normalized: str, close_pairs: list[Pair], window: int = WINDOW,
) -> list[Pair]:
    """Keep a nearest remote fire term for every tongue without a close pair.

    These are recall-oriented leads, not every distant cross-product pair.
    """
    seen = {pair["tongue_offset"] for pair in close_pairs}
    fires = list(FIRE.finditer(normalized))
    if not fires:
        return []
    fire_positions = [fire.start() for fire in fires]
    result: list[Pair] = []
    for tongue in TONGUE.finditer(normalized):
        if tongue.start() in seen:
            continue
        index = bisect.bisect_left(fire_positions, tongue.start())
        neighbors = [fires[i] for i in (index - 1, index) if 0 <= i < len(fires)]
        if not neighbors:
            continue
        fire = min(neighbors, key=lambda item: abs(item.start() - tongue.start()))
        distance = abs(fire.start() - tongue.start())
        if distance <= window:
            raise AssertionError("unmatched tongue has a close fire candidate")
        result.append({
            "tongue_offset": tongue.start(),
            "fire_offset": fire.start(),
            "distance": distance,
            "fire_root": fire.group(),
            "tier": "core" if fire.group().startswith(CORE) else "expanded",
        })
    return result


def scan(root: Path, output: Path, *, expected: bool = True) -> dict[str, Any]:
    # A numeric census cannot authenticate content: verify the exact checkout,
    # remote origin, release manifest, and clean working tree before any output.
    verified_revision = verify_source(root).revision if expected else None
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").unlink(missing_ok=True)
    statistics: dict[str, dict[str, int]] = {}
    tally: Counter[str] = Counter()
    out_path = output / "candidates.jsonl"
    with out_path.open("w", encoding="utf-8") as out:
        for family, (directory, nfiles, nrows) in FAMILIES.items():
            paths = sorted((root / "data" / directory).glob("*.jsonl"))
            if expected and len(paths) != nfiles:
                raise RuntimeError(f"{family}: expected {nfiles} files, got {len(paths)}")
            rows = 0
            close = 0
            boundaries = 0
            for path in paths:
                previous = None
                relative = path.relative_to(root).as_posix()
                with path.open(encoding="utf-8") as stream:
                    for ordinal, line in enumerate(stream, 1):
                        rows += 1
                        source = json.loads(line)
                        original = source["text"]
                        if not isinstance(original, str):
                            raise ValueError(f"{relative}:{ordinal}: non-string text")
                        normalized = fold(original)
                        tally[f"{family}.tongue_occurrences"] += len(TONGUE.findall(normalized))
                        pairs = matches_normalized(normalized)
                        distant_pairs = unmatched_distant(normalized, pairs)
                        positions = source_positions(original) if pairs or distant_pairs else []
                        for pair in pairs:
                            item = {
                                "family": family, "scope": "intra-passage",
                                "path": relative, "ordinal": ordinal,
                                "locus": source.get("locus"), "urn": source.get("urn"),
                                **pair,
                                "context": raw_context(original, min(
                                    pair["tongue_offset"], pair["fire_offset"]
                                ), positions),
                            }
                            out.write(json.dumps(item, ensure_ascii=False) + "\n")
                            close += 1
                            tally[f"{family}.{pair['tier']}.pairs"] += 1
                        for distant in distant_pairs:
                            item = {
                                "family": family, "scope": "intra-passage-distant",
                                "path": relative, "ordinal": ordinal,
                                "locus": source.get("locus"), "urn": source.get("urn"),
                                **distant,
                                "context": raw_context(original, min(
                                    distant["tongue_offset"], distant["fire_offset"]
                                ), positions),
                            }
                            out.write(json.dumps(item, ensure_ascii=False) + "\n")
                        if distant_pairs:
                            tally[f"{family}.distant.passages"] += 1
                            tally[f"{family}.distant.tongues"] += len(distant_pairs)
                        # Include two adjacent records from ONE file: phrase may cross
                        # the upstream locus boundary. Never bridge separate files.
                        if previous is not None:
                            old_ordinal, old_locus, old_text, old_folded = previous
                            # Check cheap normalized windows first. Source character
                            # slices may be much longer due to combining marks.
                            left_folded = old_folded[-(WINDOW + 40):]
                            right_folded = normalized[:WINDOW + 40]
                            cross_possible = (
                                (TONGUE.search(left_folded) and FIRE.search(right_folded))
                                or (FIRE.search(left_folded) and TONGUE.search(right_folded))
                            )
                            if cross_possible:
                                old_positions = source_positions(old_text)
                                new_positions = positions or source_positions(original)
                                left_start = old_positions[
                                    max(0, len(old_positions) - (WINDOW + 40))
                                ]
                                right_end = new_positions[
                                    min(len(new_positions), WINDOW + 40) - 1
                                ] + 1
                                while (right_end < len(original)
                                       and unicodedata.combining(original[right_end])):
                                    right_end += 1
                                left = old_text[left_start:]
                                right = original[:right_end]
                                combined = left + "\n" + right
                                split = len(fold(left + "\n"))
                                for pair in matches(combined):
                                    crosses = (
                                        (pair["tongue_offset"] < split)
                                        != (pair["fire_offset"] < split)
                                    )
                                    if not crosses:
                                        continue
                                    item = {
                                        "family": family, "scope": "adjacent-passages",
                                        "path": relative, "ordinal": ordinal,
                                        "previous_ordinal": old_ordinal,
                                        "previous_locus": old_locus,
                                        "locus": source.get("locus"),
                                        **pair, "context": combined,
                                    }
                                    out.write(json.dumps(item, ensure_ascii=False) + "\n")
                                    boundaries += 1
                                    tally[f"{family}.boundary.pairs"] += 1
                        previous = (ordinal, source.get("locus"), original, normalized)
            if expected and rows != nrows:
                raise RuntimeError(f"{family}: expected {nrows} rows, got {rows}")
            statistics[family] = {
                "files": len(paths), "rows": rows,
                "intra_passage_pairs": close, "adjacent_passage_pairs": boundaries,
                "tongue_occurrences": tally[f"{family}.tongue_occurrences"],
            }
    # Catch source edits made while the potentially long scan was running.
    if expected:
        verify_source(root)
    report = {
        "source": "open-greek/open-greek-corpus",
        "pinned_commit": verified_revision,
        "source_verified": expected,
        "normalization": "Unicode NFD, casefold, strip combining marks",
        "tongue_stems": ["γλωσσ", "γλωττ"],
        "fire_stems": list(FIRE.pattern.split("|")),
        "core_fire_stems": list(CORE),
        "distance_limit_normalized_characters": WINDOW,
        "families": statistics,
        "tally": dict(sorted(tally.items())),
        "result": "lexical candidates only; chronology and semantic identity require review",
    }
    (output / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-expect-counts", action="store_true")
    args = parser.parse_args()
    scan(args.source, args.output, expected=not args.no_expect_counts)


if __name__ == "__main__":
    main()
