"""Isolated full-registry native TF build and peak-memory measurements.

The child uses *only* the shared generic native composer and its own loaded
Fabric conservation. The parent independently validates F/E against raw JSON.
Metrics travel over stdout, never source content or a semantic sidecar.
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

from .registry_materializer import materialize_registry
from .tf_integrity import native_tf_manifest


class RegistryBuildError(ValueError):
    """A source registry child process could not build valid native TF."""


def _memory_mib() -> tuple[float, float]:
    """Return current/peak resident process memory, in MiB."""
    if sys.platform.startswith("linux"):
        status = Path("/proc/self/status").read_text(encoding="utf-8")
        values: dict[str, float] = {}
        for line in status.splitlines():
            if line.startswith(("VmRSS:", "VmHWM:")):
                key, count, unit = line.split()
                if unit != "kB":
                    raise RegistryBuildError("unexpected /proc memory unit")
                values[key.rstrip(":")] = int(count) / 1024
        if "VmRSS" not in values or "VmHWM" not in values:
            raise RegistryBuildError("missing Linux resident memory metrics")
        return values["VmRSS"], values["VmHWM"]
    # Text-Fabric already depends on psutil. Use native process RSS on Windows.
    import psutil  # type: ignore[import-untyped]

    memory = psutil.Process(os.getpid()).memory_info()
    peak = getattr(memory, "peak_wset", memory.rss)
    return (memory.rss / (1024 * 1024), peak / (1024 * 1024))


def _child_build(root: Path, destination: Path) -> dict[str, Any]:
    started = time.perf_counter()
    phases: list[dict[str, float | str]] = []

    def phase(name: str) -> None:
        live, peak = _memory_mib()
        phases.append({
            "phase": name,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "live_rss_mib": round(live, 2),
            "high_water_mib": round(peak, 2),
        })

    stats = materialize_registry(root, destination, on_phase=phase)
    manifest = native_tf_manifest(destination)
    live, peak = _memory_mib()
    return {
        "pid": os.getpid(),
        "stats": {
            "records": stats.records,
            "metadata_records": stats.metadata_records,
            "text_records": stats.text_records,
            "source_atoms": stats.source_atoms,
            "fact_nodes": stats.fact_nodes,
        },
        "phases": phases,
        "build_seconds": round(time.perf_counter() - started, 3),
        "last_live_rss_mib": round(live, 2),
        "peak_rss_mib": round(peak, 2),
        "native_tf_bytes": manifest.output_bytes,
        "canonical_sha256": manifest.canonical_sha256,
        "raw_sha256": manifest.raw_sha256,
    }


def run_isolated_registry_build(root: Path, destination: Path) -> dict[str, Any]:
    """Build via an independent Python interpreter, then return measurements.

    A child failure cannot masquerade as success; paths are argv elements, not
    shell commands. The returned metrics are not part of the corpus encoding.
    """
    command = [
        sys.executable, "-m", "opengreek_tf.registry_build_runner",
        "--root", os.path.abspath(root),
        "--destination", os.path.abspath(destination),
    ]
    result = subprocess.run(
        command, check=False, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RegistryBuildError(
            f"isolated native registry build failed (exit {result.returncode}): "
            f"{result.stderr.strip()[-1500:]}"
        )
    try:
        report: Any = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RegistryBuildError("isolated native registry build returned invalid metrics") from exc
    if (
        not isinstance(report, dict)
        or type(report.get("pid")) is not int
        or report["pid"] == os.getpid()
        or type(report.get("stats")) is not dict
        or type(report.get("canonical_sha256")) is not str
        or len(report["canonical_sha256"]) != 64
        or type(report.get("peak_rss_mib")) not in (float, int)
        or report["peak_rss_mib"] <= 0
    ):
        raise RegistryBuildError("isolated native registry build returned incomplete metrics")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact source registry in isolated native TF")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    report = _child_build(args.root, args.destination)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
