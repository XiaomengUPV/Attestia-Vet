"""
VetGuard — Evaluation
Computes precision, recall, F1 per fraud type and overall.
Run after fraud_engine.py has processed the full dataset.
"""

import json
from pathlib import Path
from collections import defaultdict


def compute_metrics(results: list) -> dict:
    """
    Compute per-fraud-type and overall metrics.
    Returns a structured metrics dict.
    """
    fraud_types = [
        "Duplicate billing", "Unbundling", "Upcoding", "Phantom billing",
        "Diagnosis mismatch", "Species mismatch", "Vaccine padding", "Modifier abuse"
    ]

    # Per-type counters
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    tn_overall = 0

    for r in results:
        gt_fraud = r["ground_truth_fraud"]
        gt_type = r["ground_truth_type"]
        pred_fraud = r["final_verdict"]
        pred_type = r["final_fraud_type"]

        if not gt_fraud and not pred_fraud:
            tn_overall += 1
            continue

        if not gt_fraud and pred_fraud:
            # False positive — counts against whichever type was predicted
            if pred_type:
                fp[pred_type] += 1
            continue

        if gt_fraud and not pred_fraud:
            # False negative
            if gt_type:
                fn[gt_type] += 1
            continue

        if gt_fraud and pred_fraud:
            if gt_type == pred_type:
                tp[gt_type] += 1
            else:
                fn[gt_type] += 1
                fp[pred_type] += 1

    metrics = {}
    for ft in fraud_types:
        t = tp[ft]
        f_pos = fp[ft]
        f_neg = fn[ft]
        precision = t / (t + f_pos) if (t + f_pos) > 0 else 0.0
        recall = t / (t + f_neg) if (t + f_neg) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics[ft] = {
            "tp": t, "fp": f_pos, "fn": f_neg,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3)
        }

    # Overall binary metrics (fraud vs legitimate)
    total_tp = sum(1 for r in results if r["ground_truth_fraud"] and r["final_verdict"])
    total_fp = sum(1 for r in results if not r["ground_truth_fraud"] and r["final_verdict"])
    total_fn = sum(1 for r in results if r["ground_truth_fraud"] and not r["final_verdict"])
    total_tn = sum(1 for r in results if not r["ground_truth_fraud"] and not r["final_verdict"])

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = (2 * overall_precision * overall_recall /
                  (overall_precision + overall_recall)
                  if (overall_precision + overall_recall) > 0 else 0.0)

    metrics["_overall"] = {
        "tp": total_tp, "fp": total_fp, "fn": total_fn, "tn": total_tn,
        "precision": round(overall_precision, 3),
        "recall": round(overall_recall, 3),
        "f1": round(overall_f1, 3),
        "accuracy": round((total_tp + total_tn) / len(results), 3) if results else 0.0
    }

    # Agent attribution stats
    agent_counts = defaultdict(int)
    for r in results:
        agent_counts[r.get("deciding_agent", "unknown")] += 1
    metrics["_agent_attribution"] = dict(agent_counts)

    return metrics


def print_report(metrics: dict):
    print("\n" + "="*65)
    print("VetGuard — Evaluation Report")
    print("="*65)

    overall = metrics.get("_overall", {})
    print(f"\nOverall Performance:")
    print(f"  F1:        {overall.get('f1', 0):.3f}")
    print(f"  Precision: {overall.get('precision', 0):.3f}")
    print(f"  Recall:    {overall.get('recall', 0):.3f}")
    print(f"  Accuracy:  {overall.get('accuracy', 0):.3f}")
    print(f"  TP:{overall.get('tp',0)}  FP:{overall.get('fp',0)}  "
          f"FN:{overall.get('fn',0)}  TN:{overall.get('tn',0)}")

    print(f"\nPer-Fraud-Type Breakdown:")
    print(f"{'Fraud Type':<28} {'F1':>6} {'Prec':>6} {'Rec':>6} {'TP':>4} {'FP':>4} {'FN':>4}")
    print("-"*65)
    fraud_types = [k for k in metrics if not k.startswith("_")]
    for ft in sorted(fraud_types, key=lambda x: metrics[x]["f1"], reverse=True):
        m = metrics[ft]
        print(f"{ft:<28} {m['f1']:>6.3f} {m['precision']:>6.3f} {m['recall']:>6.3f} "
              f"{m['tp']:>4} {m['fp']:>4} {m['fn']:>4}")

    print(f"\nAgent Attribution:")
    for agent, count in metrics.get("_agent_attribution", {}).items():
        print(f"  {agent}: {count} claims decided")
    print("="*65)


if __name__ == "__main__":
    results_path = Path(__file__).parent.parent / "data" / "final_results" / "results.json"
    if not results_path.exists():
        print("No results file found. Run the full batch via fraud_engine.py first.")
        import sys
        sys.exit(1)

    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)

    metrics = compute_metrics(results)
    print_report(metrics)

    metrics_path = Path(__file__).parent.parent / "data" / "final_results" / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics saved to {metrics_path}")
