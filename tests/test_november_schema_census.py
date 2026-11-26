"""Regression tests for the actual November workflow's source census.

Run the embedded step on tiny local fixtures; only acquisition and the exact
pinned file/row expectations are substituted. The real workflow retains them.
"""

import json
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/november-source-pin.yml"
STEP = "Audit ALL actual November original text-family schemas, nested paths and CR"


def run_census(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    primary: list[dict[str, Any]],
    paratext: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    note_rows = paratext or []
    workflow = WORKFLOW.read_text(encoding="utf-8")
    step = workflow.split(f"      - name: {STEP}\n", 1)[1]
    step = step.split("\n      - ", 1)[0].split("        run: |\n", 1)[1]
    script = textwrap.dedent(step)
    # Test fixtures are deliberately tiny. Only source identity and counts are mocked.
    for family, directory, files, count, rows in (
        ("primary", "corpus", 3939, 1913683, primary),
        ("secondary", "corpus_secondary", 560, 338245, []),
        ("paratext", "paratext", 17, 23969, note_rows),
    ):
        script = script.replace(
            f'("{family}", "{directory}", {files}, {count})',
            f'("{family}", "{directory}", 1, {len(rows)})',
        ).replace(
            f'("{family}", "{directory}", {files})',
            f'("{family}", "{directory}", 1)',
        )
        directory_path = tmp_path / "new-source/data" / directory
        if family == "paratext":
            directory_path /= "gutenberg"
        directory_path.mkdir(parents=True, exist_ok=True)
        (directory_path / "fixture.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
    source_module = ModuleType("opengreek_tf.source")
    source_module.__dict__["verify_source"] = lambda *_a, **_kw: True
    release_module = ModuleType("opengreek_tf.release")
    release_module.__dict__["NOVEMBER_RELEASE"] = object()
    monkeypatch.setitem(sys.modules, "opengreek_tf.source", source_module)
    monkeypatch.setitem(sys.modules, "opengreek_tf.release", release_module)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    scope: dict[str, Any] = {}
    exec(compile(script, str(WORKFLOW), "exec"), scope)
    return cast(dict[str, Any], json.loads(json.dumps(scope["report"])))


def test_all_row_variants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"text": "λόγος", f"rare_{i}": 1} for i in range(70)]
    primary = run_census(tmp_path, monkeypatch, rows)["primary"]
    variants = primary["row_variants"]
    assert len(variants) == 70
    assert sum(row["count"] for row in variants) == 70
    assert {row["example"]["line"] for row in variants} == set(range(1, 71))
    assert {row["example"]["file"] for row in variants} == {"data/corpus/fixture.jsonl"}


def test_mixed_nested_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"text": "α", "tokens": [{"flag": False, "x": 1}, {"x": 1.5, "flag": 0},
                                 None, "a", 1, True], "empty": []},
        {"text": "β", "tokens": [{"x": None, "flag": True}]},
    ]
    nested = run_census(tmp_path, monkeypatch, rows)["primary"]["nested_types"]

    def shapes(kind: str, path: list[str | None]) -> list[Any]:
        return [r["shape"] for r in nested if r["type"] == kind and r["path"] == path]

    assert ["bool", "dict", "int", "null", "str"] in shapes("array", ["tokens"])
    assert shapes("array", ["empty"]) == [[]]
    assert set(shapes("scalar", ["tokens", None, "flag"])) == {"bool", "int"}
    assert set(shapes("scalar", ["tokens", None, "x"])) == {"int", "float", "null"}
    assert shapes("object", ["tokens", None]) == [["flag", "x"]]
    entry = next(r for r in nested if r["type"] == "object" and r["path"] == ["tokens", None])
    assert entry["count"] == 3
    assert entry["example"]["line"] == 1


def test_nested_shapes_and_literal_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        "text": "γ", "meta": {f"rare_{i}": i for i in range(80)},
        "collision": {"a.b": 1, "a": {"b": "not the same path"}, "[]": 2},
        "other": [{"x": 3}],
    }
    primary = run_census(tmp_path, monkeypatch, [row])["primary"]
    nested = primary["nested_types"]
    assert len([r for r in nested if r["type"] == "scalar" and r["path"][0] == "meta"]) == 80
    paths = [r["path"] for r in nested]
    assert ["collision", "a.b"] in paths
    assert ["collision", "a", "b"] in paths
    assert ["collision", "[]"] in paths
    assert ["other", None, "x"] in paths
    assert "not the same path" not in json.dumps(primary)


def test_cr_empty_file_and_determinism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = [{"text": "α", "meta": {"a.b": "x\r\r", "a": {"b": "x\r"}}}]
    paratext = [{"text": "α\r\nβ", "source": "gutenberg"}]
    report = run_census(tmp_path, monkeypatch, primary, paratext)
    assert report == run_census(tmp_path, monkeypatch, primary, paratext)
    assert report["secondary"]["nonempty_files"] == 0
    assert report["secondary"]["rows"] == 0
    assert report["paratext"]["nested_paratext_paths"] == [
        "data/paratext/gutenberg/fixture.jsonl",
    ]
    assert {tuple(r["path"]): r["count"] for r in report["primary"]["cr_paths"]} == {
        ("meta", "a.b"): 2, ("meta", "a", "b"): 1,
    }
    assert report["paratext"]["cr_paths"] == [{"path": ["text"], "count": 1}]
