"""Command-line entry point for OpenGreek-TF."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .audit import audit_source
from .jsonl_conservation import validate_native_jsonl_sources
from .primary_materializer import materialize_primary
from .release import SUPPORTED_RELEASE
from .research_queries import search_native
from .source import fetch_source, verify_source
from .text_materializer import materialize_texts, select_all_text_files
from .tf_integrity import native_tf_manifest

# Complete pinned release census, independently established from all 4,447 files.
_PINNED_ALL_TEXT_ROWS = (SUPPORTED_RELEASE.passages, 307_085, 15_958)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opengreek-tf",
        description="Materialize the Open Greek Corpus as native Text-Fabric.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "source-info",
        help="Print the immutable default Open Greek release identity",
    )

    fetch = subparsers.add_parser("fetch", help="Fetch the supported Open Greek release")
    fetch.add_argument("destination", help="Empty/nonexistent destination directory")

    verify = subparsers.add_parser(
        "verify-source",
        help="Verify a clean local checkout of the supported Open Greek release",
    )
    verify.add_argument("source", help="Local Open Greek Git checkout")

    audit = subparsers.add_parser(
        "audit-source",
        help="Audit the semantic surface of the verified supported release",
    )
    audit.add_argument("source", help="Local Open Greek Git checkout")
    audit.add_argument("--output", required=True, help="Write deterministic audit JSON here")

    convert = subparsers.add_parser(
        "convert-primary",
        help="Convert explicitly selected pinned primary JSONL files to validated native TF",
    )
    convert.add_argument("source", help="Clean local checkout of the supported upstream release")
    convert.add_argument(
        "--file", action="append", required=True, dest="files",
        metavar="data/corpus/WORK.jsonl",
        help="Canonical primary source file; repeat to specify deterministic order",
    )
    convert.add_argument(
        "--output", type=Path, required=True,
        help="New native TF output directory outside the source checkout",
    )

    convert_texts = subparsers.add_parser(
        "convert-texts",
        help="Convert selected or all pinned primary, secondary and paratext originals",
    )
    convert_texts.add_argument(
        "source", help="Clean Git checkout of exact supported Open Greek release",
    )
    text_selection = convert_texts.add_mutually_exclusive_group(required=True)
    text_selection.add_argument(
        "--file", action="append", dest="files",
        metavar="data/{corpus,corpus_secondary,paratext}/SOURCE.jsonl",
        help="Original JSONL file; repeat to determine source order",
    )
    text_selection.add_argument(
        "--all", action="store_true",
        help="All 4,447 original textual files (memory-intensive, unreleased scale)",
    )
    convert_texts.add_argument(
        "--output", type=Path, required=True,
        help="New single native TF graph directory outside the source checkout",
    )

    search = subparsers.add_parser(
        "search-native",
        help="Search literal Greek/source facts in an existing generated native TF graph",
    )
    search.add_argument("tf_directory", type=Path, help="Generated native TF directory")
    search.add_argument(
        "--kind", required=True,
        choices=("primary-passage", "secondary-witness", "paratext-record"),
    )
    search.add_argument("--contains", default="", help="Exact Unicode substring")
    search.add_argument("--urn", help="Original source row urn field (not inferred CTS)")
    search.add_argument("--edition", help="Original source row edition field")
    search.add_argument("--source", help="Original source row source field")
    search.add_argument("--max-results", type=int, default=20)
    return parser


def _source_info() -> dict[str, object]:
    identity = SUPPORTED_RELEASE
    return {
        "repository": identity.repository,
        "tag": identity.tag,
        "revision": identity.commit,
        "release_id": identity.release_id,
        "corpus_sha256": identity.corpus_sha256,
        "catalog_sha256": identity.catalog_sha256,
        "works": identity.works,
        "passages": identity.passages,
        "greek_tokens": identity.greek_tokens,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "source-info":
        print(json.dumps(_source_info(), sort_keys=True))
        return 0

    if args.command == "fetch":
        snapshot = fetch_source(args.destination, identity=SUPPORTED_RELEASE)
        print(
            json.dumps(
                {"path": str(snapshot.path), "revision": snapshot.revision},
                sort_keys=True,
            )
        )
        return 0

    if args.command == "verify-source":
        snapshot = verify_source(args.source, identity=SUPPORTED_RELEASE)
        print(
            json.dumps(
                {"path": str(snapshot.path), "revision": snapshot.revision},
                sort_keys=True,
            )
        )
        return 0

    if args.command == "audit-source":
        snapshot = verify_source(args.source, identity=SUPPORTED_RELEASE)
        report = audit_source(snapshot.path)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0

    if args.command == "convert-primary":
        snapshot = verify_source(args.source, identity=SUPPORTED_RELEASE)
        destination = args.output.resolve()
        if destination.is_relative_to(snapshot.path.resolve()):
            raise ValueError("native TF output must be outside the source checkout")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("native TF output already exists")
        selected = tuple(args.files)
        stats = materialize_primary(snapshot.path, selected, destination)
        # Independent stock-JSON source/loaded-Fabric F/E conservation, not the
        # writer's parser or graph equality. Emit success only after this gate.
        validation = validate_native_jsonl_sources(snapshot.path, selected, destination)
        if (
            validation.records != stats.records
            or validation.primary_passages != stats.text_records
            or validation.source_fact_nodes != stats.fact_nodes
        ):
            raise ValueError("independent primary source/TF census mismatch")
        # Confirm the original checkout stayed pinned and clean throughout the
        # conversion and independently loaded source conservation.
        final_snapshot = verify_source(snapshot.path, identity=SUPPORTED_RELEASE)
        if (
            final_snapshot.revision != snapshot.revision
            or final_snapshot.path.resolve() != snapshot.path.resolve()
        ):
            raise ValueError("upstream source checkout identity changed during conversion")
        manifest = native_tf_manifest(destination)
        print(json.dumps({
            "status": "validated-selected-primary",
            "revision": snapshot.revision,
            "destination": str(destination),
            "source_files": selected,
            "records": validation.records,
            "primary_passages": validation.primary_passages,
            "source_fact_nodes": validation.source_fact_nodes,
            "source_unicode_codepoints": validation.source_unicode_codepoints,
            "original_source_sha256": validation.original_source_sha256,
            "tf_file_count": manifest.tf_file_count,
            "tf_bytes": manifest.output_bytes,
            "canonical_sha256": manifest.canonical_sha256,
        }, sort_keys=True))
        return 0

    if args.command == "convert-texts":
        snapshot = verify_source(args.source, identity=SUPPORTED_RELEASE)
        destination = args.output.resolve()
        if destination.is_relative_to(snapshot.path.resolve()):
            raise ValueError("native TF output must be outside the source checkout")
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("native TF output already exists")

        if args.all:
            inventory = select_all_text_files(snapshot.path)
            selected = inventory.files
            empty_files = inventory.empty_files
        else:
            selected = tuple(args.files)
            empty_files = frozenset()

        stats = materialize_texts(
            snapshot.path, selected, destination, allow_empty_files=empty_files,
        )
        validation = validate_native_jsonl_sources(
            snapshot.path, selected, destination, allow_empty_files=empty_files,
        )
        if (
            validation.records != stats.records
            or validation.primary_passages != stats.text_records
            or validation.secondary_witnesses + validation.paratext_records
            != stats.metadata_records
            or validation.source_fact_nodes != stats.fact_nodes
            or validation.source_files != len(selected)
        ):
            raise ValueError("independent original-text/native-TF conservation mismatch")
        if args.all and (
            (
                validation.primary_passages,
                validation.secondary_witnesses,
                validation.paratext_records,
            ) != _PINNED_ALL_TEXT_ROWS
            or stats.records != sum(_PINNED_ALL_TEXT_ROWS)
        ):
            raise ValueError("complete pinned original-text row census mismatch")

        # Do not publish success if the source checkout changed during the
        # conversion or the independently decoded original JSONL verification.
        final = verify_source(snapshot.path, identity=SUPPORTED_RELEASE)
        if final.revision != snapshot.revision or final.path.resolve() != snapshot.path.resolve():
            raise ValueError("original source changed during full-text conversion")
        manifest = native_tf_manifest(destination)
        summary: dict[str, object] = {
            "status": "validated-all-texts" if args.all else "validated-selected-texts",
            "revision": snapshot.revision,
            "destination": str(destination),
            "source_file_count": len(selected),
            "empty_source_files": len(empty_files),
            "records": validation.records,
            "primary_passages": validation.primary_passages,
            "secondary_witnesses": validation.secondary_witnesses,
            "paratext_records": validation.paratext_records,
            "source_fact_nodes": validation.source_fact_nodes,
            "source_unicode_codepoints": validation.source_unicode_codepoints,
            "original_source_sha256": validation.original_source_sha256,
            "tf_file_count": manifest.tf_file_count,
            "tf_bytes": manifest.output_bytes,
            "canonical_sha256": manifest.canonical_sha256,
        }
        if not args.all:
            summary["source_files"] = list(selected)
        print(json.dumps(summary, sort_keys=True))
        return 0

    if args.command == "search-native":
        for hit in search_native(
            args.tf_directory, kind=args.kind, contains=args.contains,
            urn=args.urn, edition=args.edition, source=args.source,
            max_results=args.max_results,
        ):
            print(json.dumps(asdict(hit), ensure_ascii=False, sort_keys=True))
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
