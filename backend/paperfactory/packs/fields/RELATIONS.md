# Relations per field (D5)

Made with `uv run paperfactory relation-table --field law --field medicine --field materials --field llm`; edit the packs, not this file.

### law (tested in the law pilot (21 Nov 2026, 3 papers))

| Relation | Words | Definition | Subject kinds | Object kinds | Easily confused with |
|---|---|---|---|---|---|
| relies_on | relied on | the decision uses the source as a basis for its ruling | decision | provision, decision | rejects |
| distinguishes | distinguished | the decision says an earlier decision does not apply because the facts differ | decision | decision | rejects |
| rejects | rejected | the decision refuses to accept the source as a basis for its ruling | decision | provision, decision | relies_on, distinguishes |

DRAFT for review: distinguishing an earlier decision is easily written as rejecting it; a decision that relied on a source only to reject an argument reads as both.

### medicine (DRAFT, not yet run: Aditya reviews before use)

| Relation | Words | Definition | Subject kinds | Object kinds | Easily confused with |
|---|---|---|---|---|---|
| finds_benefit | found a benefit of | the trial reports that the treatment improved the main outcome | trial | treatment | finds_no_effect, finds_harm |
| finds_no_effect | found no effect of | the trial reports no clear difference on the main outcome for the treatment | trial | treatment | finds_benefit, finds_harm |
| finds_harm | found harm from | the trial reports that the treatment made the main outcome or safety worse | trial | treatment | finds_benefit, finds_no_effect |
| contradicts | contradicted | the trial reports a result that disagrees with an earlier trial | trial | trial | - |

DRAFT for review: a trend that is not significant is often written as a benefit; a safety signal with no difference on the main outcome reads as harm or as no effect.

### materials (DRAFT, not yet run: Aditya reviews before use)

| Relation | Words | Definition | Subject kinds | Object kinds | Easily confused with |
|---|---|---|---|---|---|
| reports_improvement | reported an improvement with | the study reports that the material improved the property it tested | study | material | reports_no_change, reports_degradation |
| reports_no_change | reported no change with | the study reports no clear change in the tested property for the material | study | material | reports_improvement, reports_degradation |
| reports_degradation | reported degradation with | the study reports that the material worsened the tested property | study | material | reports_improvement, reports_no_change |
| fails_to_replicate | failed to replicate | the study repeated an earlier study and did not get its result | study | study | - |

DRAFT for review: for a property where lower is better (wear, creep) a fall is an improvement; small changes are written as improvement or as no change.

### llm (DRAFT, not yet run: Aditya reviews before use)

| Relation | Words | Definition | Subject kinds | Object kinds | Easily confused with |
|---|---|---|---|---|---|
| reports_gain | reported a gain from | the study reports that the method raised the model's score on the benchmark over the baseline | study | method | reports_no_gain, reports_drop |
| reports_no_gain | reported no gain from | the study reports no clear difference from the baseline score on the benchmark for the method | study | method | reports_gain, reports_drop |
| reports_drop | reported a drop with | the study reports that the method lowered the model's score on the benchmark below the baseline | study | method | reports_gain, reports_no_gain |
| fails_to_replicate | failed to replicate | the study re-ran an earlier study's setup and did not get its reported result | study | study | - |

DRAFT for review: a gain within run-to-run noise (one seed, no error bars) is often written as a gain; for a metric where lower is better (error rate, perplexity) a fall is a gain; a gain on one benchmark split with a drop on another reads as gain, drop or no gain.

