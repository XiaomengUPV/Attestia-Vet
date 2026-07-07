import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import adversarial_validator


def make_claim(claim_id: str, species: str, diagnosis: str, procedure: str) -> dict:
    return {
        "claim_id": claim_id,
        "species": species,
        "breed": "Test Breed",
        "diagnosis": diagnosis,
        "procedures": [procedure],
    }


class AdversarialValidatorWhitelistTests(unittest.TestCase):
    def test_bird_echocardiogram_uses_shared_species_exception(self):
        claim = make_claim(
            "BIRD-ECHO",
            "bird",
            "Heart murmur",
            "Echocardiogram complete",
        )

        entries = adversarial_validator.find_relevant_whitelist_entries(claim)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["procedure"], "Echocardiogram complete")
        self.assertIn("bird", entries[0]["species"])
        self.assertIn("reptile", entries[0]["species"])
        self.assertIn("heart murmur", entries[0]["diagnosis_context"])

    def test_reptile_chemotherapy_uses_shared_species_exception(self):
        claim = make_claim(
            "REPTILE-CHEMO",
            "reptile",
            "Splenic mass",
            "Chemotherapy",
        )

        entries = adversarial_validator.find_relevant_whitelist_entries(claim)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["procedure"], "Chemotherapy")
        self.assertIn("bird", entries[0]["species"])
        self.assertIn("reptile", entries[0]["species"])
        self.assertIn("splenic mass", entries[0]["diagnosis_context"])

    def test_species_exception_requires_matching_diagnosis_context(self):
        claim = make_claim(
            "BIRD-WELLNESS",
            "bird",
            "Routine wellness",
            "Echocardiogram complete",
        )

        entries = adversarial_validator.find_relevant_whitelist_entries(claim)

        self.assertEqual(entries, [])

    def test_context_formats_species_exception_diagnosis_context(self):
        claim = make_claim(
            "BIRD-ECHO",
            "bird",
            "Heart murmur",
            "Echocardiogram complete",
        )

        context = adversarial_validator.build_whitelist_context(claim)

        self.assertIn("Echocardiogram complete on bird, reptile", context)
        self.assertIn("heart murmur", context.lower())

    def test_run_auto_overrides_when_species_exception_exactly_matches(self):
        claim = make_claim(
            "REPTILE-ECHO",
            "reptile",
            "Mitral valve disease",
            "Echocardiogram complete",
        )
        agent2_result = {
            "fraud_detected": True,
            "fraud_type": "Phantom billing",
            "confidence": "high",
            "explanation": "Echocardiography is not feasible on reptiles.",
        }

        result = adversarial_validator.run(claim, agent2_result)

        self.assertTrue(result["override_applied"])
        self.assertFalse(result["final_fraud_detected"])
        self.assertEqual(result["decision_status"], "clean")
        self.assertIn("Echocardiogram complete on bird, reptile", result["whitelist_entry_cited"])


if __name__ == "__main__":
    unittest.main()
