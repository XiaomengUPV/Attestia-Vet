"""
VetGuard — Agent 3: Adversarial Validator
Novel contribution: challenges Agent 2's fraud verdict.
Only overrides if Claude can cite a specific whitelist entry.
Prevents false positives on legitimate but unusual procedure-diagnosis pairs.
Now enhanced to better handle phantom billing and species mismatch cases.
"""

import json
import anthropic
from pathlib import Path

client = anthropic.Anthropic()
KB = Path(__file__).parent.parent / "knowledge_base"

with open(KB / "clinical_whitelist.json", "r", encoding="utf-8") as f:
    WHITELIST = json.load(f)

# Additional legitimate species-procedure exceptions that are clinically valid
# but might be flagged as fraud by Agent 2
SPECIES_EXCEPTIONS = [
    # TPLO in cats - legitimate for feline cruciate repair (though less common)
    {"procedure": "TPLO surgery", "species": ["cat"], "diagnosis": ["cranial cruciate ligament rupture", "fracture", "hip dysplasia"], 
     "rationale": "TPLO is a recognized surgical technique for cruciate ligament disease in cats, though less common than in dogs", "source": "ACVS feline orthopedic guidelines"},
    # Echocardiogram in reptiles - can be performed by specialists
    {"procedure": "Echocardiogram complete", "species": ["reptile"], "diagnosis": ["dilated cardiomyopathy", "pericardial effusion", "mitral valve disease"],
     "rationale": "Advanced cardiac imaging is possible in large reptiles under sedation with specialized equipment", "source": "Specialist exotic animal practice"},
    # Chemotherapy in birds - legitimate for avian oncology
    {"procedure": "Chemotherapy", "species": ["bird"], "diagnosis": ["lymphoma", "mast cell tumor"],
     "rationale": "Chemotherapy protocols exist for avian species at specialized exotic animal centers", "source": "Association of Avian Veterinarians"},
    # General anesthesia in reptiles - legitimate under proper protocols
    {"procedure": "General anesthesia", "species": ["reptile"], "diagnosis": ["fracture", "surgery", "diagnostic imaging"],
     "rationale": "Reptiles can safely receive injectable and inhalant anesthesia with appropriate monitoring", "source": "Journal of Herpetological Medicine"},
]

# Expand whitelist with species exceptions at runtime
EXTENDED_WHITELIST = WHITELIST + SPECIES_EXCEPTIONS


def build_whitelist_context(claim: dict) -> str:
    """Find whitelist entries relevant to this claim's procedures and diagnosis, including species exceptions."""
    diagnosis_lower = claim["diagnosis"].lower()
    species_lower = claim["species"].lower()
    procedures_lower = [p.lower() for p in claim["procedures"]]

    relevant = []
    
    for entry in EXTENDED_WHITELIST:
        # Check procedure match
        proc_match = False
        if "procedure" in entry:
            entry_proc = entry["procedure"].lower()
            proc_match = any(entry_proc in p or p in entry_proc for p in procedures_lower)
        
        # Check diagnosis match
        diag_match = False
        if "diagnosis" in entry:
            if isinstance(entry["diagnosis"], list):
                diag_match = any(d.lower() in diagnosis_lower or diagnosis_lower in d.lower() 
                                for d in entry["diagnosis"])
            else:
                diag_match = entry["diagnosis"].lower() in diagnosis_lower or \
                             diagnosis_lower in entry["diagnosis"].lower()
        
        # Check species match (for species exceptions)
        species_match = False
        if "species" in entry:
            species_match = species_lower in [s.lower() for s in entry["species"]]
        
        # For species exceptions, require species match
        if "species" in entry:
            if species_match and proc_match:
                relevant.append(entry)
        elif proc_match or diag_match:
            relevant.append(entry)

    if not relevant:
        return "No matching whitelist entries found for this procedure-diagnosis-species combination."

    lines = ["Potentially relevant whitelist entries and clinical exceptions:"]
    for e in relevant[:15]:  # Limit to 15 entries to avoid context overflow
        if "species" in e:
            lines.append(f"- {e['procedure']} on {', '.join(e['species'])} for {e['diagnosis']}: {e['rationale']} (Source: {e['source']})")
        else:
            lines.append(f"- {e['procedure']} + {e['diagnosis']}: {e['rationale']} (Source: {e['source']})")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a senior veterinary clinician reviewing a fraud analyst's decision.
Your role is to CHALLENGE the fraud verdict — construct the strongest possible clinical argument
that the claim is LEGITIMATE.

Rules you must follow:
1. You may only override the fraud verdict if you can cite a SPECIFIC entry from the provided whitelist or clinical exceptions.
2. For SPECIES MISMATCH fraud: Override ONLY if the procedure is actually possible for the species in specialized practice.
   - TPLO in cats → MAY override if documented reason exists
   - Echocardiogram in reptiles → MAY override for large reptiles with specialist equipment
   - General anesthesia in reptiles → MAY override with proper protocol documentation
3. For PHANTOM BILLING fraud: Override ONLY if the procedure is technically feasible for the species.
4. For UPCODING fraud: Override ONLY if the complex procedure is medically justified (e.g., senior pet needs comprehensive panel).
5. For VACCINE PADDING fraud: Override ONLY if this is a legitimate puppy/kitten series or multi-valent vaccine.
6. General clinical reasoning alone is NOT sufficient to override — you must cite the whitelist or exception.
7. If no whitelist entry applies, you must uphold the fraud verdict.
8. Be precise and conservative — false negatives (missed fraud) are more costly than false positives.

