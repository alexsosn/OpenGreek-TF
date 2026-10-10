"""Independent, bounded raw-JSONL -> loaded Text-Fabric conservation probe.

Do not import the converter's source parser, text-run segmentation or writer:
the purpose is to detect their shared assumptions against original JSON bytes.
This module does NOT validate the complete corpus or the final ontology.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tf.fabric import Fabric  # type: ignore[import-untyped]


class ProbeValidationError(ValueError):
    """Raw source and loaded native TF disagree, or source is unsupported."""


@dataclass(frozen=True, slots=True)
class ProbeValidationReport:
    """Validated source prefix size and exact text-codepoint count."""

    passage_count: int
    text_codepoints: int


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"unsupported non-JSON constant {value}")


def _source_prefix(
    source_path: Path, record_count: int
) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    try:
        with source_path.open("rb") as fh:
            for ordinal in range(1, record_count + 1):
                raw = fh.readline()
                if not raw:
                    raise ProbeValidationError(
                        f"{source_path}:{ordinal}: source prefix is shorter than "
                        f"requested {record_count} records"
                    )
                try:
                    decoded: Any = json.loads(
                        raw.decode("utf-8", errors="strict"),
                        object_pairs_hook=_unique_object,
                        parse_constant=_reject_constant,
                    )
                except (UnicodeError, ValueError, TypeError) as exc:
                    raise ProbeValidationError(
                        f"{source_path}:{ordinal}: invalid JSON: {exc}"
                    ) from exc
                if not isinstance(decoded, dict):
                    raise ProbeValidationError(
                        f"{source_path}:{ordinal}: source row must be an object"
                    )
                row: dict[str, str | int] = {}
                for key, value in decoded.items():
                    if not isinstance(key, str) or type(value) not in (str, int):
                        raise ProbeValidationError(
                            f"{source_path}:{ordinal}: {key}: unsupported source fact"
                        )
                    row[key] = value
                if not isinstance(row.get("text"), str):
                    raise ProbeValidationError(
                        f"{source_path}:{ordinal}: missing text string"
                    )
                if not isinstance(row.get("urn"), str) or not row["urn"]:
                    raise ProbeValidationError(
                        f"{source_path}:{ordinal}: missing work URN"
                    )
                rows.append(row)
    except OSError as exc:
        raise ProbeValidationError(f"cannot read original source: {exc}") from exc
    return rows


def _check(condition: bool, explanation: str) -> None:
    if not condition:
        raise ProbeValidationError(explanation)


def validate_primary_probe(
    source_root: str | Path,
    relative_file: str,
    destination: str | Path,
    *,
    record_count: int,
) -> ProbeValidationReport:
    """Verify a bounded primary source prefix against *loaded* native TF.

    Source is decoded independently from raw bytes. No source parser, writer
    primitive, or converter expected-value helper is called by this validator.
    """
    if record_count < 1 or record_count > 32:
        raise ProbeValidationError("record_count must be in [1, 32] for this probe")

    root = Path(source_root)
    output = Path(destination)
    raw_rows = _source_prefix(root / relative_file, record_count)
    source_fields = {
        f"src_{key}" for row in raw_rows for key in row if key != "text"
    }
    # The bounded direct writer stores every supported scalar in its own
    # native feature; reject fabricated/extra source features too.
    observed_features = {file.stem for file in output.glob("src_*.tf")}
    _check(
        observed_features == source_fields,
        f"source feature inventory differs: expected {sorted(source_fields)}, "
        f"found {sorted(observed_features)}",
    )

    requested = source_fields | {
        "atom_kind",
        "form",
        "passage_key",
        "source_file",
        "source_ordinal",
        "work_slug",
    }
    try:
        api = Fabric(locations=str(output), silent="deep").load(
            " ".join(sorted(requested)), silent="deep"
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise ProbeValidationError(f"cannot load native TF: {exc}") from exc
    _check(bool(api), "cannot load native TF feature inventory")

    try:
        features = {name: getattr(api.F, name) for name in requested}
    except AttributeError as exc:
        raise ProbeValidationError(f"missing expected native TF feature: {exc}") from exc

    works = tuple(api.F.otype.s("work"))
    passages = tuple(api.F.otype.s("passage"))
    all_atoms = tuple(api.F.otype.s("atom"))
    _check(len(works) == 1, f"work count differs: {len(works)} != 1")
    _check(
        len(passages) == record_count,
        f"passage count differs: {len(passages)} != {record_count}",
    )
    _check(
        features["work_slug"].v(works[0]) == raw_rows[0]["urn"],
        "work slug differs from source URN",
    )

    claimed_slots: list[int] = []
    total_codepoints = 0
    for ordinal, (node, row) in enumerate(zip(passages, raw_rows, strict=True), 1):
        ctx = f"{relative_file}:{ordinal}"
        slots = tuple(api.E.oslots.s(node))
        _check(bool(slots), f"{ctx}: passage has no slots")
        _check(
            features["source_file"].v(node) == relative_file,
            f"{ctx}: source_file differs",
        )
        _check(
            features["source_ordinal"].v(node) == ordinal,
            f"{ctx}: physical source_ordinal differs",
        )
        _check(
            features["passage_key"].v(node) == f"{relative_file}:{ordinal}",
            f"{ctx}: passage_key differs",
        )
        for src_feature in sorted(source_fields):
            original = row.get(src_feature[4:])
            actual = features[src_feature].v(node)
            _check(
                actual == original and (
                    (src_feature[4:] in row) == (actual is not None)
                ),
                f"{ctx}: {src_feature} differs: {actual!r} vs {original!r}",
            )

        kinds = [features["atom_kind"].v(slot) for slot in slots]
        _check(
            kinds.count("source-row") == 1 and kinds[-1] == "source-row",
            f"{ctx}: missing, duplicated or misplaced source-row atom",
        )
        _check(
            all(kind in {"source-row", "text"} for kind in kinds),
            f"{ctx}: unrecognized native atom kind",
        )
        text_parts = [features["form"].v(slot) for slot, kind in zip(slots, kinds, strict=True)
                      if kind == "text"]
        _check(
            all(isinstance(part, str) and bool(part) for part in text_parts),
            f"{ctx}: missing native text atom form",
        )
        _check(
            features["form"].v(slots[-1]) is None,
            f"{ctx}: source-row atom invents displayed text",
        )
        original_text = row["text"]
        assert isinstance(original_text, str)  # validated independently during JSONL read
        _check(
            "".join(text_parts) == original_text,
            f"{ctx}: exact source text differs from loaded TF form slots",
        )
        _check(
            api.T.text(node, fmt="text-orig-full") == original_text,
            f"{ctx}: T.text output differs from source text",
        )
        total_codepoints += len(original_text)
        claimed_slots.extend(slots)

    _check(
        tuple(claimed_slots) == all_atoms,
        "global text/metadata atom order or multiplicity differs",
    )
    _check(
        tuple(api.E.oslots.s(works[0])) == all_atoms,
        "work slot span differs from source passages",
    )
    return ProbeValidationReport(
        passage_count=record_count,
        text_codepoints=total_codepoints,
    )
