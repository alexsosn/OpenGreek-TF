# Fire tongues before Acts: chronological and semantic audit

**Date:** 2026-10-27. **Source:** pinned Open Greek Corpus release `corpus-2026-09-15.2`, publishing commit `338aa27310b3cfe2588a993b4d113b503597d70f`.

## Question

Does surviving Greek attest **a projection of flame itself being called a tongue** before Acts 2:3, and can the 1 Enoch 14:9–15 expression be established as the first appearance of this Greek metaphor? Distinguish flame projections (γλῶσσαι πυρός) from tongues *burned in fire*, fiery or malicious *human speech*, the tongue as body part, and “tongues” meaning languages.

## Corpus-wide evidence

The validated scan covers **4,447 source files and 2,293,990 records**: primary 3,909/1,970,947; secondary 533/307,085; paratext 5/15,958. Reproducible scanner: `python -m opengreek_tf.fire_tongues_scan upstream --output results`. The pinned full-corpus CI in this PR passed on head `b43a9ac`.

The broad accent/case-insensitive stem search for γλωσσ-/γλωττ- near πῦρ / φλόγα and related heating vocabulary (including across passage boundaries and distant same-passage occurrences) retrieved **4,865 candidate pair records from 904 source files**. These are pair counts, not independently dated works or true metaphors.

A provisional 904-file / 319-author-or-collection chronological triage yielded:

| Group | Candidate-bearing files |
| --- | ---: |
| Likely pre-Acts attributed texts | 128 |
| First-century or uncertain | 56 |
| Post-Acts authors/works | 611 |
| Mixed anthologies, catenae, pseudepigrapha, later-tradition fragments | 109 |

Every file received a chronological triage and first-pass semantic screening; author labels **are not proof** of the date of each excerpt. A higher-priority shortlist of **142 core tongue/fire pairs separated by ≤35 normalized characters in 74 not-clearly-post-Acts source files** was examined for semantic direction. The remaining **57 mixed-transmission files** were also categorized by source carrier and nearest context; internal attribution and fragment boundaries remain to verify. The short-range threshold does not cap semantic recall.

## Relevant cases and exclusions

- **1 Enoch 14:9, 14:10, 14:15:** `γλῶσσαι πυρὸς`, `τὰς γλώσσας τοῦ πυρὸς`, `ἐν γλώσσαις πυρός`; visibly tongues of flame in the heavenly building. Secure lexical-semantic positives, **but Greek translation date is not securely established**.
- **Acts 2:3:** `γλῶσσαι ὡσεὶ πυρός`; index passage, not an independent earlier comparator.
- **Homer, Odyssey 3.341:** `γλώσσας δʼ ἐν πυρὶ βάλλον`; sacrificial **animal tongues put into fire**, confirmed in Homeric scholia.
- **Apollonius Rhodius, Argonautica 1.516–18:** `ἐπὶ γλώσσῃσι χέοντο αἰθομέναις`; libations poured on **burning sacrificial animal tongues**; ancient scholia explicitly interpret it as that ritual.
- **Sappho fr. 31:** `γλῶσσα ἔαγε` and `χρῷ πῦρ`; speech and heat under skin as *different* sensations; later reused by Longinus and Plutarch.
- **Hesiod, Theogony / Typhon:** tongues belong to the creature, fire flashes from its eyes.
- **Hippocratic Epidemics, Aretaeus, Dioscorides, Nicander and related pseudo-medical writings:** clinical bodily tongue, inflammation, fever, burns; some `πυρ-` forms describe fever, reddening or `πυροί` grains.
- **Philo, De confusione linguarum:** `κατὰ γλῶτταν` means “in the (Greek) language,” beside an etymology of fiery aether.
- **Dio Chrysostom, Or. 8.19:** `τῇ γλώττῃ τὸ πῦρ σβεννύουσι`; children extinguish fire **with their tongue**.
- **Psalms of Solomon 12:5:** whisperer's **human** tongue associated with burning; not a flame named “tongue”.
- **Proverbs 10:20 LXX:** tongue of the righteous compared with refined silver.
- **Aristophanes, Wasps 1405 and Suda quotations:** `πυρούς` means wheat, not flame.
- **Later biblical revisions (Theodotion/Symmachus Isaiah):** the Lord's tongue likened to consuming fire reverses the referent; beware chronology of the Greek translation.
- **Christian catenae on Acts / James, patristic OCR:** numerous *actual* γλῶσσαι πυρός strings are quotations or interpretations **later than Acts**. Attribution to the earlier scriptural episode is not independent pre-Lucan evidence.
- **Thomas Patricius epigram in Cougny/Anthologia:** `γλώττης ἀστραπαὶ τῆς πυρπνοῦ`, a fire-breathing tongue's “lightning”; independently later than Acts (its precise Byzantine date disputed).
- **Evagrius Scholasticus, Ecclesiastical History 4.27:** `αἱ γλωσσίδες τοῦ πυρός` emerging from the earth; independent literal flame-tongue imagery, **sixth century CE**, not a pre-Lucan comparator.

## Boundaries of the claim

This is **a systematic lexical retrieval plus structured first-pass chronological screening and targeted contextual adjudication**, not a proof that **all 904 files have been individually dated and all 4,865 raw hits separately read**. In particular, 57 mixed-carrier works need embedded quote dates verified; post-Acts carriers may quote older material; the stem set can omit paraphrases or variant lexemes; and texts outside Open Greek are excluded.

**Most important chronological caveat:** the *Book of Watchers* itself predates Acts and survives in Aramaic fragments, but its **Greek** translation/recension cannot be automatically assigned the date of the underlying Semitic composition. The extant Greek Codex Panopolitanus is much later. A claim that Enoch *introduced this precise word usage into Greek before Acts* requires a separate argument about the Greek textual history.

The defensible current conclusion is:

> The pinned full-corpus search has not identified an independently established pre-Acts Greek use describing **flame projections as tongues** outside 1 Enoch 14. The closest identifiable non-Christian comparanda have distinct physical, linguistic or physiological meanings. A stronger assertion of first-ever Greek usage remains conditional on Greek Enoch translation dating, quotation-provenance review, corpus coverage and editorial accuracy.

## Key independent checks

- [Open Greek pinned Enoch JSONL](https://github.com/open-greek/open-greek-corpus/blob/338aa27310b3cfe2588a993b4d113b503597d70f/data/corpus/liber-enoch.apocalypsis-enochi.jsonl)
- [Perseus Apollonius and ancient scholia](https://beta.perseus.tufts.edu/urn%3Acts%3AgreekLit%3Atlg0001.tlg001.seatonrevised2026-eng2/card%3A2.1/)
- [Online Critical Pseudepigrapha, Enoch witnesses](https://pseudepigrapha.org/reader.html?doc=1En.xml)
- [*Dead Sea Discoveries* 31 (2024), Greek Enoch witness date](https://brill.com/view/journals/dsd/31/2/article-p143_2.xml)
- G. Menzies, “[Pre-Lucan Occurrences of the Phrase ‘Tongue(s) of Fire’](https://doi.org/10.1163/157007400X00051),” *Pneuma* 22 (2000): 27–60.

For the candidate-level audit, use the report and TSVs generated with this research episode alongside the CI artifact; the 904-file chronology screen contains provisional author-group classifications, not source-certified dating for each physical occurrence.
