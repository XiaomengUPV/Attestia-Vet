"""
VetGuard — Flask API
Bridges the Next.js frontend to the Python agent pipeline.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import tempfile
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

import rule_checker
import clinical_reasoner
import adversarial_validator
from document_integrity_checker import run_agent_zero

app = Flask(__name__)
CORS(app)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "VetGuard API"})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json
    claim = {
        "claim_id": data.get("claim_id", "WEB-CLAIM"),
        "species": data.get("species", "dog"),
        "breed": data.get("breed", "Unknown"),
        "age": data.get("age", 5),
        "diagnosis": data.get("diagnosis", ""),
        "procedures": data.get("procedures", []),
        "billed_amount": data.get("billed_amount", 0),
        "average_market_rate": data.get("average_market_rate", 0),
        "modifier": data.get("modifier"),
        "fraud_indicator": None,
        "fraud_type": None
    }

    steps = []

    # Agent 1
    a1 = rule_checker.run(claim)
    steps.append({
        "agent": "Rule Checker",
        "agent_number": 1,
        "fraud_detected": a1["fraud_detected"],
        "fraud_type": a1.get("fraud_type"),
        "confidence": a1.get("confidence", "high"),
        "explanation": a1.get("explanation", ""),
        "rule_cited": a1.get("rule_cited")
    })

    if a1["fraud_detected"]:
        return jsonify({
            "fraud_detected": True,
            "fraud_type": a1["fraud_type"],
            "confidence": "high",
            "decision_status": "fraud",
            "deciding_agent": "Rule Checker",
            "explanation": a1["explanation"],
            "steps": steps
        })

    # Agent 2
    a2 = clinical_reasoner.run(claim)
    steps.append({
        "agent": "Clinical Reasoner",
        "agent_number": 2,
        "fraud_detected": a2["fraud_detected"],
        "fraud_type": a2.get("fraud_type"),
        "confidence": a2.get("confidence", "low"),
        "decision_status": a2.get("decision_status"),
        "explanation": a2.get("explanation", ""),
        "clinical_flags": a2.get("clinical_flags", []),
        "error": a2.get("error")
    })

    if a2["fraud_detected"] is None:
        return jsonify({
            "fraud_detected": None,
            "fraud_type": None,
            "confidence": a2.get("confidence", "low"),
            "decision_status": "indeterminate",
            "deciding_agent": "Clinical Reasoner",
            "explanation": a2.get("explanation", "Manual review required."),
            "steps": steps
        })

    if a2["fraud_detected"] is False:
        return jsonify({
            "fraud_detected": False,
            "fraud_type": None,
            "confidence": "high",
            "decision_status": "clean",
            "deciding_agent": "Clinical Reasoner",
            "explanation": "No fraud detected after clinical analysis.",
            "steps": steps
        })

    # Agent 3
    a3 = adversarial_validator.run(claim, a2)
    steps.append({
        "agent": "Adversarial Validator",
        "agent_number": 3,
        "fraud_detected": a3["final_fraud_detected"],
        "override_applied": a3.get("override_applied", False),
        "whitelist_entry_cited": a3.get("whitelist_entry_cited"),
        "decision_status": a3.get("decision_status"),
        "explanation": a3.get("validator_explanation", ""),
        "error": a3.get("error")
    })

    if a3["final_fraud_detected"] is None:
        return jsonify({
            "fraud_detected": None,
            "fraud_type": None,
            "confidence": a2.get("confidence", "low"),
            "decision_status": "indeterminate",
            "deciding_agent": "Adversarial Validator",
            "override_applied": False,
            "explanation": a3.get("validator_explanation", "Manual review required."),
            "steps": steps
        })

    return jsonify({
        "fraud_detected": a3["final_fraud_detected"],
        "fraud_type": a2["fraud_type"] if a3["final_fraud_detected"] else None,
        "confidence": a2["confidence"],
        "decision_status": "fraud" if a3["final_fraud_detected"] else "clean",
        "deciding_agent": "Adversarial Validator",
        "override_applied": a3.get("override_applied", False),
        "explanation": a3.get("validator_explanation", ""),
        "steps": steps
    })


@app.route("/analyze-pdf", methods=["POST"])
def analyze_pdf():
    """
    Accepts a multipart PDF upload.
    Runs Agent 0 (document integrity) + Agents 1-3 (clinical pipeline).
    """
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file in request. Use field name 'pdf'."}), 400

    pdf_file = request.files["pdf"]
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "File must be a PDF."}), 400

    claim_id = f"PDF-{uuid.uuid4().hex[:8].upper()}"
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            pdf_file.save(tmp.name)
            tmp_path = tmp.name

        # Agent 0: Document Integrity
        agent0_result = run_agent_zero(tmp_path, verbose=False)

        response = {
            "claim_id": claim_id,
            "file_name": pdf_file.filename,
            "agent0_result": agent0_result,
            "agent1_result": None,
            "agent2_result": None,
            "agent3_result": None,
            "final_verdict": agent0_result["fraud_detected"],
            "final_fraud_type": agent0_result.get("fraud_type"),
            "deciding_agent": "document_integrity_checker" if agent0_result["fraud_detected"] else None,
            "decision_status": "fraud" if agent0_result["fraud_detected"] else "pending",
        }

        # Short-circuit on CRITICAL
        if agent0_result.get("risk_level") == "CRITICAL":
            return jsonify(response)

        # Agents 1-3: Clinical pipeline
        claim_stub = {
            "claim_id": claim_id,
            "species": "unknown",
            "breed": None,
            "diagnosis": "See attached document",
            "procedures": ["See attached document"],
            "billed_amount": None,
            "average_market_rate": None,
            "modifier": None,
            "fraud_indicator": False,
            "fraud_type": None,
        }

        steps = []

        a1 = rule_checker.run(claim_stub)
        steps.append(a1)
        response["agent1_result"] = a1

        if not a1["fraud_detected"]:
            a2 = clinical_reasoner.run(claim_stub)
            steps.append(a2)
            response["agent2_result"] = a2

            if a2["fraud_detected"] is None:
                response["final_verdict"] = None
                response["final_fraud_type"] = None
                response["deciding_agent"] = "clinical_reasoner"
                response["decision_status"] = "indeterminate"
            elif a2["fraud_detected"]:
                a3 = adversarial_validator.run(claim_stub, a2)
                steps.append(a3)
                response["agent3_result"] = a3

                if a3["final_fraud_detected"] is None:
                    response["final_verdict"] = None
                    response["final_fraud_type"] = None
                    response["deciding_agent"] = "adversarial_validator"
                    response["decision_status"] = "indeterminate"
                elif a3["final_fraud_detected"]:
                    response["final_verdict"] = True
                    response["final_fraud_type"] = a2.get("fraud_type")
                    response["deciding_agent"] = "adversarial_validator"
                    response["decision_status"] = "fraud"
                else:
                    response["final_verdict"] = False
                    response["final_fraud_type"] = None
                    response["deciding_agent"] = "adversarial_validator"
                    response["decision_status"] = "clean"
            else:
                if not response["final_verdict"]:
                    response["deciding_agent"] = "clinical_reasoner"
                    response["decision_status"] = "clean"
        else:
            response["final_verdict"] = True
            response["final_fraud_type"] = a1.get("fraud_type")
            response["deciding_agent"] = "rule_checker"
            response["decision_status"] = "fraud"

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e), "claim_id": claim_id}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _extract_field(pdf_path: str, field: str):
    """
    Placeholder for real PDF text extraction.
    Swap this out later with pdfplumber to parse real claim fields.
    """
    return None


if __name__ == "__main__":
    app.run(port=8000, debug=True)
