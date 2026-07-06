"""
Attestia Vet — Fraud Engine (unified)
Thin wrapper: every entry point (dashboard, batch, pipeline) runs the SAME
LangGraph cascade — Agent 1 rules -> Agent 2 tool-using Claude reasoner ->
Agent 3 adversarial validator — plus the Agent 0 PDF-forensics pre-check
when a document is attached.
"""

import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

import fraud_engine_langgraph as _graph_engine


def process_claim(claim: dict, model: str = None, verbose: bool = False) -> dict:
    t_start = time.time()

    # Agent 0: document integrity (only when a PDF is attached)
    if claim.get("pdf_path"):
        from document_integrity_checker import run_agent_zero
        doc = run_agent_zero(claim["pdf_path"], verbose=verbose)
        if doc["fraud_detected"]:
            return {
                "claim_id": claim["claim_id"],
                "species": claim.get("species"),
                "diagnosis": claim.get("diagnosis"),
                "procedures": claim.get("procedures"),
                "ground_truth_fraud": claim.get("fraud_indicator"),
                "ground_truth_type": claim.get("fraud_type"),
                "agent0_result": doc,
                "final_verdict": True,
                "final_fraud_type": doc["fraud_type"],
                "deciding_agent": "document_integrity_checker",
                "processing_time_ms": round((time.time() - t_start) * 1000, 1),
            }

    # Agents 1-3 via the LangGraph cascade
    engine = _get_engine()
    g = engine.process_claim(claim)

    # Normalize to the audit schema the dashboard/evaluator expect,
    # while keeping the graph's own fields and audit trail.
    trail = {e.get("agent"): e for e in g.get("audit_trail", []) if isinstance(e, dict)}
    return {
        "claim_id": claim["claim_id"],
        "species": claim.get("species"),
        "breed": claim.get("breed"),
        "diagnosis": claim.get("diagnosis"),
        "procedures": claim.get("procedures"),
        "billed_amount": claim.get("billed_amount"),
        "average_market_rate": claim.get("average_market_rate"),
        "ground_truth_fraud": claim.get("fraud_indicator"),
        "ground_truth_type": claim.get("fraud_type"),
        "agent1_result": trail.get("rule_checker"),
        "agent2_result": trail.get("clinical_reasoner"),
        "agent3_result": trail.get("adversarial_validator"),
        "final_verdict": bool(g.get("fraud_detected")),
        "final_fraud_type": g.get("fraud_type") if g.get("fraud_detected") else None,
        "deciding_agent": g.get("deciding_agent"),
        "errors": g.get("errors") or [],
        "audit_trail": g.get("audit_trail", []),
        "processing_time_ms": round((time.time() - t_start) * 1000, 1),
    }


_ENGINE = None
def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = _graph_engine.VetGuardAgent()
    return _ENGINE


def run_batch(claims: list, model: str = None, use_fast_model: bool = False,
              verbose: bool = True) -> list:
    results = []
    total = len(claims)
    for i, claim in enumerate(claims):
        if verbose and i % 50 == 0:
            print(f"Processing claim {i+1}/{total}...")
        results.append(process_claim(claim))
    return results
