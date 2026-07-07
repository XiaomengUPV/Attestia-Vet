"""
Attestia Vet — Agent 1: Rule Checker
Deterministic fraud detection for:
- Duplicate billing
- Unbundling            (knowledge_base/bundle_rules.json)
- Species mismatch      (knowledge_base/species_procedure_rules.json)
- Modifier abuse
"""

import json
from pathlib import Path

# Load knowledge bases
KB = Path(__file__).parent.parent / "knowledge_base"

with open(KB / "bundle_rules.json", "r", encoding="utf-8") as f:
    BUNDLE_RULES = json.load(f)

with open(KB / "species_procedure_rules.json", "r", encoding="utf-8") as f:
    SPECIES_RULES = json.load(f)

with open(KB / "species_exceptions.json", "r", encoding="utf-8") as f:
    SPECIES_EXCEPTIONS = json.load(f)


WELLNESS_MARKERS = ("wellness", "preventive", "health check")


def _is_vaccine_procedure(procedure: str) -> bool:
    proc_lower = procedure.lower()
    return "vaccine" in proc_lower or "core vaccine series" in proc_lower


def _looks_like_vaccine_padding_candidate(claim: dict) -> bool:
    """True when the claim looks like a multi-vaccine wellness stack.

    These claims are still fraudulent, but we let Agent 2 assign the more
    specific 'Vaccine padding' label instead of short-circuiting as duplicate
    billing, species mismatch, or unbundling.
    """
    procedures = claim.get("procedures", [])
    vaccine_count = sum(1 for proc in procedures if _is_vaccine_procedure(proc))
    diagnosis_lower = claim.get("diagnosis", "").lower()
    has_wellness_context = any(marker in diagnosis_lower for marker in WELLNESS_MARKERS) or \
        any("annual wellness exam" in proc.lower() for proc in procedures)
    return vaccine_count >= 2 and has_wellness_context


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


def _exception_possible(proc_lower: str, species_lower: str) -> bool:
    """True when the species-exceptions KB documents a legitimate scenario
    for this procedure+species — those cases are escalated to the clinical
    reasoner (Agent 2) instead of being hard-flagged."""
    for exc in SPECIES_EXCEPTIONS:
        if exc["procedure"].lower() in proc_lower and \
           species_lower in [x.lower() for x in exc.get("species", [])]:
            return True
    return False


def check_species_mismatch(species: str, procedures: list) -> tuple:
    """
    Check procedures against the species-validity knowledge base.

    Hard-flags only UNAMBIGUOUS violations (no documented exception exists).
    Where the knowledge bases conflict — the species rules forbid it but the
    exceptions KB documents a legitimate specialist scenario — the claim is
    passed to Agent 2, whose tools include the whitelist, to adjudicate.
    """
    species_lower = (species or "").lower()
    for proc in procedures:
        proc_lower = proc.lower()
        for rule in SPECIES_RULES:
            if rule["procedure"].lower() in proc_lower:
                if species_lower in [s.lower() for s in rule.get("invalid_species", [])]:
                    if _exception_possible(proc_lower, species_lower):
                        return (False, None, None)   # escalate to Agent 2
                    return (True, "Species mismatch",
                            f"'{proc}' billed for a {species} — {rule['rule']}")
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
    vaccine_padding_candidate = _looks_like_vaccine_padding_candidate(claim)

    # 1. Duplicate billing
    fraud, fraud_type, explanation = check_duplicate_billing(claim["procedures"])
    if fraud and not vaccine_padding_candidate:
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
    if fraud and not vaccine_padding_candidate:
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
    
    # 3. Species mismatch (knowledge-base rule)
    fraud, fraud_type, explanation = check_species_mismatch(claim.get("species",""), claim["procedures"])
    if fraud and not vaccine_padding_candidate:
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

    # 4. Modifier abuse
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
