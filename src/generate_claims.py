"""
VetGuard - Synthetic Veterinary Claims Generator
Generates 660 labeled claims across 8 fraud types + legitimate claims.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

SPECIES_BREEDS = {
    "dog": {
        "weight": 0.65,
        "breeds": ["Labrador Retriever", "Golden Retriever", "French Bulldog",
                   "German Shepherd", "Bulldog", "Poodle", "Beagle", "Rottweiler",
                   "Yorkshire Terrier", "Dachshund", "Siberian Husky", "Chihuahua"]
    },
    "cat": {
        "weight": 0.28,
        "breeds": ["Domestic Shorthair", "Maine Coon", "Ragdoll", "Bengal",
                   "Siamese", "Persian", "British Shorthair", "Scottish Fold"]
    },
    "rabbit": {"weight": 0.03, "breeds": ["Holland Lop", "Mini Rex", "Netherland Dwarf"]},
    "bird":   {"weight": 0.02, "breeds": ["African Grey", "Cockatiel", "Budgerigar"]},
    "hamster":{"weight": 0.01, "breeds": ["Syrian Hamster", "Dwarf Hamster"]},
    "fish":   {"weight": 0.005,"breeds": ["Koi", "Goldfish", "Betta"]},
    "reptile":{"weight": 0.005,"breeds": ["Bearded Dragon", "Leopard Gecko", "Ball Python"]}
}

PROCEDURE_RATES = {
    "Annual wellness exam": 65, "Physical examination": 55,
    "Comprehensive dental cleaning": 400, "Tooth extraction": 150,
    "Dental scaling": 200, "Complete blood count panel": 85,
    "White blood cell count": 35, "Red blood cell count": 30,
    "Comprehensive metabolic panel": 110, "Liver enzyme test": 45,
    "Kidney function test": 45, "Rabies vaccine": 25, "DHPP vaccine": 35,
    "Bordetella bronchiseptica vaccine (canine)": 30, "Feline leukemia vaccine": 30,
    "Core vaccine series": 80, "Spay surgery": 350, "Neuter surgery": 250,
    "Radiograph series (3+ views)": 250, "Single radiograph view": 95,
    "Ultrasound abdomen complete": 350, "Ultrasound liver": 180,
    "General anesthesia": 200, "Anesthesia monitoring": 75,
    "IV catheter placement": 45, "Venipuncture": 20,
    "Chemotherapy": 500, "Chemotherapy CHOP protocol": 800,
    "Canine heartworm test": 45, "Feline immunodeficiency virus test": 40,
    "Hospitalization daily rate": 120, "Nursing care": 60,
    "TPLO surgery": 3500, "Total hip replacement": 4500,
    "Amputation": 2000, "Splenectomy": 2500, "Enucleation": 1200,
    "Echocardiogram complete": 450, "MRI brain scan": 2200,
    "Feeding tube placement": 600, "Insulin therapy": 80,
    "Radioiodine therapy": 1800, "Anal gland expression": 30,
    "Ear cytology and flush": 85, "Ear cytology": 45,
    "Fecal parasite panel": 55, "Giardia test": 35,
    "Urinalysis": 40, "Cystocentesis": 25, "Blood pressure measurement": 35,
    "Surgical wound closure": 180, "Suture placement": 60,
    "Laceration repair": 250, "Wound debridement": 80, "Skin biopsy": 180,
    "Hip dysplasia radiograph (OFA)": 200, "Egg binding treatment": 300,
    "Rabbit dental spur filing": 180, "Aquatic antibiotic injection": 120,
    "Gastropexy": 800, "Pacemaker implantation": 4000, "Weight check": 0,
    "Pericardiectomy": 3000, "Renal transplant": 8000,
    "Canine distemper vaccine": 35, "Blood transfusion (canine blood)": 400,
    "Feline panleukopenia vaccine": 30,
}

DIAGNOSES = {
    "wellness":   ["Routine wellness", "Annual health check", "Preventive care visit"],
    "dental":     ["Periodontal disease", "Dental disease grade 2", "Tooth fracture"],
    "orthopedic": ["Hip dysplasia", "Cranial cruciate ligament rupture", "Fracture"],
    "oncology":   ["Lymphoma", "Mast cell tumor", "Osteosarcoma", "Splenic mass"],
    "cardiac":    ["Dilated cardiomyopathy", "Mitral valve disease", "Pericardial effusion"],
    "endocrine":  ["Diabetes mellitus", "Hyperthyroidism", "Hypothyroidism"],
    "emergency":  ["Trauma", "Hemoabdomen", "Gastric dilatation volvulus"],
    "renal":      ["Chronic kidney disease stage 4", "Acute kidney injury"],
    "ophthalmic": ["Glaucoma", "Cataracts", "Uveitis"],
    "gi":         ["Hepatic lipidosis", "Inflammatory bowel disease", "Anorexia (severe)"],
    "minor_visit": ["Weight recheck only", "Suture removal visit",
                    "Routine urine screening", "Nail trim visit"],
}


def pick_species_breed():
    species = random.choices(
        list(SPECIES_BREEDS.keys()),
        weights=[v["weight"] for v in SPECIES_BREEDS.values()]
    )[0]
    breed = random.choice(SPECIES_BREEDS[species]["breeds"])
    return species, breed


def random_date():
    start = datetime(2023, 1, 1)
    return (start + timedelta(days=random.randint(0, 700))).strftime("%Y-%m-%d")


def make_claim(claim_id, species, breed, diagnosis, procedures,
               fraud_type, fraud_indicator, modifier=None, billed_override=None):
    total_market = sum(PROCEDURE_RATES.get(p, 80) for p in procedures)
    billed = billed_override if billed_override else round(
        total_market * random.uniform(0.95, 1.10), 2)
    return {
        "claim_id": claim_id,
        "species": species,
        "breed": breed,
        "age": random.randint(1, 14),
        "diagnosis": diagnosis,
        "procedures": procedures,
        "billed_amount": billed,
        "average_market_rate": round(total_market, 2),
        "modifier": modifier,
        "date_of_service": random_date(),
        "fraud_indicator": fraud_indicator,
        "fraud_type": fraud_type
    }


def generate_claims():
    claims = []
    cid = 1

    def nid():
        nonlocal cid
        _id = f"VET{cid:05d}"
        cid += 1
        return _id

    # 1. LEGITIMATE (200)
    # Each scenario is constrained to species it is clinically valid for.
    # Cat-TPLO and bird/reptile cardiology/oncology are DELIBERATE edge cases:
    # rare-but-legitimate specialist care, covered by the species-exceptions KB
    # and adjudicated by the reasoning agents rather than hard rules.
    legit_scenarios = [
        {
            "procedures": ["Annual wellness exam", "Rabies vaccine", "DHPP vaccine"],
            "valid_species": ["dog"],
            "diagnoses": DIAGNOSES["wellness"],
        },
        {
            "procedures": ["Annual wellness exam", "Rabies vaccine", "Feline leukemia vaccine"],
            "valid_species": ["cat"],
            "diagnoses": DIAGNOSES["wellness"],
        },
        {
            "procedures": ["Comprehensive dental cleaning", "General anesthesia"],
            "valid_species": ["dog", "cat", "rabbit"],
            "diagnoses": DIAGNOSES["dental"],
        },
        {
            "procedures": ["Chemotherapy", "Complete blood count panel"],
            "valid_species": ["dog", "dog", "cat", "cat"],
            "diagnoses": ["Lymphoma", "Mast cell tumor"],
        },
        {
            "procedures": ["Chemotherapy", "Complete blood count panel"],
            "valid_species": ["bird", "reptile"],
            "diagnoses_by_species": {
                "bird": ["Lymphoma", "Mast cell tumor", "Splenic mass"],
                "reptile": ["Lymphoma", "Mast cell tumor", "Splenic mass"],
            },
        },
        {
            "procedures": ["Echocardiogram complete", "Blood pressure measurement"],
            "valid_species": ["dog", "dog", "cat", "cat"],
            "diagnoses": DIAGNOSES["cardiac"],
        },
        {
            "procedures": ["Echocardiogram complete", "Blood pressure measurement"],
            "valid_species": ["bird", "reptile"],
            "diagnoses_by_species": {
                "bird": [
                    "Dilated cardiomyopathy",
                    "Pericardial effusion",
                    "Mitral valve disease",
                    "Heart murmur",
                ],
                "reptile": [
                    "Dilated cardiomyopathy",
                    "Pericardial effusion",
                    "Mitral valve disease",
                    "Heart murmur",
                ],
            },
        },
        {
            "procedures": ["Insulin therapy", "Comprehensive metabolic panel"],
            "valid_species": ["dog", "cat"],
            "diagnoses": ["Diabetes mellitus"],
        },
        {
            "procedures": ["TPLO surgery", "General anesthesia", "Radiograph series (3+ views)"],
            "valid_species": ["dog", "dog", "dog", "cat"],
            "diagnoses": ["Cranial cruciate ligament rupture"],
        },
    ]
    for _ in range(200):
        scenario = random.choice(legit_scenarios)
        species = random.choice(scenario["valid_species"])
        breed = random.choice(SPECIES_BREEDS[species]["breeds"])
        diagnoses = scenario.get("diagnoses_by_species", {}).get(species, scenario.get("diagnoses", []))
        diagnosis = random.choice(diagnoses)
        claims.append(
            make_claim(
                nid(),
                species,
                breed,
                diagnosis,
                scenario["procedures"],
                None,
                False,
            )
        )

    # 2. DUPLICATE BILLING (50)
    for _ in range(50):
        species, breed = pick_species_breed()
        proc = random.choice(["Annual wellness exam", "Physical examination",
                              "Complete blood count panel", "Rabies vaccine"])
        diagnosis = random.choice(DIAGNOSES["wellness"])
        billed = round(PROCEDURE_RATES.get(proc, 65) * 2 * 1.05, 2)
        claims.append(make_claim(nid(), species, breed, diagnosis,
                                 [proc, proc], "Duplicate billing", True,
                                 billed_override=billed))

    # 3. UNBUNDLING (60)
    unbundle_pairs = [
        ("Comprehensive dental cleaning", "Tooth extraction",       "dental"),
        ("Annual wellness exam",          "Physical examination",   "wellness"),
        ("Complete blood count panel",    "White blood cell count", "wellness"),
        ("Comprehensive metabolic panel", "Liver enzyme test",      "wellness"),
        ("General anesthesia",            "Anesthesia monitoring",  "wellness"),
        ("Ultrasound abdomen complete",   "Ultrasound liver",       "wellness"),
    ]
    for i in range(60):
        species, breed = pick_species_breed()
        p1, p2, diag_key = unbundle_pairs[i % len(unbundle_pairs)]
        diagnosis = random.choice(DIAGNOSES[diag_key])
        total = PROCEDURE_RATES.get(p1, 100) + PROCEDURE_RATES.get(p2, 80)
        claims.append(make_claim(nid(), species, breed, diagnosis,
                                 [p1, p2], "Unbundling", True,
                                 billed_override=round(total * 1.05, 2)))

    # 4. UPCODING (60)
    # The observable trace of upcoding: the visit reason on the claim justifies
    # only a simple service, but a substantially more intensive service is
    # billed. (A wellness diagnosis with a wellness exam is NOT detectable —
    # the diagnosis must be narrower than the billed service.)
    upcode_map = [
        # (visit reason on claim,        billed service)
        ("Weight recheck only",          "Annual wellness exam"),
        ("Nail trim visit",              "Comprehensive dental cleaning"),
        ("Routine urine screening",      "Comprehensive metabolic panel"),
        ("Suture removal visit",         "Ultrasound abdomen complete"),
        ("Weight recheck only",          "Radiograph series (3+ views)"),
        ("Routine urine screening",      "Kidney function test"),
    ]

    for i in range(60):
        species, breed = pick_species_breed()
        diagnosis, billed_proc = upcode_map[i % len(upcode_map)]
        billed = round(PROCEDURE_RATES.get(billed_proc, 100) * 1.1, 2)
        claims.append(make_claim(nid(), species, breed, diagnosis,
                                 [billed_proc], "Upcoding", True,
                                 billed_override=billed))

    # 5. PHANTOM BILLING (60)
    # These are anatomically or practically impossible procedures on tiny exotic
    # species, but they are NOT duplicated from the species-rule KB. That keeps
    # Phantom billing distinct from Agent 1's hard Species mismatch label.
    phantom_scenarios = [
        ("fish",    "Pacemaker implantation", "Heart block"),
        ("fish",    "Renal transplant",       "End-stage renal failure"),
        ("fish",    "Pericardiectomy",        "Cardiac tamponade"),
        ("hamster", "Pacemaker implantation", "Arrhythmia"),
        ("hamster", "Renal transplant",       "End-stage renal failure"),
        ("hamster", "Radioiodine therapy",    "Thyroid nodule"),
    ]
    for i in range(60):
        sp, proc, diagnosis = phantom_scenarios[i % len(phantom_scenarios)]
        breed = random.choice(SPECIES_BREEDS[sp]["breeds"])
        billed = round(PROCEDURE_RATES.get(proc, 200) * 1.05, 2)
        claims.append(make_claim(nid(), sp, breed, diagnosis,
                                 [proc], "Phantom billing", True,
                                 billed_override=billed))

    # 6. DIAGNOSIS MISMATCH (60)
    mismatch_scenarios = [
        {
            "procedures": ["Chemotherapy CHOP protocol"],
            "diagnosis": "Routine wellness",
            "valid_species": ["dog", "cat"],
        },
        {
            "procedures": ["Amputation"],
            "diagnosis": "Annual health check",
            "valid_species": ["dog", "cat"],
        },
        {
            "procedures": ["Splenectomy"],
            "diagnosis": "Preventive care visit",
            "valid_species": ["dog", "cat"],
        },
        {
            "procedures": ["Pacemaker implantation"],
            "diagnosis": "Routine wellness",
            "valid_species": ["dog"],
        },
        {
            "procedures": ["Renal transplant"],
            "diagnosis": "Annual health check",
            "valid_species": ["cat"],
        },
        {
            "procedures": ["TPLO surgery"],
            "diagnosis": "Routine wellness",
            "valid_species": ["dog"],
        },
    ]
    for i in range(60):
        scenario = mismatch_scenarios[i % len(mismatch_scenarios)]
        species = random.choice(scenario["valid_species"])
        breed = random.choice(SPECIES_BREEDS[species]["breeds"])
        procs = scenario["procedures"]
        diagnosis = scenario["diagnosis"]
        billed = round(sum(PROCEDURE_RATES.get(p, 500) for p in procs) * 1.05, 2)
        claims.append(make_claim(nid(), species, breed, diagnosis,
                                 procs, "Diagnosis mismatch", True,
                                 billed_override=billed))

    # 7. SPECIES MISMATCH (50)
    species_mismatch = [
        ("dog",     "Feline leukemia vaccine",            "wellness"),
        ("dog",     "Feline immunodeficiency virus test", "wellness"),
        ("cat",     "Canine heartworm test",              "wellness"),
        ("hamster", "Total hip replacement",              "orthopedic"),
        ("fish",    "Chemotherapy CHOP protocol",         "oncology"),
        ("bird",    "TPLO surgery",                       "orthopedic"),
        ("reptile", "Blood transfusion (canine blood)",   "emergency"),
        ("rabbit",  "Canine distemper vaccine",           "wellness"),
    ]
    for i in range(50):
        sp, proc, diag_key = species_mismatch[i % len(species_mismatch)]
        breed = random.choice(SPECIES_BREEDS[sp]["breeds"])
        diagnosis = random.choice(DIAGNOSES[diag_key])
        billed = round(PROCEDURE_RATES.get(proc, 100) * 1.05, 2)
        claims.append(make_claim(nid(), sp, breed, diagnosis,
                                 [proc], "Species mismatch", True,
                                 billed_override=billed))

    # 8. VACCINE PADDING (60)
    # Species-coherent vaccines with an observable trace of padding:
    #  (a) duplicate administration of the same vaccine in one visit,
    #  (b) a vaccine series billed alongside its own component, or
    #  (c) species-inappropriate vaccine stacked on (caught by species rules).
    CANINE = ["DHPP vaccine", "Bordetella bronchiseptica vaccine (canine)"]
    FELINE = ["Feline leukemia vaccine", "Feline panleukopenia vaccine"]
    for i in range(60):
        species = random.choice(["dog", "cat"])
        breed = random.choice(SPECIES_BREEDS[species]["breeds"])
        diagnosis = random.choice(DIAGNOSES["wellness"])
        valid = CANINE if species == "dog" else FELINE
        base = ["Annual wellness exam", "Rabies vaccine"]
        mode = i % 3
        if mode == 0:      # duplicate same vaccine
            v = random.choice(valid)
            padding = [v, v]
        elif mode == 1:    # series + its own component
            padding = ["Core vaccine series", random.choice(valid)]
        else:              # cross-species vaccine stacked on
            wrong = random.choice(FELINE if species == "dog" else CANINE)
            padding = [random.choice(valid), wrong]
        procs = base + padding
        billed = round(sum(PROCEDURE_RATES.get(p, 30) for p in procs) * 1.15, 2)
        claims.append(make_claim(nid(), species, breed, diagnosis,
                                 procs, "Vaccine padding", True,
                                 billed_override=billed))

    # 9. MODIFIER ABUSE (60)
    for _ in range(60):
        species, breed = pick_species_breed()
        proc = random.choice([
            "Annual wellness exam", "Comprehensive dental cleaning",
            "Complete blood count panel", "Radiograph series (3+ views)"
        ])
        diagnosis = random.choice(DIAGNOSES["wellness"])
        billed = round(PROCEDURE_RATES.get(proc, 80) * 1.5, 2)
        claims.append(make_claim(nid(), species, breed, diagnosis,
                                 [proc], "Modifier abuse", True,
                                 modifier="emergency", billed_override=billed))

    random.shuffle(claims)
    return claims


if __name__ == "__main__":
    claims = generate_claims()
    out_path = Path(__file__).parent.parent / "data" / "raw_claims" / "claims.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(claims, f, indent=2)
    fraud = sum(1 for c in claims if c["fraud_indicator"])
    legit = len(claims) - fraud
    print(f"Generated {len(claims)} claims: {legit} legitimate, {fraud} fraudulent")
    by_type = {}
    for c in claims:
        t = c["fraud_type"] or "Legitimate"
        by_type[t] = by_type.get(t, 0) + 1
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")
