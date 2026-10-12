# Alternative models and task-specific prompting

The mapping task benefits from a fixed vocabulary, terminology definitions and
explicit rules for ambiguous names. Alternative models, reasoning effort and
additional task context can improve proposals, with a possible cost in latency
and memory. Evaluate these choices on the assignments reviewers actually need.

## Swift development pilot, 12 October 2026

We tested [Swift-Qwen3.8-27B](https://huggingface.co/ukisai/Swift-Qwen3.8-27b)
against the [documented Qwen configuration](evaluation.md#documented-local-configuration).
This was a separate retrospective development pilot, not the manuscript's
full-cohort evaluation or an independent external validation.

The pilot contained 361 unique native structure names from 12 cases and 11
centres, with 306 reviewed case/master reference assignments. Case selection
had been fixed by hashes before the Swift outputs were available. Only names
and the standard vocabulary entered the model requests: no case identifiers,
volumes, geometry or reference labels.

All arms used the same task prompt, 40-name vocabulary, batches of 32 names,
temperature 0, seed 20260930, 8192-token context and frozen postprocessing.
The prompt defined target families, laterality, whole structures versus subsets,
and when to abstain. Postprocessing required high ordinal certainty, checked
laterality and restricted contour types, and enforced one ROI per master per case.

| Measure | Documented Qwen, thinking off | Swift, thinking off | Swift, thinking low |
|---|---:|---:|---:|
| Correctly prepared reference assignments | 220/306 (71.9%) | 210/306 (68.6%) | 245/306 (80.1%) |
| Required assignments needing a switch | 7 | 11 | 8 |
| Required assignments remaining manual | 79 | 85 | 53 |
| Extra automatic proposals without a reference slot | 6 | 6 | 7 |
| Precision among automatic proposals | 94.4% | 93.3% | 94.6% |
| Failed batches after retries | 0 | 1 | 0 |
| Duplicate automatic masters after checks | 0 | 0 | 0 |
| Model processing, including loading and retries | 265.5 s | 275.5 s | 733.4 s |
| Generation throughput | 56.9 tokens/s | 53.8 tokens/s | 54.8 tokens/s |
| Observed text-model GPU allocation | 11.2 GiB | 12.0 GiB | 12.0 GiB |

A correctly prepared assignment selected the same native ROI as the reviewed
reference. Each required case/master slot counted once. Extra proposals were
reported separately and did not count as successful assignments. Failed batches
remained in the denominator. Ordinal certainty is not a calibrated probability.
Zero duplicate final masters reflects the shared Python checks; it does not
mean the model never proposed competing candidates.

Compared with Qwen in the same-day pilot, Swift low added 28 correctly prepared
assignments and lost three, for a net gain of 25. Precision remained similar.
The trade-off was **2.76 times the model processing time**. Queue waiting was
excluded from these times. The local coordinator unloaded the model after each
batch, so the totals include repeated loading and should not be extrapolated
directly to a continuously loaded server. Human editing time was not measured.

The extra low-thinking arm was added after the initial non-thinking comparison.
It used 4096 output tokens rather than 1800 to accommodate reasoning and the
JSON answer. Swift used the publisher's IQ3_XS quantisation, whereas the existing
Qwen configuration used mixed IQ2_M weights. This compares practical local
deployments; it does not isolate the Swift adapter or verify the publisher's
reasoning-token savings against its own Qwen3.8 base model.

## Prompt variation and reproducibility

This pilot kept prompt content constant. It demonstrates a benefit from the
tested model/reasoning configuration, not a measured improvement from adding
another prompt. To assess additional context, make a separate comparison:

1. Freeze a reference set and retain a held-out set for the final check.
2. Compare the base prompt with a version adding relevant terminology, aliases,
   target definitions or explicit abstention rules.
3. Keep model, batches, decoding settings and assignment checks fixed.
4. Report correctly prepared assignments, incorrect/extra proposals, unresolved
   items, failed responses and processing time together.

Do not supply case-specific reference answers in the prompt or silently score
a tuned prompt on the same examples used to develop it. Preserve the raw response
and record the actual model digest, prompt hash and settings. See
[evaluation and reproducibility](evaluation.md) for the shared scoring framework.

## Using Swift locally

The [publisher's GGUF repository](https://huggingface.co/ukisai/Swift-Qwen3.8-27B-GGUF)
provides Ollama instructions. The tested IQ3_XS text weights fitted our 16 GB
RTX 5080. Different quantisations, context lengths or vision requests may need
different resources. The model weights have their own
[Swift licence](https://huggingface.co/ukisai/Swift-Qwen3.8-27b/blob/main/LICENSE),
including conditions on commercial use; the Mapper's MIT licence does not
relicense those weights.

For a separately configured Ollama client, the tested low mode uses
`think: "low"`, `num_ctx: 8192`, `num_predict: 4096` and `temperature: 0`.
Check the installed model's `/api/show` metadata for supported thinking levels.

**Current integration boundary:** the repository's original CLI and GUI mapping
requests set `think: false`. Selecting the Swift model alone therefore does not
reproduce the low-thinking pilot. The pilot used an isolated test client with
the explicit low setting; this documentation update does not change the
evaluated mapping core or add a reasoning selector.

Only this aggregate development summary is public. Case lists, native name sets,
reference annotations and response caches remain in the controlled workspace.
