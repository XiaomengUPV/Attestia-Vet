import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import clinical_reasoner
import evaluate
import fraud_engine_langgraph
import generate_claims


def make_claim() -> dict:
    return {
        "claim_id": "TEST-CLAIM",
        "species": "dog",
        "breed": "Labrador Retriever",
        "age": 7,
        "diagnosis": "Routine wellness",
        "procedures": ["Annual wellness exam"],
        "billed_amount": 65.0,
        "average_market_rate": 65.0,
        "modifier": None,
    }


class ClinicalReasonerStatusTests(unittest.TestCase):
    def test_missing_client_returns_indeterminate(self):
        with mock.patch.object(clinical_reasoner, "_get_client", return_value=None):
            result = clinical_reasoner.run(make_claim())

        self.assertIsNone(result["fraud_detected"])
        self.assertEqual(result["decision_status"], "indeterminate")
        self.assertIn("manual review", result["explanation"].lower())


class LangGraphFinalizeTests(unittest.TestCase):
    def test_finalize_preserves_indeterminate_agent2(self):
        state = {
            "agent1_result": {"fraud_detected": False},
            "agent2_result": {
                "fraud_detected": None,
                "decision_status": "indeterminate",
                "error": "low balance",
            },
            "agent3_result": {},
            "current_agent": "clinical_reasoner",
            "errors": [],
        }

        final = fraud_engine_langgraph.finalize_node(state)

        self.assertIsNone(final["fraud_detected"])
        self.assertEqual(final["decision_status"], "indeterminate")
        self.assertIn("low balance", final["errors"])


class EvaluationCoverageTests(unittest.TestCase):
    def test_metrics_skip_indeterminate_claims_and_report_coverage(self):
        results = [
            {
                "ground_truth_fraud": True,
                "ground_truth_type": "Upcoding",
                "final_verdict": True,
                "final_fraud_type": "Upcoding",
                "deciding_agent": "clinical_reasoner",
                "decision_status": "fraud",
            },
            {
                "ground_truth_fraud": False,
                "ground_truth_type": None,
                "final_verdict": False,
                "final_fraud_type": None,
                "deciding_agent": "clinical_reasoner",
                "decision_status": "clean",
            },
            {
                "ground_truth_fraud": True,
                "ground_truth_type": "Phantom billing",
                "final_verdict": None,
                "final_fraud_type": None,
                "deciding_agent": "clinical_reasoner",
                "decision_status": "indeterminate",
            },
        ]

        metrics = evaluate.compute_metrics(results)

        self.assertEqual(metrics["_overall"]["scored_claims"], 2)
        self.assertEqual(metrics["_overall"]["indeterminate_claims"], 1)
        self.assertEqual(metrics["_overall"]["coverage"], 0.667)
        self.assertEqual(metrics["_overall"]["recall"], 1.0)
        self.assertEqual(metrics["_indeterminate_by_ground_truth"]["Phantom billing"], 1)


class LegitimateGeneratorTests(unittest.TestCase):
    def test_legitimate_claims_keep_endocrine_and_tplo_labels_coherent(self):
        claims = generate_claims.generate_claims()
        legitimate = [claim for claim in claims if not claim["fraud_indicator"]]

        insulin_claims = [
            claim for claim in legitimate if "Insulin therapy" in claim["procedures"]
        ]
        self.assertTrue(insulin_claims)
        self.assertTrue(
            all(claim["diagnosis"] == "Diabetes mellitus" for claim in insulin_claims)
        )

        tplo_claims = [
            claim for claim in legitimate if "TPLO surgery" in claim["procedures"]
        ]
        self.assertTrue(tplo_claims)
        self.assertTrue(
            all(
                claim["diagnosis"] == "Cranial cruciate ligament rupture"
                for claim in tplo_claims
            )
        )


if __name__ == "__main__":
    unittest.main()
