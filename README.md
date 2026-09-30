![STOPSTORM VOI Mapper](docs/banner.png)

# STOPSTORM VOI Mapper

Local name-matching assistance for radiotherapy research. The tool proposes mappings to a 40-VOI vocabulary, checks laterality and duplicate assignments, and leaves uncertain or conflicting structures open for review. It never modifies DICOM objects or approves a clinical plan.

## Quick start

Python 3.10 or later is sufficient for the CSV workflow. Clone this repository and run from its root:

```bash
python -m unittest discover -s tests -v
python -m voi_mapper --input examples/synthetic_structures.csv --output results/exact_demo
```

The default is an exact-name baseline with no model calls. The synthetic example deliberately includes names that require a language model or manual review.

For local LLM proposals, start Ollama and select a model you have already installed:

```bash
python -m voi_mapper --input structures.csv --output results/local_review --mode llm --model YOUR_LOCAL_MODEL_TAG
```

No model is downloaded automatically. Only loopback HTTP endpoints are accepted. The tested study configuration uses a locally registered `qwen3.8-ridge-benchmark:3.7bpw` tag. This is a local alias, not a promise that an identically named model is available in the Ollama registry. Model metadata and its digest are recorded with each run. Model weights and their separate licences are not part of this repository. Other Ollama models need their own schema/quality check; quality is not transferable from a model name alone.

## Input and review

CSV headers:

```csv
Case,ROI_ID,StructureName,Volume_cc,SourceGroup
DEMO_A,1,Heart,500,Synthetic
DEMO_A,2,Lung Left,1600,Synthetic
```

`Case`, `ROI_ID` and `StructureName` are required. Case/ROI pairs must be unique. Volume is optional and displayed for review, not used as proof of anatomy. `SourceGroup` is optional provenance, for example a submission round. Only unique structure names enter the local model prompt; case IDs, volumes, source groups and reference assignments do not.

For a case folder containing exactly one RTSTRUCT:

```bash
pip install pydicom
python -m voi_mapper.extract path/to/case structures.csv --case DEMO_A
```

The extractor handles extensionless DICOM files. Multiple RTSTRUCTs require explicit selection by preparing a folder with the intended structure set. It does not export PatientName or PatientID and does not calculate volumes. ROI names can still contain identifying text, so inspect input before any sharing.

Outputs:

| File | Purpose |
|---|---|
| `mappings.csv` | Original name, volume, source group, model proposal, automatic assignment and editable review/comment columns |
| `missing_masters.csv` | Every master without an automatic assignment, per case |
| `review.html` | Local searchable review table, with unresolved mappings highlighted |
| `run.json` | Input/prompt hashes, model metadata, parameters and counts |
| `cache/` | Local model responses for traceability; potentially sensitive, never commit |

A populated output directory is never overwritten. CSV files can be opened in Excel. The study's separate Excel preparation adds case-sheet ordering, master-name grouping and a missing-master view; this repository keeps its dependency-free export simple and does not claim to implement the complete historical workbook formatter.

## Workflow

![Name mapping workflow](docs/workflow.png)

[Download the interactive workflow](docs/workflow.html). The diagram is generated from [workflow.json](docs/workflow.json) with Archify. The banner is an AI-generated conceptual illustration, not patient anatomy or a result figure.

1. Read source names and deduplicate identical strings.
2. Ask the local model for one vocabulary proposal and an ordinal certainty judgment per name.
3. Accept only high-certainty candidates that pass explicit laterality checks.
4. Enforce one structure per master per case. A sole exact-name candidate wins a conflict; otherwise conflicting candidates remain unassigned.
5. Review all proposals and open items. Numbered targets, contour subsets and boolean unions require anatomical review or a separate geometrical workflow.

The certainty categories are not calibrated probabilities. No duplicate automatic masters is a software invariant, not evidence that the retained mapping is correct. An incorrect unique mapping remains possible.

## Evaluation and manuscript

The current study evaluation is a **retrospective reference-withheld replay**, not a prospective or externally validated clinical system. A frozen prompt, model digest, vocabulary, parameters, input list and reference hash are recorded before inference. Prior aliases and finalized mappings are not supplied to the model. Predictions are frozen before scoring against the final curation.

Report these separately:

- **Coverage:** correct automatic assignments divided by positive reference assignments.
- **Precision:** correct automatic assignments divided by all automatic assignments.
- Exact-name baseline, raw model proposals and postprocessed proposals.
- Conflicts, abstentions, per-master results and provenance of unresolved cases.

Do not report total-row accuracy dominated by unassigned structures as the principal result. Do not interpret a replay as historical time saved or the number of edits actually made during original curation. Final source names may already incorporate earlier repairs, and the curated reference can itself need review. The study-specific data and case-level results are deliberately not distributed here.

## Limits

This is name matching, not segmentation, dose calculation, DICOM repair or anatomical validation. It cannot establish contour completeness from a name. It does not infer target intent from dose. A shared name is cached across cases and therefore cannot resolve case-specific anatomy. The vocabulary groups historical GTV/CTV/TV labels under CardTV for this cardiac research use case, while ITV and PTV remain separate; do not reuse that target convention for tumour studies without changing the vocabulary and prompt.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests cover duplicate prevention, independent cases, laterality, abstention, malformed input and loopback-only requests. Contributions should include synthetic examples and tests. Do not submit clinical DICOM files, patient-identifying labels, internal case lists or model-response caches in issues or pull requests.

Code: MIT licence. Third-party diagram runtime notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
