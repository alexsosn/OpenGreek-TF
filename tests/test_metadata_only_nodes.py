"""Executable Text-Fabric 13.1.x proof for metadata-only nodes (issue #20).

The low-level native TF writer is deliberately exercised directly: this is a
schema research test, not a corpus converter and not a production writer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]


def test_walker_removes_unlinked_metadata_entities(tmp_path: Path) -> None:
    output = tmp_path / "walker"
    tf = Fabric(locations=str(output), silent="deep")

    def director(cv: CV) -> None:
        orphan = cv.node("author")
        cv.terminate(orphan)

        passage = cv.node("passage")
        slot = cv.slot()
        cv.feature(slot, form="λόγος")
        cv.feature(passage, locus="1")
        cv.terminate(passage)

    cv = CV(tf, silent="deep")
    assert cv.walk(
        director,
        slotType="word",
        generic={"source": "synthetic metadata-only TF regression fixture"},
        otext={
            "sectionTypes": "passage",
            "sectionFeatures": "locus",
            "fmt:text-orig-full": "{form}",
        },
        featureMeta={
            "locus": {"description": "source label"},
            "form": {"description": "literal text form"},
        },
        warn=False,
    )

    loaded = Fabric(locations=str(output), silent="deep").load(
        "locus form", silent="deep"
    )
    assert loaded
    assert loaded.F.otype.s("word") == (1,)
    assert loaded.F.otype.s("author") == ()
    assert loaded.F.otype.s("passage")


def test_native_tf_save_load_rejects_empty_oslots_edges(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The plain-text TF reader rejects empty oslots edges after saving them."""
    output = tmp_path / "native"
    tf = Fabric(locations=str(output), silent="deep")

    # Nodes 1,2 are genuine words; 3,4 are authors with no text extents;
    # 5 is an actual passage containing both words.
    assert tf.save(
        nodeFeatures={
            "otype": {
                1: "word",
                2: "word",
                3: "author",
                4: "author",
                5: "passage",
            },
            "form": {1: "λόγος", 2: " ἄλλος"},
            "entity_id": {3: "oga000001", 4: "oga000002"},
            "entity_status": {3: "served", 4: "retired"},
            "locus": {5: "1"},
        },
        edgeFeatures={
            "oslots": {3: set(), 4: set(), 5: {1, 2}},
            "written_by": {5: {3}},
        },
        metaData={
            "otype": {"valueType": "str"},
            "oslots": {"valueType": "str"},
            "otext": {
                "sectionTypes": "passage",
                "sectionFeatures": "locus",
                "fmt:text-orig-full": "{form}",
            },
            "form": {"valueType": "str", "description": "Exact token content"},
            "entity_id": {"valueType": "str", "description": "Opaque ID"},
            "entity_status": {
                "valueType": "str",
                "description": "Current identity status",
            },
            "locus": {"valueType": "str", "description": "Source locus"},
            "written_by": {"valueType": "int", "description": "Author relationship"},
        },
        silent="deep",
    )

    # Fabric.save accepts the *presence* of an oslots mapping, but writing a
    # genuinely empty edge set has no valid TF edge-target specification. The
    # parser rejects that row, so the metadata identities cannot be queried.
    # This explicitly documents the rejected alternative.
    api = Fabric(locations=str(output), silent="deep").load(
        "form entity_id entity_status locus written_by", silent="deep"
    )
    assert api is False
    assert "oslots: emptyNode2Spec" in capsys.readouterr().err
