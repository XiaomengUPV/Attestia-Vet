# Attestia Vet (VetGuard)

AI-powered veterinary insurance fraud detection using a multi-agent pipeline.

This repo combines deterministic billing rules, LLM-assisted clinical reasoning,
and an evidence-based adversarial review step to analyze veterinary claims and
produce structured, auditable fraud decisions.

Note on naming:
- The draft README uses the product name `Attestia Vet`.
- Much of the current code, UI, and API still use the internal name `VetGuard`.

## What the Project Does

Given a single veterinary claim, the pipeline attempts to determine:
- whether the claim is fraudulent
- the most likely fraud type
- a plain-English explanation of the decision

The primary runtime claim object is a single JSON-like record containing fields
such as species, breed, diagnosis, procedures, billed amount, market rate, and
modifier.

If a PDF is attached, the repo also includes an optional document-integrity
pre-check for forensic PDF analysis.

## Fraud Types Covered

The generated synthetic dataset covers 8 fraud categories:

| Fraud Type | Primary Handling Path |
| --- | --- |
| Duplicate billing | Rule Checker |
| Unbundling | Rule Checker |
| Species mismatch | Rule Checker |
| Modifier abuse | Rule Checker |
| Phantom billing | Clinical Reasoner |
| Diagnosis mismatch | Clinical Reasoner |
| Upcoding | Clinical Reasoner |
| Vaccine padding | Clinical Reasoner |

Important nuance:
- Some Clinical Reasoner categories also have deterministic helper logic for
  obvious patterns.
- Some rule-detectable traces can still be intentionally routed onward when the
  code wants Agent 2 to assign a more specific label.

## How the Pipeline Actually Works

The current pipeline is conditional, not strictly linear.

```text
Claim JSON
  |
  +--> Agent 0: Document Integrity Checker (optional, only if pdf_path is present)
  |
  +--> Agent 1: Rule Checker
         |
         +--> if rule-based fraud is finalized here: stop
         |
         +--> otherwise -> Agent 2: Clinical Reasoner
                           |
                           +--> if clean: stop
                           +--> if indeterminate/error: stop
                           +--> if fraud with enough confidence:
                                   -> Agent 3: Adversarial Validator
                                      -> final verdict
```

This routing behavior comes from:
- [src/fraud_engine.py](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/src/fraud_engine.py)
- [src/fraud_engine_langgraph.py](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/src/fraud_engine_langgraph.py)

## Agent Overview

| Agent | Purpose | Implementation |
| --- | --- | --- |
| Agent 0: Document Integrity Checker | Optional PDF forensics before claim reasoning | Python |
| Agent 1: Rule Checker | Deterministic checks for billing and species-rule violations | Python |
| Agent 2: Clinical Reasoner | Tool-using claim reasoning for clinically ambiguous fraud types | Anthropic Claude API + Python tools |
| Agent 3: Adversarial Validator | Conservative override step that can only rescue fraud findings by citing knowledge-base evidence | Anthropic Claude API + knowledge base |

## Current Runtime Behavior

The current code can return three runtime outcomes:
- `fraud`
- `clean`
- `indeterminate`

`indeterminate` can occur when:
- the Anthropic API key is missing or invalid
- an LLM call fails
- a validator response cannot be parsed

So it is not correct to describe the current implementation as always producing
a binary decision under every runtime condition.

## Technology Actually Used in This Repo

| Layer | Current Repo Technology |
| --- | --- |
| Orchestration | LangGraph |
| LLMs | Anthropic Claude Haiku / Sonnet |
| API | Flask |
| UI | Streamlit |
| Tool Integration | MCP |
| Config | python-dotenv |
| Charting | Plotly |
| PDF Forensics | Optional `pikepdf`, `Pillow`, `exiftool-py` |

Things the pasted draft overstated:
- The repo does not currently ship a FastAPI app.
- `requirements.txt` does not currently install FastAPI, Pandas, or Pydantic.

## Dataset

The generator currently creates 660 claims total:
- 200 legitimate claims
- 460 fraudulent claims across 8 fraud types

The generated labels `fraud_indicator` and `fraud_type` are used for dataset
generation and evaluation only. They are not supposed to be read by the
inference path when making a fraud decision.

Primary generator file:
- [src/generate_claims.py](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/src/generate_claims.py)

## Results and Evaluation

This repo should not hard-code a single permanent metrics table in the README.
End-to-end results depend on:
- the current synthetic dataset version
- the current rules and reasoning code
- the model path being used
- whether the Anthropic API key is valid and available

Also, the generated dataset and result artifacts are local files and are
currently gitignored:
- [data/raw_claims/claims.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/data/raw_claims/claims.json)
- [data/final_results/results.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/data/final_results/results.json)
- [data/final_results/metrics.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/data/final_results/metrics.json)

That means readers cannot verify a static metrics table from the repo alone.

To generate a fresh local metrics snapshot:

```bash
python src/generate_claims.py
python run_full_batch.py
python src/evaluate.py
```

If you want explicit model selection from the wrapper script instead:

```bash
python run_pipeline.py --generate
python run_pipeline.py --sample 20
python run_pipeline.py --full
python run_pipeline.py --full --fast
python run_pipeline.py --evaluate
```

## Quick Start

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add your Anthropic API key

The repo loads `.env` automatically in the LLM-based agents.

Create or update:
- [.env](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/.env)

Contents:

```env
ANTHROPIC_API_KEY=your_real_key_here
```

You can also set the environment variable in your shell instead, but `.env`
matches how the current code is written.

### 3. Generate the dataset

```bash
python src/generate_claims.py
```

