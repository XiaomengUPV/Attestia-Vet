"""
VetGuard — Pipeline Runner
Runs the complete pipeline: generate → process → evaluate.
Usage:
  python run_pipeline.py --generate     # Generate claims dataset
  python run_pipeline.py --sample N     # Run N claims (default 20, for testing)
  python run_pipeline.py --full         # Run all 600 claims
  python run_pipeline.py --fast         # Use Haiku (cheaper, less accurate)
  python run_pipeline.py --sonnet       # Use Sonnet (default, better accuracy)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import generate_claims
import fraud_engine_langgraph as fraud_engine
import evaluate as evaluator

DATA_DIR = Path(__file__).parent / "data"
CLAIMS_PATH = DATA_DIR / "raw_claims" / "claims.json"
RESULTS_PATH = DATA_DIR / "final_results" / "results.json"

# Model options
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_HAIKU = "claude-haiku-4-5-20251001"


def main():
    parser = argparse.ArgumentParser(description="VetGuard Pipeline Runner")
    parser.add_argument("--generate", action="store_true", help="Generate synthetic claims")
    parser.add_argument("--sample", type=int, default=0, help="Run N sample claims")
    parser.add_argument("--full", action="store_true", help="Run full 600-claim batch")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate existing results")
    parser.add_argument("--fast", action="store_true", help="Use Haiku (faster, cheaper, less accurate)")
    parser.add_argument("--sonnet", action="store_true", help="Use Sonnet (default, better accuracy)")
    args = parser.parse_args()

    # Determine model
    if args.fast:
        model = MODEL_HAIKU
        use_fast = True
        print(f"Using Haiku model (fast/cheap mode)")
    else:
        model = MODEL_SONNET
        use_fast = False
        print(f"Using Sonnet model (high accuracy mode)")

    if args.generate or not CLAIMS_PATH.exists():
        print("Generating synthetic claims dataset...")
        claims = generate_claims.generate_claims()
        CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CLAIMS_PATH, "w") as f:
            json.dump(claims, f, indent=2)
        fraud = sum(1 for c in claims if c["fraud_indicator"])
        print(f"Generated {len(claims)} claims: {len(claims)-fraud} legitimate, {fraud} fraudulent\n")

    if args.sample > 0 or args.full:
        with open(CLAIMS_PATH) as f:
            all_claims = json.load(f)

        if args.sample:
            claims_to_run = all_claims[:args.sample]
            print(f"Running {args.sample} sample claims...")
        else:
            claims_to_run = all_claims
            print(f"Running full batch of {len(all_claims)} claims...")
            if args.fast:
                print("Estimated cost: ~$0.30-$0.50 with Haiku")
            else:
                print("Estimated cost: ~$1.00-$2.00 with Sonnet (higher accuracy)")
        print()

        results = fraud_engine.run_batch(claims_to_run, model=model, verbose=True)
        
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {RESULTS_PATH}")

        # Auto-evaluate after run
        metrics = evaluator.compute_metrics(results)
        evaluator.print_report(metrics)

    elif args.evaluate:
        if not RESULTS_PATH.exists():
            print("No results found. Run --sample or --full first.")
            sys.exit(1)
        with open(RESULTS_PATH) as f:
            results = json.load(f)
        metrics = evaluator.compute_metrics(results)
        evaluator.print_report(metrics)


if __name__ == "__main__":
    main()