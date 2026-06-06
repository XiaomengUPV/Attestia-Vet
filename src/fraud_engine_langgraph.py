"""
VetGuard — LangGraph Fraud Detection Agent
Replaces fraud_engine.py with LangGraph StateGraph for better state management.
"""

from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator
import json
import asyncio
from datetime import datetime
from pathlib import Path

# Import existing agents
import rule_checker
import clinical_reasoner
import adversarial_validator


# ============================================================
# State Definition
# ============================================================

class VetGuardState(TypedDict):
    """State maintained throughout the fraud detection graph."""
    
    # Input claim
    claim: Dict[str, Any]
    
    # Agent results
    agent1_result: Dict[str, Any]
    agent2_result: Dict[str, Any]
    agent3_result: Dict[str, Any]
    
    # Decision tracking
    current_agent: str
    fraud_detected: bool
    fraud_type: str
    deciding_agent: str
    
    # Audit trail (accumulates over steps)
    audit_trail: Annotated[List[Dict], operator.add]
    
    # Error handling
    errors: List[str]
    retry_count: int


# ============================================================
# Agent Nodes (Synchronous versions for simplicity)
# ============================================================

def rule_checker_node(state: VetGuardState) -> dict:
    """Node 1: Run deterministic rule checks."""
    claim = state["claim"]
    
    try:
        result = rule_checker.run(claim)
        
        return {
            "agent1_result": result,
            "current_agent": "rule_checker",
            "audit_trail": [{
                "agent": "rule_checker",
                "timestamp": datetime.now().isoformat(),
                "fraud_detected": result["fraud_detected"],
                "fraud_type": result.get("fraud_type"),
                "explanation": result.get("explanation")
            }]
        }
    except Exception as e:
        return {
            "errors": [f"Rule checker failed: {str(e)}"],
            "retry_count": state.get("retry_count", 0) + 1
        }


def clinical_reasoner_node(state: VetGuardState) -> dict:
    """Node 2: Run clinical LLM reasoning."""
    claim = state["claim"]
    
    try:
        result = clinical_reasoner.run(claim)
        
        return {
            "agent2_result": result,
            "current_agent": "clinical_reasoner",
            "audit_trail": [{
                "agent": "clinical_reasoner",
                "timestamp": datetime.now().isoformat(),
                "fraud_detected": result["fraud_detected"],
                "fraud_type": result.get("fraud_type"),
                "confidence": result.get("confidence"),
                "explanation": result.get("explanation")
            }]
        }
    except Exception as e:
        return {
            "errors": [f"Clinical reasoner failed: {str(e)}"],
            "retry_count": state.get("retry_count", 0) + 1
        }


def adversarial_validator_node(state: VetGuardState) -> dict:
    """Node 3: Challenge the fraud verdict."""
    claim = state["claim"]
    agent2_result = state["agent2_result"]
    
    try:
        result = adversarial_validator.run(claim, agent2_result)
        
        return {
            "agent3_result": result,
            "current_agent": "adversarial_validator",
            "audit_trail": [{
                "agent": "adversarial_validator",
                "timestamp": datetime.now().isoformat(),
                "override_applied": result.get("override_applied"),
                "final_fraud_detected": result.get("final_fraud_detected"),
                "explanation": result.get("validator_explanation")
            }]
        }
    except Exception as e:
        return {
            "errors": [f"Adversarial validator failed: {str(e)}"],
            "retry_count": state.get("retry_count", 0) + 1
        }


def finalize_node(state: VetGuardState) -> dict:
    """Final node: Aggregate results into final verdict."""

    # Agent 3 ran — use its verdict
    if state.get("agent3_result"):
        final = state["agent3_result"].get("final_fraud_detected", False)
        return {
            "fraud_detected": final,
            "fraud_type": state["agent2_result"].get("fraud_type") if final else None,
            "deciding_agent": "adversarial_validator"
        }

    # Agent 2 ran — use its verdict
    if state.get("agent2_result") and state["agent2_result"].get("fraud_detected") is not None:
        final = state["agent2_result"].get("fraud_detected", False)
        return {
            "fraud_detected": final,
            "fraud_type": state["agent2_result"].get("fraud_type") if final else None,
            "deciding_agent": "clinical_reasoner"
        }

    # Agent 1 only — use its verdict
    final = state.get("agent1_result", {}).get("fraud_detected", False)
    return {
        "fraud_detected": final,
        "fraud_type": state.get("agent1_result", {}).get("fraud_type") if final else None,
        "deciding_agent": "rule_checker"
    }

