"""Process-isolated primary Greek native Text-Fabric build and measurements.

Only metrics cross the process boundary. The actual Greek source and native
Text-Fabric output use the already verified shared native composer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .primary_materializer import materialize_primary
from .registry_build_runner import _memory_mib
from .tf_integrity import native_tf_manifest


class PrimaryBuildError(ValueError):
    """Isolated native primary build failed or returned malformed measurements."""


def _child_build(
    root: Path, relative_files: tuple[str, ...], destination: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    phases: list[dict[str, str | float]] = []

    def record_phase(stage: str) -> None:
        current_mib, peak_mib = _memory_mib()
        phases.append({
            "phase": stage,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "live_rss_mib": round(current_mib, 2),
            "high_water_mib": round(peak_mib, 2),
        })

    stats = materialize_primary(
        root, relative_files, destination, on_phase=record_phase,
    )
    manifest = native_tf_manifest(destination)
    current_mib, peak_mib = _memory_mib()
    return {
        "pid": os.getpid(),
        "source_files": list(relative_files),
        "stats": {
            "records": stats.records,
            "metadata_records": stats.metadata_records,
            "text_records": stats.text_records,
            "source_atoms": stats.source_atoms,
            "fact_nodes": stats.fact_nodes,
        },
        "phases": phases,
        "build_seconds": round(time.perf_counter() - started, 3),
        "last_live_rss_mib": round(current_mib, 2),
        "peak_rss_mib": round(peak_mib, 2),
        "native_tf_bytes": manifest.output_bytes,
        "canonical_sha256": manifest.canonical_sha256,
        "raw_sha256": manifest.raw_sha256,
    }


def run_isolated_primary_build(
    root: Path,
    relative_files: tuple[str, ...],
    destination: Path,
) -> dict[str, Any]:
    """Build native primary graph in a child process, failing closed on error.

    Each input path is an argv argument. No shell interpolation, no data
    sidecar, no standalone serializer and no weakening of loaded conservation.
    """
    args = [
        sys.executable, "-m", "opengreek_tf.primary_build_runner",
        "--root", os.path.abspath(root),
        "--destination", os.path.abspath(destination),
    ]
    for relative in relative_files:
        args.extend(("--file", relative))
    result = subprocess.run(
        args, check=False, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        raise PrimaryBuildError(
            f"isolated primary build failed (exit {result.returncode}): "
            f"{result.stderr.strip()[-1500:]}"
        )
    try:
        report: Any = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PrimaryBuildError("isolated primary build returned invalid metrics") from exc
    if (
        type(report) is not dict
        or type(report.get("pid")) is not int
        or report["pid"] == os.getpid()
        or report.get("source_files") != list(relative_files)
        or type(report.get("stats")) is not dict
        or type(report.get("peak_rss_mib")) not in (int, float)
        or report["peak_rss_mib"] <= 0
        or type(report.get("canonical_sha256")) is not str
        or len(report["canonical_sha256"]) != 64
    ):
        raise PrimaryBuildError("isolated primary build returned incomplete metrics")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build selected original primary Greek rows in isolated native TF"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--file", dest="files", action="append", required=True)
    args = parser.parse_args()
    report = _child_build(args.root, tuple(args.files), args.destination)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