### 4. Run a full batch locally

```bash
python run_full_batch.py
python src/evaluate.py
```

### 5. Optional entry points

Dashboard:

```bash
streamlit run src/app.py
```

API:

```bash
python src/api.py
```

Wrapper pipeline:

```bash
python run_pipeline.py --sample 20
python run_pipeline.py --full
python run_pipeline.py --evaluate
```

### 6. Optional PDF-forensics dependencies

If you want the full Agent 0 PDF analysis path, install the extra packages noted
in the checker module:

```bash
pip install pikepdf pillow exiftool-py
```

## Example Output Shape

The real saved batch output is a structured claim-level record. A simplified
example looks like this:

```json
{
  "claim_id": "VET00160",
  "species": "reptile",
  "breed": "Bearded Dragon",
  "diagnosis": "Splenic mass",
  "procedures": ["Chemotherapy", "Complete blood count panel"],
  "billed_amount": 590.48,
  "average_market_rate": 585.0,
  "agent1_result": {
    "agent": "rule_checker",
    "timestamp": "2026-07-06T21:51:41.118180",
    "fraud_detected": false,
    "fraud_type": null,
    "decision_status": "clean",
    "explanation": "No rule violations detected. Passing to clinical reasoner."
  },
  "agent2_result": {
    "agent": "clinical_reasoner",
    "timestamp": "2026-07-06T21:51:52.288124",
    "fraud_detected": false,
    "fraud_type": null,
    "confidence": "low",
    "decision_status": "clean",
    "explanation": "Claim appears clinically appropriate.",
    "error": null
  },
  "agent3_result": null,
  "final_verdict": false,
  "final_fraud_type": null,
  "deciding_agent": "clinical_reasoner",
  "decision_status": "clean",
  "errors": []
}
```

Notes:
- Rule-based fraud can finalize after Agent 1 without Agent 2 or Agent 3.
- Agent 3 only appears when Agent 2 has already flagged fraud and the graph
  routes the claim onward for challenge/review.

## Knowledge Base

Current knowledge-base files:
- [knowledge_base/bundle_rules.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/knowledge_base/bundle_rules.json)
- [knowledge_base/species_procedure_rules.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/knowledge_base/species_procedure_rules.json)
- [knowledge_base/species_exceptions.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/knowledge_base/species_exceptions.json)
- [knowledge_base/clinical_whitelist.json](C:/Users/hazel/Desktop/AI/Projects/VetGuardC/knowledge_base/clinical_whitelist.json)

Current local counts:
- bundle rules: 30
- species-procedure rules: 19
- species exceptions: 4
- clinical whitelist entries: 23

The adversarial validator relies on these files when deciding whether a flagged
claim has a documented legitimate exception.

## Project Structure

```text
Attestia-Vet/
|-- AGENTS.md
|-- README.md
|-- README_pasted_corrected.md
|-- requirements.txt
|-- run_full_batch.py
|-- run_pipeline.py
|-- debug_vaccine.py
|-- diagnose_vp.py
|-- test_on_real_data.py
|-- test_claim.pdf
|
|-- src/
|   |-- app.py
|   |-- api.py
|   |-- adversarial_validator.py
|   |-- check_pipeline_path.py
|   |-- clinical_reasoner.py
|   |-- document_integrity_checker.py
|   |-- evaluate.py
|   |-- fraud_engine.py
|   |-- fraud_engine_langgraph.py
|   |-- generate_claims.py
|   |-- rule_checker.py
|   |-- upcoding_rules.json
|   `-- vetguard_mcp_server.py
|
|-- knowledge_base/
|   |-- bundle_rules.json
|   |-- clinical_whitelist.json
|   |-- species_exceptions.json
|   `-- species_procedure_rules.json
|
|-- data/
|   |-- raw_claims/
|   `-- final_results/
|
`-- tests/
    |-- test_adversarial_validator.py
    |-- test_fraud_regressions.py
    `-- test_pipeline_status.py
```

Important note:
- `src/upcoding_rules.json` exists in the repo as reference data, but it is not
  currently wired into the active runtime path.

## Design Decisions That Are True Today

### Rule-first architecture

Deterministic issues such as unbundling or species-rule violations are handled
first by Agent 1.

### Evidence-based overrides

Agent 3 is intentionally conservative. It is designed to rescue a claim only
when a knowledge-base entry supports doing so.

### Shared tool-backed reasoning

The Clinical Reasoner and the MCP server both work from the same underlying
knowledge-base files for bundle checks, species validity checks, and whitelist
lookups.

### Optional PDF pre-check

Agent 0 exists and is wired into the unified engine when a claim includes a
`pdf_path`, but its deepest analysis requires optional packages not installed by
default.

## Important Limitations

- The current codebase still has inconsistent naming between `Attestia Vet` and
  `VetGuard`.
- Model defaults are not uniform across every entry point.
  `run_pipeline.py` exposes explicit Haiku/Sonnet selection, while other entry
  points rely on module defaults or UI selection.
- Result quality depends on a valid Anthropic API key.
- If the key is invalid, many non-rule claims will end up as `indeterminate`
  rather than receiving a complete decision.

## Potential Next Steps

- Standardize naming across the repo (`Attestia Vet` vs `VetGuard`)
- Add a fail-fast API-key preflight before long batch runs
- Make model selection consistent across all entry points
- Decide whether evaluation should allow `indeterminate` or always force a
  binary verdict
- Expand PDF support with documented optional dependencies and sample workflows

## Author

Hazel Zhang

## License

This project is presented as a demonstration / educational repository unless
the author states otherwise elsewhere.
