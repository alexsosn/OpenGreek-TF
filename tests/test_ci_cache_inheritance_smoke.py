"""RED-first cross-PR proof that a protected main Git-object cache is restorable.

This is a narrowly triggered *integration* workflow, not a general fallback job.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / ".github" / "workflows" / "main-cache-inheritance-smoke.yml"


def test_separate_pr_main_cache_smoke_is_explicit_and_narrow() -> None:
    workflow = SMOKE.read_text(encoding="utf-8")
    assert "  workflow_dispatch:" in workflow
    assert "  pull_request:" in workflow
    assert '      - ".github/workflows/main-cache-inheritance-smoke.yml"' in workflow
    assert '      - "tests/test_ci_cache_inheritance_smoke.py"' in workflow
    assert "on:\n  push:" not in workflow
    assert "pull_request_target:" not in workflow


def test_smoke_requires_actual_default_branch_cache_hit_without_writing() -> None:
    workflow = SMOKE.read_text(encoding="utf-8")
    assert "opengreek_tf.ci_source_cache prepare upstream" in workflow
    assert "actions/cache/restore@v4" in workflow
    assert "key: ${{ steps.scope.outputs.key }}" in workflow
    assert "steps.objects.outputs.cache-hit" in workflow
    assert "!= 'true'" in workflow
    assert "actions/cache/save@" not in workflow
    assert "actions/cache@v" not in workflow


def test_smoke_independently_checks_real_source_and_never_disables_verification() -> None:
    workflow = SMOKE.read_text(encoding="utf-8")
    assert "opengreek_tf.ci_source_cache checkout upstream" in workflow
    assert "opengreek_tf.source import verify_source" in workflow
    assert "338aa27310b3cfe2588a993b4d113b503597d70f" in workflow
    assert "heraclides-ponticus.fragmenta.jsonl" in workflow
    assert "source bytes" in workflow
