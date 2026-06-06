# test_on_real_data.py
import sys
import importlib

# Force remove any cached version
if 'src.clinical_reasoner' in sys.modules:
    del sys.modules['src.clinical_reasoner']
if 'clinical_reasoner' in sys.modules:
    del sys.modules['clinical_reasoner']

sys.path.insert(0, 'src')

import clinical_reasoner
import importlib
importlib.reload(clinical_reasoner)  # Force reload

import json

# Load claims
with open('data/raw_claims/claims.json', 'r', encoding='utf-8') as f:
    claims = json.load(f)

# Test vaccine padding
vp_claims = [c for c in claims if c.get('fraud_type') == 'Vaccine padding']
print(f"Testing on {len(vp_claims)} vaccine padding claims...")

detected = 0
for claim in vp_claims[:10]:
    result = clinical_reasoner.run(claim)
    if result["fraud_detected"] and result["fraud_type"] == "Vaccine padding":
        detected += 1
    else:
        print(f"  MISSED: {claim['claim_id']} - {claim['procedures']}")
        print(f"    Result: {result['fraud_type'] if result['fraud_detected'] else 'Clean'}")

print(f"\nDetected {detected}/10 vaccine padding claims")

# Test species mismatch
sm_claims = [c for c in claims if c.get('fraud_type') == 'Species mismatch']
print(f"\nTesting on {len(sm_claims)} species mismatch claims...")

detected = 0
for claim in sm_claims[:10]:
    result = clinical_reasoner.run(claim)
    if result["fraud_detected"] and result["fraud_type"] == "Species mismatch":
        detected += 1
    else:
        print(f"  MISSED: {claim['claim_id']} - {claim['species']}: {claim['procedures'][0]}")
        print(f"    Result: {result['fraud_type'] if result['fraud_detected'] else 'Clean'}")

print(f"\nDetected {detected}/10 species mismatch claims")