"""
VetGuard — MCP Server
Exposes VetGuard knowledge bases and agents as MCP tools.
Compatible with any MCP client (Claude Desktop, Cursor, custom clients).
"""

import json
import sys
from pathlib import Path
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

# Add src to path for agent imports
sys.path.insert(0, str(Path(__file__).parent))

import rule_checker
import clinical_reasoner
import adversarial_validator

# Load knowledge bases once at startup
KB = Path(__file__).parent.parent / "knowledge_base"

with open(KB / "bundle_rules.json", encoding="utf-8") as f:
    BUNDLE_RULES = json.load(f)

with open(KB / "species_procedure_rules.json", encoding="utf-8") as f:
    SPECIES_RULES = json.load(f)

with open(KB / "clinical_whitelist.json", encoding="utf-8") as f:
    WHITELIST = json.load(f)

# Initialize MCP server
server = Server("vetguard")


# ── Tool 1: Check bundle rules ─────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="check_bundle_rules",
            description=(
                "Check if two veterinary procedures violate bundling rules. "
                "Returns the rule and fraud type if a violation exists."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "procedure_1": {
                        "type": "string",
                        "description": "First procedure name"
                    },
                    "procedure_2": {
                        "type": "string",
                        "description": "Second procedure name"
                    }
                },
                "required": ["procedure_1", "procedure_2"]
            }
        ),
        types.Tool(
            name="check_species_validity",
            description=(
                "Check if a procedure is valid for a given species. "
                "Returns validity status and rule if invalid."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "procedure": {
                        "type": "string",
                        "description": "Procedure name to check"
                    },
                    "species": {
                        "type": "string",
                        "description": "Animal species (dog, cat, rabbit, bird, hamster, fish, reptile)"
                    }
                },
                "required": ["procedure", "species"]
            }
        ),
        types.Tool(
            name="lookup_clinical_whitelist",
            description=(
                "Look up whether a procedure-diagnosis combination is in the "
                "clinical whitelist (i.e. legitimate despite appearing unusual). "
                "Returns the rationale and source if found."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "procedure": {
                        "type": "string",
                        "description": "Procedure name"
                    },
                    "diagnosis": {
                        "type": "string",
                        "description": "Diagnosis name"
                    }
                },
                "required": ["procedure", "diagnosis"]
            }
        ),
        types.Tool(
            name="analyze_claim",
            description=(
                "Run a complete fraud analysis on a veterinary claim using all "
                "three VetGuard agents (Rule Checker, Clinical Reasoner, "
                "Adversarial Validator). Returns fraud verdict with full audit trail."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "description": "Unique claim identifier"
                    },
                    "species": {
                        "type": "string",
                        "description": "Animal species"
                    },
                    "breed": {
                        "type": "string",
                        "description": "Animal breed"
                    },
                    "age": {
                        "type": "integer",
                        "description": "Animal age in years"
                    },
                    "diagnosis": {
                        "type": "string",
                        "description": "Clinical diagnosis"
                    },
                    "procedures": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of procedures billed"
                    },
                    "billed_amount": {
                        "type": "number",
                        "description": "Total amount billed in USD"
                    },
                    "average_market_rate": {
                        "type": "number",
                        "description": "Expected market rate for these procedures"
                    },
                    "modifier": {
                        "type": "string",
                        "description": "Billing modifier if any (e.g. emergency)",
                        "nullable": True
                    }
                },
                "required": ["claim_id", "species", "diagnosis", "procedures",
                             "billed_amount", "average_market_rate"]
            }
        ),
        types.Tool(
            name="get_knowledge_base_stats",
            description="Get statistics about the VetGuard knowledge bases.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


# ── Tool implementations ───────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # ── Tool: check_bundle_rules ──────────────────────────────────────────────
    if name == "check_bundle_rules":
        p1 = arguments["procedure_1"].lower()
        p2 = arguments["procedure_2"].lower()

        for rule in BUNDLE_RULES:
            r1 = rule["procedure_1"].lower()
            r2 = rule["procedure_2"].lower()
            if (p1 in r1 or r1 in p1) and (p2 in r2 or r2 in p2):
                result = {
                    "violation_found": True,
                    "fraud_type": rule["fraud_type"],
                    "rule": rule["rule"],
                    "procedure_1": rule["procedure_1"],
                    "procedure_2": rule["procedure_2"]
                }
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            if (p2 in r1 or r1 in p2) and (p1 in r2 or r2 in p1):
                result = {
                    "violation_found": True,
                    "fraud_type": rule["fraud_type"],
                    "rule": rule["rule"],
                    "procedure_1": rule["procedure_1"],
                    "procedure_2": rule["procedure_2"]
                }
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        return [types.TextContent(type="text", text=json.dumps({
            "violation_found": False,
            "message": f"No bundling rule violation found for '{arguments['procedure_1']}' and '{arguments['procedure_2']}'"
        }, indent=2))]

    # ── Tool: check_species_validity ──────────────────────────────────────────
    elif name == "check_species_validity":
        procedure = arguments["procedure"].lower()
        species = arguments["species"].lower()

        for rule in SPECIES_RULES:
            if rule["procedure"].lower() == procedure:
                invalid = [s.lower() for s in rule["invalid_species"]]
                valid = [s.lower() for s in rule["valid_species"]]
                if species in invalid:
                    return [types.TextContent(type="text", text=json.dumps({
                        "valid": False,
                        "procedure": rule["procedure"],
                        "species": species,
                        "rule": rule["rule"],
                        "valid_species": rule["valid_species"],
                        "invalid_species": rule["invalid_species"]
                    }, indent=2))]
                if species in valid:
                    return [types.TextContent(type="text", text=json.dumps({
                        "valid": True,
                        "procedure": rule["procedure"],
                        "species": species,
                        "message": f"'{arguments['procedure']}' is valid for {species}"
                    }, indent=2))]

        return [types.TextContent(type="text", text=json.dumps({
            "valid": True,
            "message": f"No species restriction found for '{arguments['procedure']}'"
        }, indent=2))]

    # ── Tool: lookup_clinical_whitelist ───────────────────────────────────────
    elif name == "lookup_clinical_whitelist":
        procedure = arguments["procedure"].lower()
        diagnosis = arguments["diagnosis"].lower()

        for entry in WHITELIST:
            proc_match = entry["procedure"].lower() in procedure or \
                         procedure in entry["procedure"].lower()
            diag_match = entry["diagnosis"].lower() in diagnosis or \
                         diagnosis in entry["diagnosis"].lower()
            if proc_match and diag_match:
                return [types.TextContent(type="text", text=json.dumps({
                    "found": True,
                    "procedure": entry["procedure"],
                    "diagnosis": entry["diagnosis"],
                    "rationale": entry["rationale"],
                    "source": entry["source"]
                }, indent=2))]

        return [types.TextContent(type="text", text=json.dumps({
            "found": False,
            "message": f"No whitelist entry for '{arguments['procedure']}' + '{arguments['diagnosis']}'"
        }, indent=2))]

    # ── Tool: analyze_claim ───────────────────────────────────────────────────
    elif name == "analyze_claim":
        claim = {
            "claim_id": arguments.get("claim_id", "MCP-CLAIM"),
            "species": arguments["species"],
            "breed": arguments.get("breed", "Unknown"),
            "age": arguments.get("age", 5),
            "diagnosis": arguments["diagnosis"],
            "procedures": arguments["procedures"],
            "billed_amount": arguments["billed_amount"],
            "average_market_rate": arguments["average_market_rate"],
            "modifier": arguments.get("modifier"),
            "fraud_indicator": None,
            "fraud_type": None
        }

        # Run Agent 1
        a1 = rule_checker.run(claim)

        if a1["fraud_detected"]:
            result = {
                "fraud_detected": True,
                "fraud_type": a1["fraud_type"],
                "confidence": "high",
                "decision_status": "fraud",
                "deciding_agent": "rule_checker",
                "explanation": a1["explanation"],
                "audit_trail": [{"agent": "rule_checker", "result": a1}]
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        # Run Agent 2
        a2 = clinical_reasoner.run(claim)

        if a2["fraud_detected"] is None:
            result = {
                "fraud_detected": None,
                "fraud_type": None,
                "confidence": a2.get("confidence", "low"),
                "decision_status": "indeterminate",
                "deciding_agent": "clinical_reasoner",
                "explanation": a2.get("explanation", "Manual review required."),
                "audit_trail": [
                    {"agent": "rule_checker", "result": a1},
                    {"agent": "clinical_reasoner", "result": a2}
                ]
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        if a2["fraud_detected"] is False:
            result = {
                "fraud_detected": False,
                "fraud_type": None,
                "decision_status": "clean",
                "deciding_agent": "clinical_reasoner",
                "explanation": "No fraud detected by clinical reasoning",
                "audit_trail": [
                    {"agent": "rule_checker", "result": a1},
                    {"agent": "clinical_reasoner", "result": a2}
                ]
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        # Run Agent 3
        a3 = adversarial_validator.run(claim, a2)

        if a3["final_fraud_detected"] is None:
            result = {
                "fraud_detected": None,
                "fraud_type": None,
                "confidence": a2.get("confidence", "low"),
                "decision_status": "indeterminate",
                "deciding_agent": "adversarial_validator",
                "override_applied": False,
                "whitelist_entry_cited": a3.get("whitelist_entry_cited"),
                "explanation": a3.get("validator_explanation", "Manual review required."),
                "audit_trail": [
                    {"agent": "rule_checker", "result": a1},
                    {"agent": "clinical_reasoner", "result": a2},
                    {"agent": "adversarial_validator", "result": a3}
                ]
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        result = {
            "fraud_detected": a3["final_fraud_detected"],
            "fraud_type": a2["fraud_type"] if a3["final_fraud_detected"] else None,
            "confidence": a2["confidence"],
            "decision_status": "fraud" if a3["final_fraud_detected"] else "clean",
            "deciding_agent": "adversarial_validator",
            "override_applied": a3["override_applied"],
            "whitelist_entry_cited": a3.get("whitelist_entry_cited"),
            "explanation": a3["validator_explanation"],
            "audit_trail": [
                {"agent": "rule_checker", "result": a1},
                {"agent": "clinical_reasoner", "result": a2},
                {"agent": "adversarial_validator", "result": a3}
            ]
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── Tool: get_knowledge_base_stats ────────────────────────────────────────
    elif name == "get_knowledge_base_stats":
        result = {
            "bundle_rules": len(BUNDLE_RULES),
            "species_procedure_rules": len(SPECIES_RULES),
            "clinical_whitelist_entries": len(WHITELIST),
            "total_knowledge_base_entries": len(BUNDLE_RULES) + len(SPECIES_RULES) + len(WHITELIST),
            "tools_available": [
                "check_bundle_rules",
                "check_species_validity",
                "lookup_clinical_whitelist",
                "analyze_claim",
                "get_knowledge_base_stats"
            ]
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [types.TextContent(type="text",
                                  text=json.dumps({"error": f"Unknown tool: {name}"}))]


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
