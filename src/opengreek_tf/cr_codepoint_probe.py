"""Lossless native integer CR-codepoint atoms, bounded Text-Fabric probe (#29).

TF 13.1's default T.text still cannot render CR; the *loaded graph*
holds every literal codepoint without storing raw CR in a string feature.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]


class CRCodepointError(ValueError):
    """The source text or reconstructed native TF graph is not lossless."""


@dataclass(frozen=True, slots=True)
class CRProbeResult:
    source_file: str
    source_ordinal: int
    text: str
    cr_count: int
    text_slot_count: int


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_cr_codepoint_probe(
    text: str,
    destination: Path,
    *,
    source_file: str,
    source_ordinal: int,
) -> None:
    """Store genuine string runs and U+000D as typed, ordered native TF slots.

    A final source-row slot is authentic source provenance, not a lexical word.
    No source string feature contains CR and no Text-Fabric internals are patched.
    """
    if (
        not isinstance(text, str)
        or not isinstance(source_file, str)
        or not source_file
        or any(ord(c) < 32 for c in source_file)
        or type(source_ordinal) is not int
        or source_ordinal < 1
    ):
        raise CRCodepointError("invalid source text or physical source provenance")
    output = Path(destination)
    if output.exists() or output.is_symlink():
        raise CRCodepointError("refusing pre-existing native TF destination")
    parts = text.split("\r")
    run_exists = any(parts)
    cr_exists = len(parts) > 1
    names = {
        "atom_kind", "source_file", "source_ordinal", "text_digest",
        "text_length", "cr_count", "locus",
    }
    if run_exists:
        names.add("form")
    if cr_exists:
        names.add("codepoint")

    def director(cv: CV) -> None:
        passage = cv.node("passage")
        cv.feature(
            passage,
            source_file=source_file,
            source_ordinal=source_ordinal,
            text_digest=_digest(text),
            text_length=len(text),
            cr_count=len(parts) - 1,
            locus=f"{source_file}:{source_ordinal}",
        )
        for idx, part in enumerate(parts):
            if part:
                run = cv.slot()
                cv.feature(run, atom_kind="text-run", form=part)
            if idx < len(parts) - 1:
                cr = cv.slot()
                cv.feature(cr, atom_kind="cr-codepoint", codepoint=13)
        anchor = cv.slot()
        cv.feature(anchor, atom_kind="source-row", source_file=source_file)
        cv.terminate(passage)

    int_features = {"source_ordinal", "text_length", "cr_count"}
    if cr_exists:
        int_features.add("codepoint")
    fmt_field = "form" if run_exists else "source_file"
    converter = CV(Fabric(locations=str(output), silent="deep"), silent="auto")
    ok = converter.walk(
        director,
        slotType="atom",
        generic={"source": "Bounded real-codepoint native TF research probe (#29)"},
        otext={
            "sectionTypes": "passage",
            "sectionFeatures": "locus",
            "fmt:text-orig-full": "{" + fmt_field + "}",
        },
        featureMeta={
            name: {"description": f"Native CR atom or source provenance: {name}"}
            for name in names
        },
        intFeatures=int_features,
        warn=False,
    )
    if not ok:
        raise CRCodepointError("native TF conversion rejected the CR codepoint graph")


def read_cr_codepoint_probe(destination: Path) -> CRProbeResult:
    """Independently reconstruct Unicode from *loaded* TF, not writer objects."""
    output = Path(destination)
    # Check the *whole native TF surface* before selecting features for the
    # loader. Otherwise a graph can carry fabricated F/E annotations not
    # accounted for by source text, slots, digest or provenance checks.
    fabric = Fabric(locations=str(output), silent="deep")
    declared = fabric.explore(silent="deep")
    if not declared:
        raise CRCodepointError("cannot discover native CR source features")
    required_nodes = {
        "otype", "atom_kind", "source_file", "source_ordinal",
        "text_digest", "text_length", "cr_count", "locus",
    }
    optional_nodes = {"form", "codepoint"}
    discovered_nodes = set(declared["nodes"])
    discovered_edges = set(declared["edges"])
    discovered_configs = set(declared["configs"])
    if (
        not required_nodes.issubset(discovered_nodes)
        or discovered_nodes - required_nodes - optional_nodes
        or discovered_edges != {"oslots"}
        or discovered_configs != {"otext"}
    ):
        raise CRCodepointError(
            "unexpected or missing native TF node/edge/config feature"
        )
    features = (
        "atom_kind source_file source_ordinal text_digest "
        "text_length cr_count locus"
    )
    with_form = "form" in discovered_nodes
    with_cr = "codepoint" in discovered_nodes
    if with_form:
        features += " form"
    if with_cr:
        features += " codepoint"
    try:
        api = fabric.load(features, silent="deep")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise CRCodepointError("corrupt native TF feature graph") from exc
    if not api:
        raise CRCodepointError("could not load native TF features")
    # The probe's ontology has only authentic slots and one parent passage.
    # Any unaccounted native node type is not an original codepoint or row.
    if (
        set(api.F.otype.all) != {"atom", "passage"}
        or len(api.F.otype.s("passage")) != 1
    ):
        raise CRCodepointError("unexpected native node type or missing passage")
    passage = api.F.otype.s("passage")[0]
    file_name = api.F.source_file.v(passage)
    ordinal = api.F.source_ordinal.v(passage)
    expected_length = api.F.text_length.v(passage)
    expected_cr = api.F.cr_count.v(passage)
    digest = api.F.text_digest.v(passage)
    if (
        not isinstance(file_name, str)
        or not file_name
        or type(ordinal) is not int
        or ordinal < 1
        or type(expected_length) is not int
        or expected_length < 0
        or type(expected_cr) is not int
        or expected_cr < 0
        or not isinstance(digest, str)
        or re.fullmatch("[0-9a-f]{64}", digest) is None
        or api.F.locus.v(passage) != f"{file_name}:{ordinal}"
    ):
        raise CRCodepointError("missing or malformed physical source provenance")
    slots = tuple(api.E.oslots.s(passage))
    all_slots = set(api.F.otype.s("atom"))
    if not slots or set(slots) != all_slots:
        raise CRCodepointError("orphan or duplicated source text atom")
    # Full feature-name validation is insufficient: an attacker may add a
    # forged value to a *known* feature on an unrelated native slot. Preserve
    # provenance only on the passage and final authentic source-row anchor.
    if (
        api.F.atom_kind.v(passage) is not None
        or (with_form and api.F.form.v(passage) is not None)
        or (with_cr and api.F.codepoint.v(passage) is not None)
    ):
        raise CRCodepointError("unexpected passage text-slot annotation")
    for slot in slots:
        if (
            api.F.source_ordinal.v(slot) is not None
            or api.F.locus.v(slot) is not None
            or api.F.text_digest.v(slot) is not None
            or api.F.text_length.v(slot) is not None
            or api.F.cr_count.v(slot) is not None
        ):
            raise CRCodepointError("unexpected provenance feature on text slot")
        source_name = api.F.source_file.v(slot)
        if slot == slots[-1]:
            if source_name != file_name:
                raise CRCodepointError("invalid final source-row provenance")
        elif source_name is not None:
            raise CRCodepointError("unexpected provenance on non-source slot")
    kinds = [api.F.atom_kind.v(slot) for slot in slots]
    if kinds.count("source-row") != 1 or kinds[-1] != "source-row":
        raise CRCodepointError("source-row anchor must occur exactly once at end")
    reconstructed: list[str] = []
    run_count = 0
    cr_count = 0
    for slot, kind in zip(slots, kinds, strict=True):
        form = api.F.form.v(slot) if with_form else None
        codepoint = api.F.codepoint.v(slot) if with_cr else None
        if kind == "text-run":
            if (
                not isinstance(form, str)
                or not form
                or "\r" in form
                or codepoint is not None
            ):
                raise CRCodepointError("invalid actual source text-run slot")
            run_count += 1
            reconstructed.append(form)
        elif kind == "cr-codepoint":
            if type(codepoint) is not int or codepoint != 13 or form is not None:
                raise CRCodepointError("invalid or lost native CR codepoint")
            cr_count += 1
            reconstructed.append(chr(codepoint))
        elif kind == "source-row":
            if (
                slot != slots[-1]
                or codepoint is not None
                or form is not None
                or api.F.source_file.v(slot) != file_name
            ):
                raise CRCodepointError("source-row anchor polluted text semantics")
        else:
            raise CRCodepointError("unrecognized source atom kind")
    text = "".join(reconstructed)
    if (
        cr_count != expected_cr
        or len(text) != expected_length
        or _digest(text) != digest
    ):
        raise CRCodepointError("source text count/length/digest mismatch")
    return CRProbeResult(file_name, ordinal, text, cr_count, run_count)
