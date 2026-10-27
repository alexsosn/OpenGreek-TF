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


def fold(text: str) -> str:
    """Case- and accent-insensitive Greek, preserving original source text elsewhere."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text).casefold()
        if not unicodedata.combining(ch)
    )


def matches(text: str, window: int = WINDOW) -> list[dict]:
    """Every tongue/fire pair within the given normalized-character distance."""
    normalized = fold(text)
    tongues = list(TONGUE.finditer(normalized))
    fires = list(FIRE.finditer(normalized))
    fire_positions = [f.start() for f in fires]
    found = []
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


def raw_context(text: str, offset: int, length: int = 420) -> str:
    """Extract exact original source characters; offset is approximate for decomposed text."""
    start = max(0, offset - 140)
    return text[start:start + length]


def scan(root: Path, output: Path, *, expected: bool = True) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    statistics: dict[str, dict] = {}
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
                        pairs = matches(original)
                        for pair in pairs:
                            item = {
                                "family": family, "scope": "intra-passage",
                                "path": relative, "ordinal": ordinal,
                                "locus": source.get("locus"), "urn": source.get("urn"),
                                **pair,
                                "context": raw_context(original, min(
                                    pair["tongue_offset"], pair["fire_offset"]
                                )),
                            }
                            out.write(json.dumps(item, ensure_ascii=False) + "\n")
                            close += 1
                            tally[f"{family}.{pair['tier']}.pairs"] += 1
                        # Include two adjacent records from ONE file: phrase may cross
                        # the upstream locus boundary. Never bridge separate files.
                        if previous is not None:
                            old_ordinal, old_locus, old_text = previous
                            left = old_text[-(WINDOW + 40):]
                            right = original[:WINDOW + 40]
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
                        previous = (ordinal, source.get("locus"), original)
            if expected and rows != nrows:
                raise RuntimeError(f"{family}: expected {nrows} rows, got {rows}")
            statistics[family] = {
                "files": len(paths), "rows": rows,
                "intra_passage_pairs": close, "adjacent_passage_pairs": boundaries,
                "tongue_occurrences": tally[f"{family}.tongue_occurrences"],
            }
    report = {
        "source": "open-greek/open-greek-corpus",
        "pinned_commit": "338aa27310b3cfe2588a993b4d113b503597d70f",
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
