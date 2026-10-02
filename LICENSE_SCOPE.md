# Licence scope

## OpenGreek-TF software

Repository-authored converter code, tests, CI/configuration, acquisition helpers, app configuration, and software documentation are MIT-licensed under `LICENSE`.

## Upstream Open Greek data and generated TF

The MIT software licence does **not** relicense Open Greek data or TF data generated from it.

At supported upstream release `corpus-2026-09-15.2`, Open Greek declares the aggregate corpus CC BY-SA 4.0. Its `LICENSE` and `CITATION.cff` further distinguish component terms, including:

- First1KGreek / Perseus canonical-greekLit / Galenus Verbatim: CC BY-SA 4.0;
- Patrologia Graeca OCR contributed by Calfa: CC BY 4.0;
- PTA: per-file CC BY-SA / CC BY, with the upstream non-commercial file excluded;
- DFHG: CC BY-SA 4.0;
- SAWS deposit: CC BY 4.0;
- Greek Wikisource contributor transcription layer: CC BY-SA 4.0 over public-domain source texts;
- Open Greek's own OCR of public-domain editions: additionally CC BY 4.0;
- derived statistical counts are described upstream as facts rather than corpus text licensing.

The generated complete TF adaptation must preserve the aggregate ShareAlike and attribution obligations applicable to the source release and expose per-work/source licence information where the frozen ontology requires it.

Do not infer a uniform per-work licence from the aggregate licence when upstream records a more specific component licence.

Issue #2 must audit licensing of every additional in-scope semantic layer (including secondary witnesses and paratext) before release.
