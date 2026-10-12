# Research queries on the currently implemented native Greek F/E graph

This is an **executable pre-release research interface**, not the frozen OpenGreek
ontology or the complete 0.1 corpus browser. It works on native Text-Fabric
output built with `opengreek_tf.native_composer.write_native_records`, including
real pinned original primary Greek JSONL, registry records and **unaligned**
secondary/paratetext samples. It reads native TF **only**; the source checkout,
JSONL files and sidecars are not used when querying.

## Search exact Greek text, work source fields and provenance

Install from the repository with `python -m pip install -e .`. Point the
command at an existing **generated native TF directory**, not the upstream
JSONL checkout. Replace the example value with an actual source `urn` or
edition present in that dataset:

```bash
opengreek-tf search-native ./generated/native \
  --kind primary-passage --contains "λόγος" --max-results 20

opengreek-tf search-native ./generated/native \
  --kind primary-passage --contains "ἀνήρ" --source tei \
  --edition ACTUAL_SOURCE_EDITION --max-results 10

opengreek-tf search-native ./generated/native \
  --kind secondary-witness --contains "λόγος" --max-results 10

opengreek-tf search-native ./generated/native \
  --kind paratext-record --contains "ὑπόμνημα" --max-results 10
```

The original \`python -m opengreek_tf.research_queries\` entrypoint remains available for existing scripts. Both commands delegate to the same native F/E search implementation.\n\nEach JSONL result includes literal reconstructed `text`, record `kind`,
`source_file`, 1-based `source_ordinal`, global `source_seq`,
`source_record_id`, and available *source-authored string fields*: `urn`,
`locus`, `edition`, `source`, `license`, `slug`, and string `page`.
These are names/values from the original **native source-fact graph**; the
command does not infer authority identities from `urn`, decompose page numbers,
or crosswalk author/work/edition identifiers. A passage can have an ordinal
different from its printed locus. `page` can be a source integer on primary
rows; this sample query only returns an original string `page` if present.

In Python:

```python
from pathlib import Path
from opengreek_tf.research_queries import search_native

hits = search_native(
    Path("./generated/native"),
    kind="primary-passage",
    contains="λόγος",
    source="tei",
    max_results=25,
)
for hit in hits:
    print(hit.urn, hit.locus, hit.source_file, hit.source_ordinal, repr(hit.text))
```

The substring search is **literal, case/accent/Unicode-sensitive**, not
tokenized, lemmatized, normalized or indexed. It loads native F/E and scans
matching node owners (potentially expensive for millions of passages).
`max_results` bounds results, **not peak Text-Fabric memory**. Source metadata
and original casing/spacing, tabs and newlines remain intact.

## Direct native Text-Fabric traversal (no semantic sidecar)

```python
from tf.fabric import Fabric

api = Fabric(locations="./generated/native", silent="deep").load(
    "record_kind source_file source_record_id source_seq "
    "fact_key fact_kind fact_text has_fact form", silent="deep",
)
for p in api.F.otype.s("passage"):
    if api.F.record_kind.v(p) != "primary-passage":
        continue
    # Only a genuine 'passage' has original Greek text-layout atom slots.
    greek_text = api.T.text(p, fmt="text-orig-full")
    (object_fact,) = api.E.has_fact.f(p)
    assert api.F.fact_kind.v(object_fact) == "object"
    source_strings = {
        api.F.fact_key.v(f): api.F.fact_text.v(f)
        for f in api.E.has_fact.f(object_fact)
        if api.F.fact_kind.v(f) == "str"
    }
    assert greek_text == source_strings["text"]
    print(api.F.source_record_id.v(p), source_strings.get("edition"), greek_text)
```

This reads an original `edition` string via `E.has_fact` from the owner's
root source object, rather than inventing a direct `F.edition` feature.
Nested structured objects and arrays stay typed `sourceFact` nodes, traversed
recursively using `E.has_fact`; their local order uses `fact_position`.
Repeated corrections/quality flags and explicit nulls are real source
facts, **not** judgments that a passage is linguistically corrected.

## Current public native feature and node contract

| TF name | Meaning and limits |
| --- | --- |
| `atom` (slot type), `atom_kind` | Literal whitespace/non-whitespace text runs, plus one nonlexical authentic source-row anchor per record; **not words** |
| `passage` | Original primary Greek passage owner with text-layout slots |
| `metadataRecord` | Nonlexical author/work registry row, secondary witness, or paratext source occurrence; no primary Greek text slots |
| `sourceFact` | One original JSON object, array, string, integer, boolean or explicit null; every nested container/scalar is represented through native F/E |
| `otype`, `oslots` | Built-in node-type/slot-coverage topology; source facts anchor to their originating source-row atom |
| `form` | Literal Greek Unicode text-layout run on text atoms (empty text may appear on source anchor); no morphological token or lemma |
| `source_file`, `source_ordinal`, `source_record_id` | Physical source provenance on owners/anchors, 1-based source row; IDs are not inferred cross-corpus authority equivalences |
| `source_seq` | Global sequence of source occurrences in the supplied materialization order |
| `record_kind` | `primary-passage`, `secondary-witness`, `paratext-record`, `registry-author`, or `registry-work`; not an alignment |
| `fact_count`, `fact_digest` | Source-local typed graph size and SHA-derived integrity marker on each record owner |
| `fact_kind` | `object`, `array`, `str`, `int`, `bool`, `null` |
| `fact_id`, `fact_position` | Zero-based preorder graph ID and ordered position of a member within its original container |
| `fact_key`, `fact_text`, `fact_int` | Original object key, string scalar, and numeric/boolean scalar (boolean reconstructed from `fact_kind`) |
| `has_fact` | Directed owner→root and sourceFact→child native edges; **not lexical, translation, citation, or witness alignment edges** |
| `otext`, `fmt:text-orig-full` | For a graph containing primary passages, `{form}` renders exact primary Greek. A metadata-only graph uses its original source-record identifier instead |

Source-authored keys such as `urn`, `edition`, `source`, `locus`,
`license`, `corrections`, `dfhg_flag`, `text_lines`, `cts`,
`secondary_reason`, `slug`, `lang`, and `page` are **values in
sourceFact**, not stand-alone TF features. Use typed `fact_kind` and
`has_fact` to inspect them, including nested arrays and repeated entries.

## Witness, apparatus, citation and authority caveats

Secondary witness rows, displaced editions and paratext are currently
nonprimary `metadataRecord` nodes. Their original `text` is a native
`sourceFact` **string**, not a passage's `T.text`. The query CLI only returns
them when their own `--kind` is selected. A matching `urn`, locus, or slug
does **not** prove alignment to any primary passage, nor equivalence across
differing citation conventions. No word, lexeme, author-work, work-edition,
crosswalk or primary-secondary edges are asserted in this generic graph.
Source `cts` and `locus` fields may be incomplete, reused or heterogeneous.

The source-internal `fact_digest` does not authenticate the original upstream
snapshot by itself. Before using native TF as evidence, run the independent
original-source/native graph conservation validator with the pinned original
source selection and verify the build/manifest provenance. Full corpus and
final app/section navigation remain open in issues #3, #6, #9, #10, #11 and
#14.
