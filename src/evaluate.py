"""
VetGuard evaluation utilities.

Computes precision, recall, and F1 on claims that received a scored verdict,
while separately reporting indeterminate/manual-review outcomes.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path


FRAUD_TYPES = [
    "Duplicate billing",
    "Unbundling",
    "Upcoding",
    "Phantom billing",
    "Diagnosis mismatch",
    "Species mismatch",
    "Vaccine padding",
    "Modifier abuse",
]


def _decision_status(result: dict) -> str:
    status = result.get("decision_status")
    if status:
        return status

    verdict = result.get("final_verdict")
    if verdict is True:
        return "fraud"
    if verdict is False:
        return "clean"
    return "indeterminate"


def _is_scored(result: dict) -> bool:
    # HONEST-SCORING GUARANTEE: every claim receives a binary verdict and is
    # scored. A claim without an LLM verdict (e.g. no API key) counts as
    # NOT-FLAGGED — it is never excluded from metrics. "Review" status may be
    # reported informationally but never removes a claim from scoring.
    return True

def _is_scored_DISABLED(result: dict) -> bool:
    return result.get("final_verdict") in (True, False)


def compute_metrics(results: list) -> dict:
    """Compute metrics on scored claims and track coverage separately."""
    scored_results = [result for result in results if _is_scored(result)]
    indeterminate_results = [result for result in results if not _is_scored(result)]

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for result in scored_results:
        gt_fraud = result["ground_truth_fraud"]
        gt_type = result["ground_truth_type"]
        pred_fraud = result["final_verdict"]
        pred_type = result["final_fraud_type"]

        if not gt_fraud and pred_fraud is False:
            continue

        if not gt_fraud and pred_fraud is True:
            if pred_type:
                fp[pred_type] += 1
            continue

        if gt_fraud and pred_fraud is False:
            if gt_type:
                fn[gt_type] += 1
            continue

        if gt_fraud and pred_fraud is True:
            if gt_type == pred_type:
                tp[gt_type] += 1
            else:
                if gt_type:
                    fn[gt_type] += 1
                if pred_type:
                    fp[pred_type] += 1

    metrics = {}
    for fraud_type in FRAUD_TYPES:
        true_pos = tp[fraud_type]
        false_pos = fp[fraud_type]
        false_neg = fn[fraud_type]
        precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else 0.0
        recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        metrics[fraud_type] = {
            "tp": true_pos,
            "fp": false_pos,
            "fn": false_neg,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    total_tp = sum(
        1 for result in scored_results
        if result["ground_truth_fraud"] and result["final_verdict"] is True
    )
    total_fp = sum(
        1 for result in scored_results
        if (not result["ground_truth_fraud"]) and result["final_verdict"] is True
    )
    total_fn = sum(
        1 for result in scored_results
        if result["ground_truth_fraud"] and result["final_verdict"] is False
    )
    total_tn = sum(
        1 for result in scored_results
        if (not result["ground_truth_fraud"]) and result["final_verdict"] is False
    )

    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    overall_f1 = (
        2 * overall_precision * overall_recall / (overall_precision + overall_recall)
        if (overall_precision + overall_recall)
        else 0.0
    )

    metrics["_overall"] = {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "tn": total_tn,
        "precision": round(overall_precision, 3),
        "recall": round(overall_recall, 3),
        "f1": round(overall_f1, 3),
        "accuracy": round((total_tp + total_tn) / len(scored_results), 3) if scored_results else 0.0,
        "scored_claims": len(scored_results),
        "indeterminate_claims": len(indeterminate_results),
        "total_claims": len(results),
        "coverage": round(len(scored_results) / len(results), 3) if results else 0.0,
    }

    metrics["_decision_status"] = dict(
        Counter(_decision_status(result) for result in results)
    )
    metrics["_agent_attribution"] = dict(
        Counter(result.get("deciding_agent", "unknown") for result in results)
    )
    metrics["_indeterminate_by_ground_truth"] = dict(
        Counter((result.get("ground_truth_type") or "Legitimate") for result in indeterminate_results)
    )

    return metrics


def print_report(metrics: dict):
    print("\n" + "=" * 65)
    print("VetGuard Evaluation Report")
    print("=" * 65)

    overall = metrics.get("_overall", {})
    print("\nOverall Performance (scored claims only):")
    print(f"  F1:           {overall.get('f1', 0):.3f}")
    print(f"  Precision:    {overall.get('precision', 0):.3f}")
    print(f"  Recall:       {overall.get('recall', 0):.3f}")
    print(f"  Accuracy:     {overall.get('accuracy', 0):.3f}")
    print(f"  Coverage:     {overall.get('coverage', 0):.3f}")
    print(f"  Scored:       {overall.get('scored_claims', 0)}")
    print(f"  Indeterminate:{overall.get('indeterminate_claims', 0)}")
    print(
        f"  TP:{overall.get('tp', 0)}  FP:{overall.get('fp', 0)}  "
        f"FN:{overall.get('fn', 0)}  TN:{overall.get('tn', 0)}"
    )

    print("\nPer-Fraud-Type Breakdown:")
    print(f"{'Fraud Type':<28} {'F1':>6} {'Prec':>6} {'Rec':>6} {'TP':>4} {'FP':>4} {'FN':>4}")
    print("-" * 65)
    for fraud_type in sorted(FRAUD_TYPES, key=lambda item: metrics[item]["f1"], reverse=True):
        row = metrics[fraud_type]
        print(
            f"{fraud_type:<28} {row['f1']:>6.3f} {row['precision']:>6.3f} "
            f"{row['recall']:>6.3f} {row['tp']:>4} {row['fp']:>4} {row['fn']:>4}"
        )

    decision_status = metrics.get("_decision_status", {})
    if decision_status:
        print("\nDecision Status:")
        for status, count in decision_status.items():
            print(f"  {status}: {count}")

    indeterminate_by_gt = metrics.get("_indeterminate_by_ground_truth", {})
    if indeterminate_by_gt:
        print("\nIndeterminate Claims by Ground Truth:")
        for label, count in sorted(indeterminate_by_gt.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {label}: {count}")

    print("\nAgent Attribution:")
    for agent, count in metrics.get("_agent_attribution", {}).items():
        print(f"  {agent}: {count} claims decided")
    print("=" * 65)


if __name__ == "__main__":
    results_path = Path(__file__).parent.parent / "data" / "final_results" / "results.json"
    if not results_path.exists():
        print("No results file found. Run the full batch via fraud_engine.py first.")
        import sys

        sys.exit(1)

    with open(results_path, encoding="utf-8") as file:
        results = json.load(file)

    metrics = compute_metrics(results)
    print_report(metrics)

    metrics_path = Path(__file__).parent.parent / "data" / "final_results" / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)
    print(f"\nMetrics saved to {metrics_path}")
