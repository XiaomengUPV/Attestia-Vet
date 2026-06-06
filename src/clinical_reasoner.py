"""
VetGuard — Agent 2: Clinical Reasoner
SIMPLIFIED WORKING VERSION
"""

import json

# ============================================================
# VACCINE PADDING - SIMPLE BUT RELIABLE
# ============================================================

# Direct list of vaccine procedure names (exact matches)
VACCINE_NAMES = [
    "Rabies vaccine",
    "DHPP vaccine", 
    "Bordetella bronchiseptica vaccine (canine)",
    "Feline leukemia vaccine",
    "Feline panleukopenia vaccine",
    "Canine distemper vaccine",
    "Core vaccine series"
]

def check_vaccine_padding(procedures: list) -> tuple:
    """Count vaccines directly by name."""
    vaccine_count = 0
    vaccine_list = []
    
    for proc in procedures:
        # Direct match against vaccine names
        for vname in VACCINE_NAMES:
            if proc == vname or vname in proc:
                vaccine_count += 1
                vaccine_list.append(proc)
                break
    
    # Core vaccine series counts extra
    if "Core vaccine series" in procedures:
        vaccine_count += 1  # Count as 2 total
    
    if vaccine_count >= 3:
        return (True, "Vaccine padding", f"{vaccine_count} vaccines")
    return (False, None, None)


# ============================================================
# SPECIES MISMATCH
# ============================================================

def check_species_mismatch(species: str, procedures: list) -> tuple:
    species_lower = species.lower()
    
    # List of species-specific procedure patterns
    checks = [
        # Feline-specific
        ("feline leukemia", "cat"),
        ("feline panleukopenia", "cat"),
        ("feline immunodeficiency", "cat"),
        # Canine-specific
        ("canine heartworm", "dog"),
        ("canine distemper", "dog"),
        ("heartworm test", "dog"),
    ]
    
    for proc in procedures:
        proc_lower = proc.lower()
        
        for pattern, expected_species in checks:
            if pattern in proc_lower:
                if species_lower != expected_species:
                    return (True, "Species mismatch", f"'{proc}' is for {expected_species}s only")
        
        # Also check by species name in procedure
        if "feline" in proc_lower and species_lower != "cat":
            return (True, "Species mismatch", f"'{proc}' is for cats only")
        
        if "canine" in proc_lower and species_lower != "dog":
            return (True, "Species mismatch", f"'{proc}' is for dogs only")
    
    return (False, None, None)


# ============================================================
# PHANTOM BILLING
# ============================================================

PHANTOM_PAIRS = [
    ("General anesthesia", "fish"),
    ("TPLO surgery", "fish"), ("TPLO surgery", "hamster"), ("TPLO surgery", "bird"),
    ("MRI brain scan", "fish"), ("MRI brain scan", "hamster"),
    ("Total hip replacement", "hamster"), ("Total hip replacement", "bird"),
    ("Echocardiogram complete", "reptile"),
]

def check_phantom_billing(species: str, procedures: list) -> tuple:
    species_lower = species.lower()
    for proc in procedures:
        proc_lower = proc.lower()
        for phantom_proc, phantom_species in PHANTOM_PAIRS:
            if phantom_proc.lower() in proc_lower and phantom_species == species_lower:
                return (True, "Phantom billing", f"'{proc}' cannot be performed on {species}")
    return (False, None, None)


# ============================================================
# DIAGNOSIS MISMATCH
# ============================================================

WELLNESS_KEYWORDS = ["wellness", "health check", "preventive care", "annual health check"]
MAJOR_PROCEDURES = ["chemotherapy", "tplo surgery", "amputation", "splenectomy", 
                    "renal transplant", "pacemaker implantation", "chop protocol"]

def check_diagnosis_mismatch(diagnosis: str, procedures: list) -> tuple:
    diagnosis_lower = diagnosis.lower()
    is_wellness = any(kw in diagnosis_lower for kw in WELLNESS_KEYWORDS)
    if not is_wellness:
        return (False, None, None)
    
    for p in procedures:
        p_lower = p.lower()
        for major in MAJOR_PROCEDURES:
            if major in p_lower:
                return (True, "Diagnosis mismatch", f"'{p}' with wellness diagnosis")
    return (False, None, None)


# ============================================================
# UPCODING
# ============================================================

def check_upcoding(procedures: list, diagnosis: str) -> tuple:
    diagnosis_lower = diagnosis.lower()
    is_wellness = any(kw in diagnosis_lower for kw in WELLNESS_KEYWORDS)
    
    if "Comprehensive metabolic panel" in procedures and is_wellness:
        return (True, "Upcoding", "CMP is upcoding for wellness")
    
    if "IV catheter placement" in procedures and is_wellness:
        return (True, "Upcoding", "IV catheter is upcoding for wellness")
    
    if "Ear cytology and flush" in procedures:
        if any(kw in diagnosis_lower for kw in ["dental", "periodontal", "tooth"]):
            return (True, "Upcoding", "Ear cytology and flush is upcoding")
    
    return (False, None, None)


# ============================================================
# MAIN
# ============================================================

def run(claim: dict, model: str = None) -> dict:
    # Reordered: Vaccine padding BEFORE Species mismatch
    checks = [
        ("Phantom billing", check_phantom_billing(claim["species"], claim["procedures"])),
        ("Vaccine padding", check_vaccine_padding(claim["procedures"])),  # MOVED UP
        ("Diagnosis mismatch", check_diagnosis_mismatch(claim["diagnosis"], claim["procedures"])),
        ("Species mismatch", check_species_mismatch(claim["species"], claim["procedures"])),
        ("Upcoding", check_upcoding(claim["procedures"], claim["diagnosis"])),
    ]
    
    for fraud_type, (detected, _, explanation) in checks:
        if detected:
            return {
                "claim_id": claim["claim_id"],
                "agent": "clinical_reasoner",
                "fraud_detected": True,
                "fraud_type": fraud_type,
                "confidence": "high",
                "explanation": explanation,
                "clinical_flags": [fraud_type],
                "pass_to_agent3": True,
                "raw_response": ""
            }
    
    return {
        "claim_id": claim["claim_id"],
        "agent": "clinical_reasoner",
        "fraud_detected": False,
        "fraud_type": None,
        "confidence": "high",
        "explanation": "No fraud detected",
        "clinical_flags": [],
        "pass_to_agent3": False,
        "raw_response": ""
    }

if __name__ == "__main__":
    # Quick test
    test_procedures = [
        ['Annual wellness exam', 'Rabies vaccine', 'Feline leukemia vaccine', 'DHPP vaccine'],
        ['Annual wellness exam', 'Rabies vaccine', 'Core vaccine series', 'Bordetella bronchiseptica vaccine (canine)'],
    ]
    
    for procs in test_procedures:
        result = check_vaccine_padding(procs)
        print(f"{procs} -> {result[0] if result[0] else 'Clean'} ({result[2] if result[0] else ''})")