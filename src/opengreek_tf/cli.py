"""Command-line entry point for OpenGreek-TF."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .audit import audit_source
from .release import SUPPORTED_RELEASE
from .research_queries import search_native
from .source import fetch_source, verify_source


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
