# debug_vaccine_direct.py
import sys
sys.path.insert(0, 'src')

import clinical_reasoner
import json

# Load a specific claim
with open('data/raw_claims/claims.json', 'r', encoding='utf-8') as f:
    claims = json.load(f)

# Find VET00571
for claim in claims:
    if claim['claim_id'] == 'VET00571':
        print(f"Claim: {claim['claim_id']}")
        print(f"Procedures: {claim['procedures']}")
        
        # Call the vaccine padding function directly
        result = clinical_reasoner.check_vaccine_padding(claim['procedures'])
        print(f"\nDirect check_vaccine_padding result: {result}")
        
        # Call the full run
        full_result = clinical_reasoner.run(claim)
        print(f"Full run result: fraud={full_result['fraud_detected']}, type={full_result['fraud_type']}")
        break