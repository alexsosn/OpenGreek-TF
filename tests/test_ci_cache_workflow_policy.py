"""RED-first policy gates for reusing the same verified source across CI."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_trusted_main_push_seeds_cache_for_other_pull_requests() -> None:
    workflow = (WORKFLOWS / "control-census-pinned.yml").read_text(encoding="utf-8")
    # A PR cache belongs to refs/pull/N/merge, not to the default branch.
    # Therefore a main push must populate the protected cache after merge.
    assert "  push:\n    branches: [main]" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "actions/cache/save@v4" in workflow


def test_shared_text_family_consumers_use_exact_same_object_cache_key() -> None:
    for name in ("record-census.yml", "source-cr-census.yml"):
        workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "opengreek_tf.ci_source_cache prepare upstream" in workflow, name
        assert "actions/cache/restore@v4" in workflow, name
        assert "key: ${{ steps.scope.outputs.key }}" in workflow, name
        assert "opengreek_tf.ci_source_cache checkout upstream" in workflow, name
        assert "actions/cache/save@v4" not in workflow, (
            name, "consumer must not race the single verified cache seeder"
        )
        assert "verify_source" in workflow, name
