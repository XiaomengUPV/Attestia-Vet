"""
Run full batch evaluation on all 600 claims
"""

import json
import sys
import time
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import fraud_engine

def main():
    # Load all claims
    claims_path = Path("data/raw_claims/claims.json")
    
    if not claims_path.exists():
        print("❌ claims.json not found. Run: python src/generate_claims.py first")
        return
    
    with open(claims_path, "r", encoding="utf-8") as f:
        all_claims = json.load(f)
    
    print(f"📊 Processing {len(all_claims)} claims...")
    print(f"⏱️  Estimated time: 5-10 minutes")
    print(f"💰 Estimated cost: ~$1.20 (Claude Haiku)")
    print("-" * 50)
    
    start_time = time.time()
    
    # Process all claims using the batch function
    results = fraud_engine.run_batch(all_claims, verbose=True)
    
    elapsed = time.time() - start_time
    
    # Save results
    out_path = Path("data/final_results/results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print("-" * 50)
    print(f"✅ Complete! Time: {elapsed/60:.1f} minutes")
    print(f"📁 Results saved to {out_path}")
    
    # Count decisions by agent
    agent_counts = Counter(r.get("deciding_agent", "unknown") for r in results)
    print("\n📊 Agent attribution:")
    for agent, count in agent_counts.items():
        pct = count / len(results) * 100
        print(f"  {agent}: {count} claims ({pct:.1f}%)")
    
    # Count fraud vs legitimate vs indeterminate
    fraud_count = sum(1 for r in results if r.get("final_verdict") is True)
    legit_count = sum(1 for r in results if r.get("final_verdict") is False)
    indeterminate_count = sum(1 for r in results if r.get("final_verdict") is None)
    print(f"\n  Fraud detected: {fraud_count}")
    print(f"  Legitimate: {legit_count}")
    print(f"  Indeterminate: {indeterminate_count}")

if __name__ == "__main__":
    main()
