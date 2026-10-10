"""Research probe: model true metadata records as slots, without phantom text."""

from __future__ import annotations

from pathlib import Path

from tf.convert.walker import CV  # type: ignore[import-untyped]
from tf.fabric import Fabric  # type: ignore[import-untyped]


def test_source_atom_slots_preserve_unserved_entities_without_fake_words(
    tmp_path: Path,
) -> None:
    """All slots correspond to a real source atom, either text or a registry record."""
    output = tmp_path / "mixed"
    tf = Fabric(locations=str(output), silent="deep")

    def director(cv: CV) -> None:
        passage = cv.node("passage")
        word = cv.node("word")
        token = cv.slot()
        cv.feature(token, atom_kind="text", form="λόγος")
        cv.feature(word, source_record_id="primary:work:1")
        cv.terminate(word)
        cv.feature(passage, locus="1")
        cv.terminate(passage)

        # These two slots represent actual opaque source-record identities;
        # they are NOT inserted into the Greek text and have no form feature.
        for identity, status in (
            ("oga000001", "served"),
            ("oga000002", "retired"),
        ):
            author = cv.node("author")
            atom = cv.slot()
            cv.feature(atom, atom_kind="registry-record")
            cv.feature(author, entity_id=identity, entity_status=status)
            cv.terminate(author)

    cv = CV(tf, silent="deep")
    assert cv.walk(
        director,
        slotType="atom",
        otext={"fmt:text-orig-full": "{form}"},
        featureMeta={
            "atom_kind": {"description": "Source atom kind"},
            "form": {"description": "Exact text atom"},
            "source_record_id": {"description": "Source occurrence identifier"},
            "locus": {"description": "Unmodified source citation label"},
            "entity_id": {"description": "Opaque source entity identifier"},
            "entity_status": {"description": "Source entity status"},
        },
        warn=False,
    )

    api = Fabric(locations=str(output), silent="deep").load(
        "atom_kind form source_record_id locus entity_id entity_status",
        silent="deep",
    )
    assert api

    author_nodes = api.F.otype.s("author")
    assert len(author_nodes) == 2
    assert len(api.F.otype.s("word")) == 1
    assert len(api.F.otype.s("atom")) == 3

    ids = {api.F.entity_id.v(n): n for n in author_nodes}
    assert set(ids) == {"oga000001", "oga000002"}
    assert api.F.entity_status.v(ids["oga000002"]) == "retired"

    atom_sets = [set(api.E.oslots.s(n)) for n in author_nodes]
    assert len(atom_sets[0]) == len(atom_sets[1]) == 1
    for slots in atom_sets:
        atom = next(iter(slots))
        assert api.F.atom_kind.v(atom) == "registry-record"
        assert api.F.form.v(atom) is None

    text_slots = tuple(
        s for s in api.F.otype.s("atom") if api.F.atom_kind.v(s) == "text"
    )
    assert len(text_slots) == 1
    assert api.F.form.v(text_slots[0]) == "λόγος"
    passage = api.F.otype.s("passage")[0]
    assert set(api.E.oslots.s(passage)) == set(text_slots)

    for author in author_nodes:
        assert set(api.E.oslots.s(author)).isdisjoint(text_slots)
