"""
VetGuard — Agent 1: Rule Checker
Deterministic fraud detection ONLY for:
- Duplicate billing
- Unbundling  
- Modifier abuse
"""

import json
from pathlib import Path

# Load knowledge bases
BUNDLE_RULES_PATH = Path(__file__).parent.parent / "knowledge_base" / "bundle_rules.json"

with open(BUNDLE_RULES_PATH, "r", encoding="utf-8") as f:
    BUNDLE_RULES = json.load(f)


def check_duplicate_billing(procedures: list) -> tuple:
    """Check for duplicate procedures in the same claim."""
    seen = {}
    for proc in procedures:
        proc_lower = proc.lower()
        if proc_lower in seen:
            return (True, "Duplicate billing", f"Procedure '{proc}' appears more than once on the same claim.")
        seen[proc_lower] = True
    return (False, None, None)


def check_unbundling(procedures: list) -> tuple:
    """Check if procedures are billed separately when they should be bundled."""
    for rule in BUNDLE_RULES:
        proc1 = rule["procedure_1"]
        proc2 = rule["procedure_2"]
        if proc1 in procedures and proc2 in procedures:
            return (True, "Unbundling", f"'{proc1}' and '{proc2}' billed together — {rule['rule']}")
    return (False, None, None)


def check_modifier_abuse(claim: dict) -> tuple:
    """Check if emergency modifier is applied to non-emergency diagnosis."""
    modifier = claim.get("modifier")
    if modifier == "emergency":
        diagnosis = claim.get("diagnosis", "").lower()
        emergency_keywords = ["emergency", "trauma", "rupture", "fracture", "severe", "acute", "torsion", "block"]
        if not any(kw in diagnosis for kw in emergency_keywords):
            return (True, "Modifier abuse", f"Emergency modifier applied but diagnosis '{claim['diagnosis']}' is not an emergency condition.")
    return (False, None, None)


def run(claim: dict) -> dict:
    """Run rule checks. Only handles duplicate billing, unbundling, and modifier abuse."""
    
    # 1. Duplicate billing
    fraud, fraud_type, explanation = check_duplicate_billing(claim["procedures"])
    if fraud:
        return {
            "claim_id": claim["claim_id"],
            "agent": "rule_checker",
            "fraud_detected": True,
            "fraud_type": fraud_type,
            "confidence": "high",
            "explanation": explanation,
            "rule_cited": explanation,
            "pass_to_agent2": False
        }
    
    # 2. Unbundling
    fraud, fraud_type, explanation = check_unbundling(claim["procedures"])
    if fraud:
        return {
            "claim_id": claim["claim_id"],
            "agent": "rule_checker",
            "fraud_detected": True,
            "fraud_type": fraud_type,
            "confidence": "high",
            "explanation": explanation,
            "rule_cited": explanation.split("—")[1].strip() if "—" in explanation else explanation,
            "pass_to_agent2": False
        }
    
    # 3. Modifier abuse
    fraud, fraud_type, explanation = check_modifier_abuse(claim)
    if fraud:
        return {
            "claim_id": claim["claim_id"],
            "agent": "rule_checker",
            "fraud_detected": True,
            "fraud_type": fraud_type,
            "confidence": "high",
            "explanation": explanation,
            "rule_cited": explanation,
            "pass_to_agent2": False
        }
    
    # No rule violations — pass to LLM for everything else
    return {
        "claim_id": claim["claim_id"],
        "agent": "rule_checker",
        "fraud_detected": False,
        "fraud_type": None,
        "confidence": "high",
        "explanation": "No rule violations detected. Passing to clinical reasoner.",
        "rule_cited": None,
        "pass_to_agent2": True
    }


if __name__ == "__main__":
    test_claims = [
        {
            "claim_id": "TEST001",
            "species": "dog",
            "procedures": ["Annual wellness exam", "Annual wellness exam"],
            "diagnosis": "Routine wellness",
            "modifier": None
        },
        {
            "claim_id": "TEST002",
            "species": "dog",
            "procedures": ["Annual wellness exam", "Physical examination"],
            "diagnosis": "Routine wellness",
            "modifier": None
        },
        {
            "claim_id": "TEST003",
            "species": "dog",
            "procedures": ["Annual wellness exam"],
            "diagnosis": "Routine wellness",
            "modifier": "emergency"
        },
    ]
    
    for claim in test_claims:
        result = run(claim)
        print(f"{claim['claim_id']}: {result['fraud_type'] if result['fraud_detected'] else 'Clean'} — {result['explanation'][:80]}")