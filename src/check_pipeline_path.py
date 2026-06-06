# check_pipeline_path.py
import sys
import clinical_reasoner
import inspect

print("clinical_reasoner.py location:", inspect.getfile(clinical_reasoner))
print("\nTesting the loaded module:")
test_claim = {
    "claim_id": "TEST",
    "species": "cat",
    "procedures": ["Canine heartworm test"],
    "diagnosis": "Wellness",
    "age": 3
}
result = clinical_reasoner.run(test_claim)
print(f"Result: {result['fraud_type'] if result['fraud_detected'] else 'Clean'}")