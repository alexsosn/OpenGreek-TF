"""Bounded, fail-closed native TF passage writer experiment (issue #27).

This prototype deliberately rejects any source field that cannot yet be
represented natively without loss. It is not the whole-corpus converter.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]

from .record_stream import FieldArray, FieldObject, ParsedRecord
from .text_runs import segment_runs

MAX_PROBE_RECORDS = 32
_UNMODELED_STRING_FIELDS = frozenset({"text_orig"})


class UnsupportedSourceStructure(ValueError):
    """Refuse a source record whose semantics the mini-writer cannot conserve."""


def write_primary_probe(
    records: Iterable[ParsedRecord],
    destination: str | Path,
    *,
    max_records: int = MAX_PROBE_RECORDS,
) -> None:
    """Materialize a *small* scalar-only primary source batch as native TF.

    A real source-row atom anchors each passage, including passages with empty
    text. Additional text-bearing atoms preserve each actual Unicode run.
    Native TF features expose all supported scalar source facts. No silent
    dropping of unimplemented scholarly metadata is permitted.
    """
    if max_records < 1:
        raise ValueError("max_records must be positive")
    accepted: list[tuple[ParsedRecord, dict[str, str | int]]] = []
    work_urn: str | None = None
    source_file: str | None = None
    for record in records:
        if len(accepted) >= max_records:
            raise UnsupportedSourceStructure(
                f"maximum {max_records} source rows per TF micro-writer probe exceeded"
            )
        if record.family != "primary":
            raise UnsupportedSourceStructure(
                f"only primary source records are supported: {record.family}"
            )
        if source_file is not None and source_file != record.relative_file:
            raise UnsupportedSourceStructure("mixed source files in one TF work probe")
        source_file = record.relative_file

        values: dict[str, str | int] = {}
        for field_name, value in record.fields.items:
            if field_name == "text":
                continue
            if field_name in _UNMODELED_STRING_FIELDS:
                raise UnsupportedSourceStructure(
                    f"{record.occurrence_key}: {field_name}: diplomatic layer is not modeled"
                )
            if isinstance(value, (FieldArray, FieldObject, bool)):
                raise UnsupportedSourceStructure(
                    f"{record.occurrence_key}: {field_name}: unsupported source semantics"
                )
            if not isinstance(value, (str, int)):
                raise UnsupportedSourceStructure(
                    f"{record.occurrence_key}: {field_name}: invalid scalar"
                )
            values[f"src_{field_name}"] = value

        urn = values.get("src_urn")
        if not isinstance(urn, str) or not urn:
            raise UnsupportedSourceStructure(
                f"{record.occurrence_key}: missing source URN"
            )
        if work_urn is None:
            work_urn = urn
        elif work_urn != urn:
            raise UnsupportedSourceStructure(
                f"{record.occurrence_key}: mixed work URN {urn!r}"
            )
        accepted.append((record, values))

    if not accepted or work_urn is None:
        raise UnsupportedSourceStructure("cannot write empty primary source probe")

    # Validation ends before any output directory or native TF feature is made.
    all_scalar_fields = set().union(*(fields for _, fields in accepted))
    int_feature_names = {"source_ordinal"} | {
        key
        for _, fields in accepted
        for key, value in fields.items()
        if type(value) is int
    }
    for key in all_scalar_fields:
        kinds = {type(fields[key]) for _, fields in accepted if key in fields}
        if len(kinds) != 1:
            raise UnsupportedSourceStructure(
                f"conflicting source types for {key} within this probe"
            )

    feature_names = all_scalar_fields | {
        "form",
        "atom_kind",
        "work_slug",
        "source_file",
        "source_ordinal",
        "passage_key",
    }

    def director(cv: CV) -> None:
        work = cv.node("work")
        cv.feature(work, work_slug=work_urn)
        for record, scalar_fields in accepted:
            passage = cv.node("passage")
            cv.feature(
                passage,
                source_file=record.relative_file,
                source_ordinal=record.ordinal,
                passage_key=f"{record.relative_file}:{record.ordinal}",
                **scalar_fields,
            )
            for run in segment_runs(record.text):
                atom = cv.slot()
                cv.feature(atom, atom_kind="text", form=run.value)

            # A real row from an existing JSONL source is a valid source atom.
            # This retains empty-text passages without inventing visible text.
            row_atom = cv.slot()
            cv.feature(row_atom, atom_kind="source-row")
            cv.terminate(passage)
        cv.terminate(work)

    output = Path(destination)
    if output.exists():
        raise UnsupportedSourceStructure(f"refusing pre-existing TF output: {output}")

    cv = CV(Fabric(locations=str(output), silent="deep"), silent="deep")
    success = cv.walk(
        director,
        slotType="atom",
        generic={"source": "Open Greek experimental primary passage graph"},
        otext={
            "sectionTypes": "work,passage",
            "sectionFeatures": "work_slug,passage_key",
            "fmt:text-orig-full": "{form}",
        },
        featureMeta={
            name: {"description": f"Source or provenance field {name}"}
            for name in feature_names
        },
        intFeatures=int_feature_names,
        warn=False,
    )
    if not success:
        raise RuntimeError("Text-Fabric rejected the primary passage probe")
