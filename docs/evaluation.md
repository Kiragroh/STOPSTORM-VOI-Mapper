# Evaluation and reproducibility

This page describes a reusable assessment method and the documented local configuration. It deliberately contains no unpublished STOPSTORM cohort results.

## Documented local configuration

| Setting | Value |
|---|---|
| Model family | Qwen3.5 |
| Parameter count | 27.3B |
| Quantisation | IQ2_M, GGUF |
| Local alias | `qwen3.8-ridge-benchmark:3.7bpw` |
| Model digest | `aa22fd8808d14819093a35553b110793f3b25f1b41dc5aa2993300a4d544d2f0` |
| Temperature | 0 |
| Seed | 20260930 |
| Context | 8192 tokens |
| Batch | 32 unique source names |
| Maximum generated tokens | 1800 |
| Thinking | Disabled |
| Assignment checks | Package version 0.2.1 |

The local alias is not a downloadable model identifier. Check metadata and digest when reproducing the configuration; substituting another checkpoint is a new configuration. Exact outputs may depend on the inference backend and batch composition. `run.json` records the local run, prompt and model metadata. The public code does not distribute model weights, clinical inputs, curated reference mappings or response caches.

## Assess the task the reviewer actually has

Freeze inputs, prompt, vocabulary, model settings and assignment rules before a reference comparison. Withhold reference assignments from inference. Store unchanged model responses before scoring. Keep later rule development separate from an initial assessment.

Count each required case/master slot once:

- **Ready:** the selected source structure agrees with the manually reviewed reference.
- **Switch:** a conflicting source occupies the required master, or the reference structure has received another master.
- **Manual:** the required master and its reference structure remain unassigned.
- **Extra proposal:** a proposed master is not required by the reference; report these separately, not as additional successful matches.

Specify exclusions for derived structures, components and unusable inputs before scoring. Report both assignment-level agreement and complete-case review needs. A case can have all required mappings and still contain extra proposals that must be rejected. Total-row accuracy dominated by unassigned structures is not an adequate headline measure.

Name agreement is not anatomical validation. A retrospective replay does not measure historical editing time. Any claim of time savings needs a separate measured workflow study. Reference annotations may themselves require adjudication, which should be documented separately.

## Adaptation

The study workflow was a data-curation aid, not a model-optimisation study. Alternative local or cloud models and task-specific tuning are possible research directions. Assess them on held-out data, preserve case-level grouping, document privacy controls, and test laterality, partial contours and duplicate prevention before use. The current CLI remains local-only; no cloud adapter is bundled.
