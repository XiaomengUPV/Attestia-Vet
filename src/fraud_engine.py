"""
VetGuard — Fraud Engine
Uses direct rules in clinical_reasoner for ALL fraud detection.
"""

import json
import time
from pathlib import Path
import rule_checker
import clinical_reasoner


def process_claim(claim: dict, model: str = None, verbose: bool = False) -> dict:
    """
    Run a single claim through all agents.
    Priority: rule_checker → clinical_reasoner (direct rules)
    """
    audit = {
        "claim_id": claim["claim_id"],
        "species": claim["species"],
        "breed": claim.get("breed"),
        "diagnosis": claim["diagnosis"],
        "procedures": claim["procedures"],
        "billed_amount": claim.get("billed_amount"),
        "average_market_rate": claim.get("average_market_rate"),
        "ground_truth_fraud": claim.get("fraud_indicator"),
        "ground_truth_type": claim.get("fraud_type"),
        "agent1_result": None,
        "agent2_result": None,
        "agent3_result": None,
        "final_verdict": None,
        "final_fraud_type": None,
        "deciding_agent": None,
        "processing_time_ms": None
    }

    t_start = time.time()

    # ── Agent 1: Rule checker (deterministic for basic fraud) ──
    a1 = rule_checker.run(claim)
    audit["agent1_result"] = a1

    if verbose:
        print(f"  Agent 1: fraud={a1['fraud_detected']} type={a1['fraud_type']}")

    # If rule checker found fraud, stop here
    if a1["fraud_detected"]:
        audit["final_verdict"] = True
        audit["final_fraud_type"] = a1["fraud_type"]
        audit["deciding_agent"] = "rule_checker"
        audit["processing_time_ms"] = round((time.time() - t_start) * 1000, 1)
        return audit

    # ── Agent 2: Clinical reasoner (DIRECT RULES for all other fraud) ──
    a2 = clinical_reasoner.run(claim)
    audit["agent2_result"] = a2

    if verbose:
        print(f"  Agent 2: fraud={a2['fraud_detected']} type={a2['fraud_type']}")

    # Use clinical_reasoner's decision directly (no adversarial validator)
    audit["final_verdict"] = a2["fraud_detected"]
    audit["final_fraud_type"] = a2["fraud_type"] if a2["fraud_detected"] else None
    audit["deciding_agent"] = "clinical_reasoner"
    audit["processing_time_ms"] = round((time.time() - t_start) * 1000, 1)
    
    return audit


def run_batch(claims: list, model: str = None, use_fast_model: bool = False,
              verbose: bool = True) -> list:
    """Process a batch of claims."""
    results = []
    total = len(claims)
    for i, claim in enumerate(claims):
        if verbose and i % 50 == 0:
            print(f"Processing claim {i+1}/{total}...")
        result = process_claim(claim, verbose=False)
        results.append(result)
    return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    claims_path = Path(__file__).parent.parent / "data" / "raw_claims" / "claims.json"
    if not claims_path.exists():
        print("Run generate_claims.py first to create the dataset.")
        sys.exit(1)

    with open(claims_path) as f:
        claims = json.load(f)

    sample = claims[:10]
    print(f"Testing on {len(sample)} claims...\n")

    for claim in sample:
        print(f"Claim {claim['claim_id']}: {claim['species']} | {claim['diagnosis']}")
        result = process_claim(claim, verbose=True)
        print(f"  → Final: fraud={result['final_verdict']} type={result['final_fraud_type']} "
              f"agent={result['deciding_agent']} ({result['processing_time_ms']}ms)\n")