When evaluating species mismatch:
- Consider if the procedure is anatomically possible (e.g., TPLO in cats IS possible, just less common)
- Consider if specialist referral centers might perform this procedure
- Only override if you can cite a legitimate clinical justification

When evaluating phantom billing:
- Determine if the procedure is PHYSICALLY IMPOSSIBLE (fish anesthesia) vs. just uncommon
- Only override if there's documented clinical necessity and feasibility

Respond ONLY with a valid JSON object — no preamble, no markdown.
"""

CHALLENGE_TEMPLATE = """A fraud analyst flagged this claim. Challenge the verdict.

ORIGINAL CLAIM:
- Species: {species} ({breed})
- Diagnosis: {diagnosis}
- Procedures: {procedures}
- Fraud verdict: {fraud_type} (confidence: {confidence})
- Analyst explanation: {explanation}

WHITELIST REFERENCE (including clinical exceptions):
{whitelist_context}

INSTRUCTIONS:
Construct the strongest possible argument that this claim is LEGITIMATE.
You may ONLY override if a specific whitelist entry or clinical exception supports it.
If no whitelist entry applies, uphold the fraud verdict.

For SPECIES MISMATCH cases:
- Ask: Is this procedure actually possible for this species?
- If yes and you can cite a source, consider override

For PHANTOM BILLING cases:
- Ask: Is this procedure technically feasible?
- Consider: Would a specialist referral center perform this?

For UPCODING cases:
- Ask: Is there clinical justification for the more complex procedure?
- Example: Senior pet, chronic condition, specific symptoms

For VACCINE PADDING cases:
- Ask: Is this a legitimate puppy/kitten series?
- Consider: Age of animal, vaccine types

Respond ONLY with this JSON:
{{
  "override_applied": true or false,
  "whitelist_entry_cited": "exact procedure + diagnosis + species combination from whitelist" or null,
  "override_rationale": "clinical justification citing the whitelist entry or exception" or null,
  "final_fraud_detected": true or false,
  "validator_explanation": "one sentence summary of your decision"
}}"""


def run(claim: dict, agent2_result: dict, model: str = "claude-haiku-4-5-20251001") -> dict:
    """
    Challenge Agent 2's fraud verdict.
    Only called when Agent 2 detected fraud.
    """
    whitelist_context = build_whitelist_context(claim)

    prompt = CHALLENGE_TEMPLATE.format(
        species=claim["species"],
        breed=claim.get("breed", "Unknown"),
        diagnosis=claim["diagnosis"],
        procedures=", ".join(claim["procedures"]),
        fraud_type=agent2_result.get("fraud_type", "Unknown"),
        confidence=agent2_result.get("confidence", "Unknown"),
        explanation=agent2_result.get("explanation", ""),
        whitelist_context=whitelist_context
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=768,  # Increased for more detailed reasoning
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

        return {
            "claim_id": claim["claim_id"],
            "agent": "adversarial_validator",
            "override_applied": result.get("override_applied", False),
            "whitelist_entry_cited": result.get("whitelist_entry_cited"),
            "override_rationale": result.get("override_rationale"),
            "final_fraud_detected": result.get("final_fraud_detected", True),
            "validator_explanation": result.get("validator_explanation", ""),
            "raw_response": raw
        }

    except json.JSONDecodeError as e:
        # Parse failure — conservatively uphold the fraud verdict
        return {
            "claim_id": claim["claim_id"],
            "agent": "adversarial_validator",
            "override_applied": False,
            "whitelist_entry_cited": None,
            "override_rationale": None,
            "final_fraud_detected": True,
            "validator_explanation": f"Parse error — fraud verdict upheld: {str(e)}",
            "raw_response": ""
        }
    except Exception as e:
        return {
            "claim_id": claim["claim_id"],
            "agent": "adversarial_validator",
            "override_applied": False,
            "whitelist_entry_cited": None,
            "override_rationale": None,
            "final_fraud_detected": True,
            "validator_explanation": f"API error — fraud verdict upheld: {str(e)}",
            "raw_response": ""
        }


if __name__ == "__main__":
    # Test case: TPLO on cat (should potentially be overridden)
    test_claim = {
        "claim_id": "TEST001",
        "species": "cat",
        "breed": "Domestic Shorthair",
        "age": 7,
        "diagnosis": "Cranial cruciate ligament rupture",
        "procedures": ["TPLO surgery"],
        "billed_amount": 3675.00,
        "average_market_rate": 3500.00,
        "modifier": None
    }
    agent2_mock = {
        "fraud_detected": True,
        "fraud_type": "Species mismatch",
        "confidence": "high",
        "explanation": "TPLO surgery is a canine-specific procedure that cannot be performed on cats"
    }
    result = run(test_claim, agent2_mock)
    print(json.dumps(result, indent=2))
    
    # Test case: Echocardiogram on reptile (should potentially be overridden)
    test_claim2 = {
        "claim_id": "TEST002",
        "species": "reptile",
        "breed": "Bearded Dragon",
        "age": 5,
        "diagnosis": "Pericardial effusion",
        "procedures": ["Echocardiogram complete"],
        "billed_amount": 472.50,
        "average_market_rate": 450.00,
        "modifier": None
    }
    agent2_mock2 = {
        "fraud_detected": True,
        "fraud_type": "Phantom billing",
        "confidence": "high",
        "explanation": "Echocardiogram cannot be performed on reptiles due to anatomical limitations"
    }
    result2 = run(test_claim2, agent2_mock2)
    print(json.dumps(result2, indent=2))