# ============================================================
# Router Functions
# ============================================================

def after_rule_checker(state: VetGuardState) -> str:
    """Decide next step after rule checker."""
    if state.get("errors"):
        return "finalize"
    if state.get("agent1_result", {}).get("fraud_detected"):
        return "finalize"
    return "clinical_reasoner"


def after_clinical_reasoner(state: VetGuardState) -> str:
    """Decide next step after clinical reasoner."""
    if state.get("errors"):
        return "finalize"
    if not state.get("agent2_result", {}).get("fraud_detected"):
        return "finalize"
    if state.get("agent2_result", {}).get("confidence") == "low":
        return "finalize"
    return "adversarial_validator"


def after_adversarial_validator(state: VetGuardState) -> str:
    """Always go to finalize after adversarial validator."""
    return "finalize"


# ============================================================
# Build the Graph
# ============================================================

def build_fraud_detection_graph():
    """Build the LangGraph state graph for fraud detection."""
    
    # Initialize graph with state schema
    builder = StateGraph(VetGuardState)
    
    # Add nodes
    builder.add_node("rule_checker", rule_checker_node)
    builder.add_node("clinical_reasoner", clinical_reasoner_node)
    builder.add_node("adversarial_validator", adversarial_validator_node)
    builder.add_node("finalize", finalize_node)
    
    # Set entry point
    builder.set_entry_point("rule_checker")

    # Add conditional edges from rule_checker
    builder.add_conditional_edges(
        "rule_checker",
        after_rule_checker,
        {
            "clinical_reasoner": "clinical_reasoner",
            "finalize": "finalize"
        }
    )

    # Add conditional edges from clinical_reasoner
    builder.add_conditional_edges(
        "clinical_reasoner",
        after_clinical_reasoner,
        {
            "adversarial_validator": "adversarial_validator",
            "finalize": "finalize"
        }
    )

    # Add conditional edges from adversarial_validator
    builder.add_conditional_edges(
        "adversarial_validator",
        after_adversarial_validator,
        {
            "finalize": "finalize"
        }
    )

    # Add edge from finalize to end
    builder.add_edge("finalize", END)

    # Add checkpointing for resumability
    memory = MemorySaver()

    return builder.compile(checkpointer=memory)


# ============================================================
# Main Agent Class
# ============================================================

class VetGuardAgent:
    """Main interface for the VetGuard LangGraph agent."""
    
    def __init__(self):
        self.graph = build_fraud_detection_graph()
    
    def process_claim(self, claim: Dict[str, Any], thread_id: str = None) -> Dict[str, Any]:
        """
        Process a single claim through the fraud detection graph.
        
        Args:
            claim: The claim to evaluate
            thread_id: Optional thread ID for resumability
        
        Returns:
            Final result with verdict and audit trail
        """
        # Initialize state
        initial_state = {
            "claim": claim,
            "agent1_result": {},
            "agent2_result": {},
            "agent3_result": {},
            "current_agent": "",
            "fraud_detected": False,
            "fraud_type": None,
            "deciding_agent": "",
            "audit_trail": [],
            "errors": [],
            "retry_count": 0
        }
        
        # Configuration for checkpointing
        config = {"configurable": {"thread_id": thread_id or claim["claim_id"]}}
        
        # Run the graph
        final_state = self.graph.invoke(initial_state, config=config)
        
        # Build final result
        return {
            "claim_id": claim["claim_id"],
            "fraud_detected": final_state.get("fraud_detected", False),
            "fraud_type": final_state.get("fraud_type"),
            "deciding_agent": final_state.get("deciding_agent", "unknown"),
            "audit_trail": final_state.get("audit_trail", []),
            "errors": final_state.get("errors", [])
        }
    
    def get_state(self, thread_id: str) -> Dict[str, Any]:
        """Get the current state for a given thread (for resumability)."""
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.get_state(config)
    
    def resume_claim(self, thread_id: str) -> Dict[str, Any]:
        """Resume a previously interrupted claim processing."""
        config = {"configurable": {"thread_id": thread_id}}
        final_state = self.graph.invoke(None, config=config)
        
        return {
            "fraud_detected": final_state.get("fraud_detected", False),
            "fraud_type": final_state.get("fraud_type"),
            "deciding_agent": final_state.get("deciding_agent", "unknown"),
            "audit_trail": final_state.get("audit_trail", [])
        }


