"""Read-only independent TF / Rust Context-Fabric equivalence and load probe.

This module does not enter OpenGreek-TF's writing or authoritative validation
path. It runs each engine in a separate process to measure the same native F/E
and literal Greek text surface without inventing an intermediate corpus model.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class EngineProbe:
    engine: str
    version: str
    nodes: int
    passages: int
    metadata_records: int
    atoms: int
    fact_nodes: int
    source_text_codepoints: int
    node_features: tuple[str, ...]
    edge_features: tuple[str, ...]
    canonical_sha256: str
    load_seconds: float
    peak_rss_mib: float
    cache_bytes: int


def _cache_bytes(corpus: Path, engine: str) -> int:
    """Count on-corpus engine compiled-cache files; not source TF files."""
    directory = corpus / (".cfr" if engine == "cf" else ".tf")
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def _peak_rss_mib() -> float:
    # This benchmark runs on Linux CI. macOS also reports ru_maxrss in bytes,
    # but avoid pretending its numeric units match Linux.
    if sys.platform != "linux":
        return 0.0
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _emit(digest: Any, value: object) -> None:
    digest.update(
        (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) +
         "\n").encode("utf-8"),
    )


def probe_native(corpus: Path, *, engine: str) -> EngineProbe:
    """Hash every native node feature, native edge and original passage text.

    No corpus-mutating operations are performed. Both engines must report the
    same canonical F/E/T digest before a performance comparison is meaningful.
    """
    if engine not in ("tf", "cf"):
        raise ValueError(f"unsupported probe engine: {engine}")
    if not corpus.is_dir() or not any(corpus.glob("*.tf")):
        raise ValueError("probe requires an existing native TF feature directory")
    module_name = "tf.fabric" if engine == "tf" else "cfabric"
    dist_name = "text-fabric" if engine == "tf" else "context-fabric"
    fabric: Any = importlib.import_module(module_name).__dict__["Fabric"]
    start = time.perf_counter()
    loader = fabric(locations=str(corpus), silent="deep")
    discovered: dict[str, list[str]] | None = loader.explore(silent="deep")
    if not discovered:
        raise ValueError(f"{engine}: native F/E feature discovery failed")
    node_features = tuple(sorted(set(discovered["nodes"]) - {"otype"}))
    edge_features = tuple(sorted(set(discovered["edges"]) - {"oslots"}))
    if "has_fact" not in edge_features:
        raise ValueError(f"{engine}: missing native has_fact source relations")
    api: Any = loader.load(" ".join((*node_features, *edge_features)), silent="deep")
    if not api:
        raise ValueError(f"{engine}: could not load native graph")
    load_seconds = time.perf_counter() - start

    digest = hashlib.sha256()
    _emit(digest, {"node_features": node_features, "edge_features": edge_features})
    otype: Any = api.F.otype
    counts: dict[str, int] = {"passage": 0, "metadataRecord": 0, "atom": 0, "sourceFact": 0}
    codepoints = 0
    total = otype.maxNode
    for n in range(1, total + 1):
        kind: str = otype.v(n)
        if kind not in counts:
            raise ValueError(f"{engine}: unexpected native node type: {kind}")
        counts[kind] += 1
        node_values = {
            feature: getattr(api.F, feature).v(n) for feature in node_features
        }
        edges = {
            feature: list(getattr(api.E, feature).f(n))
            for feature in edge_features
        }
        if kind != "atom":
            edges["oslots"] = list(api.E.oslots.s(n))
        _emit(digest, [n, kind, node_values, edges])
        if kind == "passage":
            greek = api.T.text(n, fmt="text-orig-full")
            if not isinstance(greek, str):
                raise ValueError(f"{engine}: non-string original Greek text")
            codepoints += len(greek)
            _emit(digest, ["text-orig-full", n, greek, api.T.sectionFromNode(n)])
    if not counts["passage"] or not counts["sourceFact"]:
        raise ValueError(f"{engine}: missing source Greek passages or typed facts")
    return EngineProbe(
        engine=engine, version=importlib.metadata.version(dist_name), nodes=total,
        passages=counts["passage"], metadata_records=counts["metadataRecord"],
        atoms=counts["atom"], fact_nodes=counts["sourceFact"],
        source_text_codepoints=codepoints,
        node_features=node_features, edge_features=edge_features,
        canonical_sha256=digest.hexdigest(),
        load_seconds=round(load_seconds, 6), peak_rss_mib=round(_peak_rss_mib(), 3),
        cache_bytes=_cache_bytes(corpus, engine),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=("tf", "cf"))
    parser.add_argument("--corpus", required=True, type=Path)
    args = parser.parse_args(argv)
    report = probe_native(args.corpus, engine=args.engine)
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
