"""
VetGuard — Streamlit Dashboard
Three pages: Live Demo, Performance, Audit Log
Run: streamlit run src/app.py
"""

import json
import sys
import time
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import rule_checker
import clinical_reasoner
import adversarial_validator
import fraud_engine
import evaluate as evaluator

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_PATH = DATA_DIR / "final_results" / "results.json"
CLAIMS_PATH = DATA_DIR / "raw_claims" / "claims.json"

st.set_page_config(page_title="VetGuard", page_icon="🐾", layout="wide")

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/color/96/dog.png", width=60)
st.sidebar.title("VetGuard")
st.sidebar.caption("Veterinary Billing Fraud Detection")
page = st.sidebar.radio("Navigate", ["🔍 Live Demo", "📊 Performance", "📋 Audit Log"])
model_choice = st.sidebar.selectbox("Model", ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
                                     index=0)
st.sidebar.markdown("---")
st.sidebar.caption("3-agent system: Rule Checker → Clinical Reasoner → Adversarial Validator")

CONFIDENCE_COLORS = {"high": "🔴", "medium": "🟡", "low": "🟢"}
FRAUD_COLORS = {
    "Duplicate billing": "#FF6B6B",
    "Unbundling": "#FF8E53",
    "Upcoding": "#FFA500",
    "Phantom billing": "#9B59B6",
    "Diagnosis mismatch": "#E74C3C",
    "Species mismatch": "#8E44AD",
    "Vaccine padding": "#F39C12",
    "Modifier abuse": "#D35400",
    "Legitimate": "#27AE60"
}

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — LIVE DEMO
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Live Demo":
    st.title("🐾 VetGuard — Live Claim Analysis")
    st.caption("Submit a veterinary claim and watch all three agents evaluate it in real time.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Claim Input")
        species = st.selectbox("Species", ["dog", "cat", "rabbit", "bird", "hamster", "fish", "reptile"])
        breed = st.text_input("Breed", value="Labrador Retriever")
        age = st.number_input("Age (years)", 0, 25, 4)
        diagnosis = st.text_input("Diagnosis", value="Routine wellness")
        procedures_raw = st.text_area("Procedures (one per line)",
                                       value="Annual wellness exam\nPhysical examination")
        billed = st.number_input("Billed Amount ($)", 0.0, 20000.0, 120.0, step=10.0)
        market = st.number_input("Market Rate ($)", 0.0, 20000.0, 65.0, step=10.0)
        modifier = st.selectbox("Modifier", [None, "emergency", "urgent", "routine", "complex"])

        # Quick-load fraud examples
        st.markdown("**Quick-load examples:**")
        ex_col1, ex_col2, ex_col3 = st.columns(3)
        examples = {
            "Species mismatch": {
                "species": "dog", "breed": "Golden Retriever", "age": 3,
                "diagnosis": "Routine wellness",
                "procedures": "Feline leukemia vaccine",
                "billed": 31.50, "market": 30.0, "modifier": None
            },
            "Diagnosis mismatch": {
                "species": "cat", "breed": "Domestic Shorthair", "age": 8,
                "diagnosis": "Routine wellness",
                "procedures": "Chemotherapy CHOP protocol",
                "billed": 840.0, "market": 800.0, "modifier": None
            },
            "Legitimate (Lymphoma)": {
                "species": "dog", "breed": "Boxer", "age": 7,
                "diagnosis": "Lymphoma",
                "procedures": "Chemotherapy",
                "billed": 525.0, "market": 500.0, "modifier": None
            }
        }
        for label, ex in examples.items():
            if st.button(label, use_container_width=True):
                st.session_state["example"] = ex

        if "example" in st.session_state:
            ex = st.session_state["example"]
            st.info(f"Loaded: {label} — click Analyze to run")

    with col2:
        st.subheader("Agent Results")
        if st.button("🔍 Analyze Claim", type="primary", use_container_width=True):
            ex = st.session_state.get("example", {})
            claim = {
                "claim_id": f"LIVE-{int(time.time())}",
                "species": ex.get("species", species),
                "breed": ex.get("breed", breed),
                "age": ex.get("age", age),
                "diagnosis": ex.get("diagnosis", diagnosis),
                "procedures": [p.strip() for p in
                               ex.get("procedures", procedures_raw).split("\n") if p.strip()],
                "billed_amount": ex.get("billed", billed),
                "average_market_rate": ex.get("market", market),
                "modifier": ex.get("modifier", modifier),
                "fraud_indicator": None,
                "fraud_type": None
            }

            # ── Agent 1 ──
            with st.expander("🔧 Agent 1 — Rule Checker", expanded=True):
                with st.spinner("Running deterministic checks..."):
                    t0 = time.time()
                    a1 = rule_checker.run(claim)
                    ms1 = round((time.time() - t0) * 1000, 1)

                if a1["fraud_detected"]:
                    st.error(f"🚨 **{a1['fraud_type']}** detected ({ms1}ms)")
                    st.write(a1["explanation"])
                    if a1.get("rule_cited"):
                        st.caption(f"Rule: {a1['rule_cited']}")
                else:
                    st.success(f"✅ No rule violations ({ms1}ms) — passing to Agent 2")

            if a1["fraud_detected"]:
                st.error(f"### 🚨 Final Verdict: **{a1['fraud_type']}**")
                st.caption("Decided by: Rule Checker (deterministic)")
                st.stop()

            # ── Agent 2 ──
            with st.expander("🧠 Agent 2 — Clinical Reasoner", expanded=True):
                with st.spinner("Consulting Claude for clinical assessment..."):
                    t0 = time.time()
                    a2 = clinical_reasoner.run(claim, model=model_choice)
                    ms2 = round((time.time() - t0) * 1000, 1)

                conf_icon = CONFIDENCE_COLORS.get(a2["confidence"], "⚪")
                if a2["fraud_detected"]:
                    st.warning(f"{conf_icon} **{a2['fraud_type']}** suspected "
                               f"(confidence: {a2['confidence']}, {ms2}ms)")
                    st.write(a2["explanation"])
                    if a2.get("clinical_flags"):
                        st.caption("Flags: " + " · ".join(a2["clinical_flags"]))
                else:
                    st.success(f"✅ Clinically appropriate ({ms2}ms)")

                with st.expander("Raw Claude response"):
                    st.code(a2.get("raw_response", ""), language="json")

            if not a2["fraud_detected"]:
                st.success("### ✅ Final Verdict: **Legitimate claim**")
                st.caption("Decided by: Clinical Reasoner")
                st.stop()

            # ── Agent 3 ──
            with st.expander("⚖️ Agent 3 — Adversarial Validator", expanded=True):
                with st.spinner("Challenging the fraud verdict..."):
                    t0 = time.time()
                    a3 = adversarial_validator.run(claim, a2, model=model_choice)
                    ms3 = round((time.time() - t0) * 1000, 1)

                if a3["override_applied"]:
                    st.success(f"✅ Override applied ({ms3}ms)")
                    st.write(f"**Whitelist entry:** {a3['whitelist_entry_cited']}")
                    st.write(a3["override_rationale"])
                else:
                    st.error(f"🚨 Fraud verdict upheld ({ms3}ms)")
                    st.write(a3["validator_explanation"])

                with st.expander("Raw Claude response"):
                    st.code(a3.get("raw_response", ""), language="json")

            # ── Final verdict ──
            if a3["final_fraud_detected"]:
                st.error(f"### 🚨 Final Verdict: **{a2['fraud_type']}**")
            else:
                st.success("### ✅ Final Verdict: **Legitimate claim** (override applied)")
            st.caption("Decided by: Adversarial Validator")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Performance":
    st.title("📊 Performance Metrics")

    if not RESULTS_PATH.exists():
        st.warning("No results found. Run the pipeline first: `python run_pipeline.py --sample 50`")
        st.stop()

    with open(RESULTS_PATH) as f:
        results = json.load(f)

    metrics = evaluator.compute_metrics(results)
    overall = metrics["_overall"]

    # Overall KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall F1", f"{overall['f1']:.3f}")
    c2.metric("Precision", f"{overall['precision']:.3f}")
    c3.metric("Recall", f"{overall['recall']:.3f}")
    c4.metric("Claims Evaluated", len(results))

    st.markdown("---")

    # Per-type breakdown
    st.subheader("Per-Fraud-Type F1 Scores")
    fraud_types = [k for k in metrics if not k.startswith("_")]
    chart_data = {
        "Fraud Type": fraud_types,
        "F1": [metrics[ft]["f1"] for ft in fraud_types],
        "Precision": [metrics[ft]["precision"] for ft in fraud_types],
        "Recall": [metrics[ft]["recall"] for ft in fraud_types],
    }

    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        colors = [FRAUD_COLORS.get(ft, "#888888") for ft in fraud_types]
        fig.add_trace(go.Bar(
            x=chart_data["F1"], y=chart_data["Fraud Type"],
            orientation='h', marker_color=colors,
            text=[f"{v:.3f}" for v in chart_data["F1"]],
            textposition='outside'
        ))
        fig.update_layout(xaxis_range=[0, 1.1], height=400,
                          xaxis_title="F1 Score", yaxis_title="",
                          margin=dict(l=0, r=40, t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart({ft: metrics[ft]["f1"] for ft in fraud_types})

    # Detailed table
    st.subheader("Detailed Breakdown")
    table_rows = []
    for ft in sorted(fraud_types, key=lambda x: metrics[x]["f1"], reverse=True):
        m = metrics[ft]
        table_rows.append({
            "Fraud Type": ft,
            "F1": m["f1"], "Precision": m["precision"], "Recall": m["recall"],
            "TP": m["tp"], "FP": m["fp"], "FN": m["fn"]
        })
    st.dataframe(table_rows, use_container_width=True)

    # Agent attribution
    st.subheader("Agent Attribution")
    attr = metrics.get("_agent_attribution", {})
    attr_col1, attr_col2, attr_col3 = st.columns(3)
    attr_col1.metric("Rule Checker decisions", attr.get("rule_checker", 0))
    attr_col2.metric("Clinical Reasoner decisions", attr.get("clinical_reasoner", 0))
    attr_col3.metric("Adversarial Validator decisions", attr.get("adversarial_validator", 0))

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Audit Log":
    st.title("📋 Audit Log")

    if not RESULTS_PATH.exists():
        st.warning("No results found. Run the pipeline first.")
        st.stop()

    with open(RESULTS_PATH) as f:
        results = json.load(f)

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_verdict = st.selectbox("Verdict", ["All", "Fraud", "Legitimate"])
    with col2:
        filter_agent = st.selectbox("Deciding Agent",
                                     ["All", "rule_checker", "clinical_reasoner", "adversarial_validator"])
    with col3:
        filter_correct = st.selectbox("Correctness", ["All", "Correct", "Incorrect"])

    filtered = results
    if filter_verdict == "Fraud":
        filtered = [r for r in filtered if r["final_verdict"]]
    elif filter_verdict == "Legitimate":
        filtered = [r for r in filtered if not r["final_verdict"]]

    if filter_agent != "All":
        filtered = [r for r in filtered if r.get("deciding_agent") == filter_agent]

    if filter_correct == "Correct":
        filtered = [r for r in filtered if r["final_verdict"] == r["ground_truth_fraud"]]
    elif filter_correct == "Incorrect":
        filtered = [r for r in filtered if r["final_verdict"] != r["ground_truth_fraud"]]

    st.caption(f"Showing {len(filtered)} of {len(results)} claims")

    for r in filtered[:50]:  # Show max 50
        correct = r["final_verdict"] == r["ground_truth_fraud"]
        icon = "✅" if correct else "❌"
        verdict_label = r["final_fraud_type"] or "Legitimate"
        gt_label = r["ground_truth_type"] or "Legitimate"

        with st.expander(
            f"{icon} {r['claim_id']} | {r['species']} | "
            f"Predicted: {verdict_label} | GT: {gt_label} | "
            f"Agent: {r.get('deciding_agent', 'unknown')}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Claim**")
                st.write(f"Species: {r['species']} ({r.get('breed', '')})")
                st.write(f"Diagnosis: {r['diagnosis']}")
                st.write(f"Procedures: {', '.join(r.get('procedures', []))}")
                st.write(f"Billed: ${r.get('billed_amount', 0):.2f} "
                         f"(market: ${r.get('average_market_rate', 0):.2f})")

            with col2:
                st.markdown("**Agent Decisions**")
                a1 = r.get("agent1_result", {})
                if a1:
                    st.write(f"Agent 1: {'🚨 ' + a1['fraud_type'] if a1['fraud_detected'] else '✅ Clean'}")
                a2 = r.get("agent2_result", {})
                if a2:
                    st.write(f"Agent 2: {'🚨 ' + str(a2.get('fraud_type')) if a2.get('fraud_detected') else '✅ Clean'} "
                             f"({a2.get('confidence', '')})")
                a3 = r.get("agent3_result", {})
                if a3:
                    override = "⚖️ Override applied" if a3.get("override_applied") else "🚨 Upheld"
                    st.write(f"Agent 3: {override}")

            if r.get("agent2_result", {}).get("explanation"):
                st.caption(f"Clinical note: {r['agent2_result']['explanation']}")
            if r.get("agent3_result", {}).get("whitelist_entry_cited"):
                st.caption(f"Whitelist: {r['agent3_result']['whitelist_entry_cited']}")
