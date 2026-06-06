# debug_metabolic.py
import json

with open('data/final_results/results.json') as f:
    results = json.load(f)

# Find VET00345 and VET00330
for r in results:
    if r['claim_id'] in ['VET00345', 'VET00330']:
        print(f"{r['claim_id']}:")
        print(f"  Ground truth: {r.get('ground_truth_type')}")
        print(f"  Final verdict: {r['final_verdict']}")
        print(f"  Final type: {r['final_fraud_type']}")
        print(f"  Deciding agent: {r.get('deciding_agent')}")
        a2 = r.get('agent2_result')
        if a2:
            print(f"  Agent2 fraud detected: {a2.get('fraud_detected')}")
            print(f"  Agent2 fraud type: {a2.get('fraud_type')}")
            print(f"  Agent2 explanation: {a2.get('explanation')}")
        print()