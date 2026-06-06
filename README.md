# VetGuard 🐾
### Veterinary Billing Fraud Detection — Three-Agent Autonomous System

Built with Claude Sonnet 4.6 + Python. Detects billing fraud in veterinary claims across 8 fraud types using a cascading three-agent architecture.

---

## Architecture

```
Claim → Agent 1 (Rule Checker) → Agent 2 (Clinical Reasoner) → Agent 3 (Adversarial Validator) → Verdict
```

| Agent | Method | Detects | Cost |
|---|---|---|---|
| Rule Checker | Deterministic Python | Duplicate billing, Unbundling, Species mismatch, Modifier abuse | $0 |
| Clinical Reasoner | Claude API + structured prompts | Phantom billing, Diagnosis mismatch, Upcoding, Vaccine padding | ~$0.001/claim |
| Adversarial Validator | Claude API + whitelist RAG | False positives from Agent 2 | ~$0.001/claim |

**Memory architecture (3-tier):**
- Short-term: Python dict session state (claim in flight)
- Working memory: Structured CAG context passed between agents
- Long-term: JSON knowledge bases (bundle rules, species validity, whitelist, historical verdicts)

---

## Setup

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Set your Anthropic API key
export ANTHROPIC_API_KEY="your-key-here"

# 3. Generate the dataset
python run_pipeline.py --generate

# 4. Test on 20 claims (costs ~$0.02)
python run_pipeline.py --sample 20

# 5. Run full evaluation (costs ~$0.50)
python run_pipeline.py --full

# 6. Launch the dashboard
streamlit run src/app.py
```

---

## Dataset

600 synthetic veterinary claims across 8 fraud types:

| Fraud Type | Count | Detection Method |
|---|---|---|
| Legitimate | 200 | — |
| Duplicate billing | 50 | Rule (Agent 1) |
| Unbundling | 60 | Rule (Agent 1) |
| Species mismatch | 50 | Rule (Agent 1) |
| Modifier abuse | 60 | Rule (Agent 1) |
| Phantom billing | 60 | LLM (Agent 2) |
| Diagnosis mismatch | 60 | LLM (Agent 2) |
| Upcoding | 60 | LLM (Agent 2) |
| Vaccine padding | 60 | LLM (Agent 2) |

Species/breed distributions grounded in real pet insurance data (50K+ policies).

---

## Deployment (Streamlit Cloud)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set main file to `src/app.py`
4. Add `ANTHROPIC_API_KEY` in Secrets
5. Deploy — live URL in ~2 minutes

---

## Knowledge Bases

| File | Contents |
|---|---|
| `bundle_rules.json` | 30 veterinary procedure bundling rules |
| `species_procedure_rules.json` | 30 species-procedure validity rules |
| `clinical_whitelist.json` | 20 legitimate but unusual procedure-diagnosis pairs |

---

## Interview Notes

**Why veterinary billing?** Identical billing structure to human medical claims (procedures, diagnoses, pricing, bundling rules) but legally safe — no HIPAA restrictions, publicly available pricing data.

**Novel contribution:** Agent 3 (Adversarial Validator) challenges Agent 2's verdict by constructing the strongest possible argument for legitimacy. It can only override by citing a specific whitelist entry — preventing over-permissiveness.

**Species mismatch detection** is unique to veterinary billing and has no equivalent in human medical fraud detection systems.