# ============================================================
# Batch Processing
# ============================================================

def process_batch(claims: List[Dict[str, Any]], verbose: bool = True) -> List[Dict[str, Any]]:
    """Process a batch of claims."""
    agent = VetGuardAgent()
    results = []
    
    for i, claim in enumerate(claims):
        if verbose and i % 50 == 0:
            print(f"Processing claim {i+1}/{len(claims)}...")
        
        result = agent.process_claim(claim)
        results.append(result)
    
    return results

def run_batch(claims: list, model: str = "claude-haiku-4-5-20251001",
              verbose: bool = True) -> list:
    """Alias for process_batch — compatible with run_pipeline.py."""
    agent = VetGuardAgent()
    results = []
    total = len(claims)

    for i, claim in enumerate(claims):
        if verbose and i % 50 == 0:
            print(f"Processing {i+1}/{total}...")
        raw = agent.process_claim(claim)
        results.append({
            "claim_id": claim["claim_id"],
            "species": claim["species"],
            "breed": claim.get("breed"),
            "diagnosis": claim["diagnosis"],
            "procedures": claim["procedures"],
            "billed_amount": claim.get("billed_amount"),
            "average_market_rate": claim.get("average_market_rate"),
            "ground_truth_fraud": claim.get("fraud_indicator"),
            "ground_truth_type": claim.get("fraud_type"),
            "agent1_result": raw.get("audit_trail", [{}])[0] if raw.get("audit_trail") else None,
            "agent2_result": raw.get("audit_trail", [{}, {}])[1] if len(raw.get("audit_trail", [])) > 1 else None,
            "agent3_result": raw.get("audit_trail", [{}, {}, {}])[2] if len(raw.get("audit_trail", [])) > 2 else None,
            "final_verdict": raw.get("fraud_detected", False),
            "final_fraud_type": raw.get("fraud_type"),
            "deciding_agent": raw.get("deciding_agent"),
            "processing_time_ms": None
        })

    return results

# ============================================================
# Testing
# ============================================================

if __name__ == "__main__":
    # Load a test claim
    claims_path = Path(__file__).parent.parent / "data" / "raw_claims" / "claims.json"
    
    if not claims_path.exists():
        print("No claims found. Run generate_claims.py first.")
        exit(1)
    
    with open(claims_path, 'r', encoding='utf-8') as f:
        claims = json.load(f)
    
    test_claim = claims[0]
    print(f"Testing claim: {test_claim['claim_id']}")
    print(f"Species: {test_claim['species']}")
    print(f"Diagnosis: {test_claim['diagnosis']}")
    print(f"Procedures: {test_claim['procedures']}")
    print()
    
    agent = VetGuardAgent()
    result = agent.process_claim(test_claim)
    
    print(f"\n{'='*60}")
    print("RESULT:")
    print(f"{'='*60}")
    print(f"Fraud detected: {result['fraud_detected']}")
    print(f"Fraud type: {result['fraud_type']}")
    print(f"Deciding agent: {result['deciding_agent']}")
    print(f"\nAudit Trail:")
    for step in result['audit_trail']:
        print(f"  {step['agent']}: fraud={step.get('fraud_detected', step.get('final_fraud_detected', False))}")