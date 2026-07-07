import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import clinical_reasoner
import generate_claims
import rule_checker


def make_claim(**overrides) -> dict:
    claim = {
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
    claim.update(overrides)
    return claim


class RuleCheckerRoutingTests(unittest.TestCase):
    def test_duplicate_vaccine_stack_routes_to_agent2(self):
        result = rule_checker.run(
            make_claim(
                claim_id="VAC-DUP",
                diagnosis="Routine wellness",
                procedures=[
                    "Annual wellness exam",
                    "Rabies vaccine",
                    "Rabies vaccine",
                ],
            )
        )

        self.assertFalse(result["fraud_detected"])
        self.assertTrue(result["pass_to_agent2"])

    def test_core_series_stack_routes_to_agent2_instead_of_unbundling(self):
        result = rule_checker.run(
            make_claim(
                claim_id="VAC-UNBUNDLE",
                diagnosis="Annual health check",
                procedures=[
                    "Annual wellness exam",
                    "Core vaccine series",
                    "DHPP vaccine",
                ],
            )
        )

        self.assertFalse(result["fraud_detected"])
        self.assertTrue(result["pass_to_agent2"])

    def test_species_mismatch_vaccine_stack_routes_to_agent2(self):
        result = rule_checker.run(
            make_claim(
                claim_id="VAC-SPECIES",
                species="dog",
                diagnosis="Preventive care visit",
                procedures=[
                    "Annual wellness exam",
                    "Rabies vaccine",
                    "Feline leukemia vaccine",
                ],
            )
        )

        self.assertFalse(result["fraud_detected"])
        self.assertTrue(result["pass_to_agent2"])


class ClinicalReasonerPatternTests(unittest.TestCase):
    def test_obvious_phantom_billing_is_detected_without_llm_client(self):
        with mock.patch.object(clinical_reasoner, "_get_client", return_value=None):
            result = clinical_reasoner.run(
                make_claim(
                    claim_id="PHANTOM-FISH-PACER",
                    species="fish",
                    breed="Goldfish",
                    diagnosis="Heart block",
                    procedures=["Pacemaker implantation"],
                    billed_amount=4200.0,
                    average_market_rate=4000.0,
                )
            )

        self.assertTrue(result["fraud_detected"])
        self.assertEqual(result["fraud_type"], "Phantom billing")
        self.assertEqual(result["decision_status"], "fraud")

    def test_obvious_upcoding_is_detected_without_llm_client(self):
        with mock.patch.object(clinical_reasoner, "_get_client", return_value=None):
            result = clinical_reasoner.run(
                make_claim(
                    claim_id="UPC-ROUTINE-URINE",
                    diagnosis="Routine urine screening",
                    procedures=["Kidney function test"],
                    billed_amount=45.0,
                    average_market_rate=45.0,
                )
            )

        self.assertTrue(result["fraud_detected"])
        self.assertEqual(result["fraud_type"], "Upcoding")
        self.assertEqual(result["decision_status"], "fraud")

    def test_obvious_vaccine_padding_is_detected_without_llm_client(self):
        with mock.patch.object(clinical_reasoner, "_get_client", return_value=None):
            result = clinical_reasoner.run(
                make_claim(
                    claim_id="VAC-PADDING",
                    diagnosis="Routine wellness",
                    procedures=[
                        "Annual wellness exam",
                        "Rabies vaccine",
                        "Rabies vaccine",
                    ],
                    billed_amount=115.0,
                    average_market_rate=115.0,
                )
            )

        self.assertTrue(result["fraud_detected"])
        self.assertEqual(result["fraud_type"], "Vaccine padding")
        self.assertEqual(result["decision_status"], "fraud")

    def test_whitelist_includes_small_animal_mitral_echo(self):
        hits = clinical_reasoner.tool_search_whitelist(
            "Echocardiogram complete",
            "Mitral valve disease",
        )

        self.assertIsInstance(hits["matches"], list)
        self.assertTrue(
            any(
                match.get("procedure") == "Echocardiogram complete"
                and match.get("diagnosis") == "Mitral valve disease"
                for match in hits["matches"]
            )
        )


class GeneratorRegressionTests(unittest.TestCase):
    @staticmethod
    def _violates_species_rule(claim: dict) -> bool:
        species = claim["species"].lower()
        procedures_lower = [proc.lower() for proc in claim["procedures"]]
        for rule in clinical_reasoner.SPECIES_RULES:
            invalid_species = [item.lower() for item in rule.get("invalid_species", [])]
            if species not in invalid_species:
                continue
            rule_proc = rule["procedure"].lower()
            if any(rule_proc in procedure for procedure in procedures_lower):
                return True
        return False

    def test_legitimate_small_animal_chemo_excludes_splenic_mass(self):
        claims = generate_claims.generate_claims()
        legitimate = [claim for claim in claims if not claim["fraud_indicator"]]

        self.assertFalse(
            any(
                claim["species"] in {"dog", "cat"}
                and "Chemotherapy" in claim["procedures"]
                and claim["diagnosis"] == "Splenic mass"
                for claim in legitimate
            )
        )

    def test_phantom_claims_avoid_species_rule_overlap(self):
        claims = generate_claims.generate_claims()
        phantom = [claim for claim in claims if claim["fraud_type"] == "Phantom billing"]

        self.assertTrue(
            any(
                claim["species"] == "fish"
                and claim["procedures"] == ["Pacemaker implantation"]
                for claim in phantom
            )
        )
        self.assertFalse(
            any(self._violates_species_rule(claim) for claim in phantom)
        )

    def test_diagnosis_mismatch_claims_avoid_species_rule_overlap(self):
        claims = generate_claims.generate_claims()
        mismatch = [claim for claim in claims if claim["fraud_type"] == "Diagnosis mismatch"]

        self.assertTrue(mismatch)
        self.assertFalse(
            any(self._violates_species_rule(claim) for claim in mismatch)
        )


if __name__ == "__main__":
    unittest.main()
