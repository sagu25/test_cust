import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "eval_results.db")

st.set_page_config(
    page_title="RAG Evaluation Dashboard",
    page_icon="🧠",
    layout="wide",
)

# ── helpers ──────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_evaluations() -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = get_conn()
    rows = conn.execute("""
        SELECT e.id, e.run_id, e.question, e.faithfulness, e.relevancy,
               e.completeness, e.rouge_l, e.overall_score,
               e.faithfulness_reason, e.relevancy_reason, e.completeness_reason,
               e.factual_anchor_score, e.factual_hallucinated,
               e.golden_rouge_l, e.contradicts_golden, e.contradiction_detail,
               tr.answer, tr.retrieved_context, e.timestamp
        FROM evaluations e
        JOIN test_runs tr ON e.run_id = tr.id
        ORDER BY e.timestamp ASC
    """).fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def load_golden_answers() -> dict:
    if not os.path.exists(DB_PATH):
        return {}
    conn = get_conn()
    rows = conn.execute("SELECT question, golden_answer FROM golden_answers").fetchall()
    conn.close()
    return {r["question"]: r["golden_answer"] for r in rows}


def load_consistency() -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM consistency_reports ORDER BY consistency_score ASC"
    ).fetchall()
    conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def load_generated_questions() -> list:
    if not os.path.exists(DB_PATH):
        return []
    conn = get_conn()
    rows = conn.execute("SELECT question, category FROM generated_questions").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def score_color(score):
    if score is None:
        return "gray"
    if score >= 0.80:
        return "green"
    if score >= 0.60:
        return "orange"
    return "red"


def score_badge(score):
    if score is None:
        return "⚪ N/A"
    if score >= 0.80:
        return f"🟢 {score:.2f}"
    if score >= 0.60:
        return f"🟡 {score:.2f}"
    return f"🔴 {score:.2f}"


# ── document management helpers ───────────────────────────────────────────────

def _extract_text(uploaded_file) -> str:
    if uploaded_file.name.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(uploaded_file.read()))
            pages  = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(p for p in pages if p.strip())
        except Exception as e:
            st.error(f"PDF extraction error: {e}")
            return ""
    return uploaded_file.read().decode("utf-8", errors="ignore")


def _reset_questions():
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM generated_questions")
    conn.execute("DELETE FROM golden_answers")
    try:
        conn.execute("DELETE FROM eval_cache")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/brain.png", width=60)
    st.title("RAG Eval System")
    st.caption(f"Provider: **{os.getenv('LLM_PROVIDER','groq').upper()}**")
    st.caption(f"RAG App: `{os.getenv('RAG_APP_URL','http://localhost:8000')}`")
    st.divider()

    refresh = st.button("🔄 Refresh Now", use_container_width=True)
    auto_refresh = st.toggle("Auto-refresh (30s)", value=True)
    st.divider()

    qs = load_generated_questions()
    if qs:
        st.markdown(f"**Generated Questions ({len(qs)})**")
        for i, q in enumerate(qs):
            st.caption(f"{i+1}. {q['question'][:55]}...")

    st.divider()

    # ── Document Management ───────────────────────────────────────────────────
    st.markdown("### Document Management")

    try:
        from rag_app.document_store import (
            get_all_documents, get_uploaded_documents,
            add_document, remove_document,
        )
        from rag_app import retriever as _retriever

        all_docs      = get_all_documents()
        uploaded_docs = get_uploaded_documents()
        uploaded_titles = {d["title"] for d in uploaded_docs}

        st.caption(f"{len(all_docs)} document(s) in knowledge base")
        for doc in all_docs:
            icon = "📄" if doc["title"] in uploaded_titles else "🔒"
            st.caption(f"{icon} {doc['title']} ({len(doc['content']):,} chars)")

        st.divider()

        # ── Upload ────────────────────────────────────────────────────────────
        st.markdown("**Upload New Document**")
        upload_file = st.file_uploader(
            "TXT or PDF", type=["txt", "pdf"], key="doc_upload",
            label_visibility="collapsed",
        )
        doc_title = st.text_input(
            "Document title", placeholder="e.g. Payroll Policy", key="doc_title"
        )

        add_disabled = not (upload_file and doc_title and doc_title.strip())
        if st.button("Add to Knowledge Base", type="primary",
                     disabled=add_disabled, use_container_width=True):
            text = _extract_text(upload_file)
            if text.strip():
                add_document(doc_title.strip(), text, upload_file.name)
                _reset_questions()
                _retriever.reload()
                st.success(
                    f"Added **{doc_title}**. Questions will regenerate on "
                    f"the next orchestrator cycle."
                )
                st.rerun()
            else:
                st.error("Could not extract text — check the file format.")

        # ── Remove ────────────────────────────────────────────────────────────
        if uploaded_docs:
            st.divider()
            st.markdown("**Remove Uploaded Document**")
            remove_title = st.selectbox(
                "Select document", [d["title"] for d in uploaded_docs],
                key="remove_select", label_visibility="collapsed",
            )
            if st.button("Remove Document", type="secondary",
                         use_container_width=True):
                remove_document(remove_title)
                _reset_questions()
                _retriever.reload()
                st.warning(
                    f"Removed **{remove_title}**. Questions will regenerate "
                    f"on the next orchestrator cycle."
                )
                st.rerun()

        # ── Manual reset ──────────────────────────────────────────────────────
        st.divider()
        if st.button("Reset All Questions", use_container_width=True):
            _reset_questions()
            st.success("Questions cleared — will regenerate on next cycle.")

    except Exception as _doc_err:
        st.caption(f"Document management unavailable: {_doc_err}")

if auto_refresh:
    st.markdown(
        '<meta http-equiv="refresh" content="30">',
        unsafe_allow_html=True,
    )

# ── load data ─────────────────────────────────────────────────────────────────

df = load_evaluations()
cons_df = load_consistency()
golden_map = load_golden_answers()

# ── header ────────────────────────────────────────────────────────────────────

st.markdown("## 🧠 RAG Evaluation Dashboard")
st.caption(f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
st.divider()

if df.empty:
    st.info("⏳ No evaluation data yet. Start the orchestrator and wait for the first cycle to complete.")
    st.code("python orchestrator.py", language="bash")
    st.stop()

# ── top metrics ───────────────────────────────────────────────────────────────

total_runs   = len(df)
unique_qs    = df["question"].nunique()
avg_overall  = df["overall_score"].mean()
avg_faith    = df["faithfulness"].mean()
avg_relev    = df["relevancy"].mean()
avg_compl    = df["completeness"].mean()
avg_rouge    = df["rouge_l"].mean()
avg_factual  = df["factual_anchor_score"].mean() if "factual_anchor_score" in df.columns and df["factual_anchor_score"].notna().any() else None
avg_golden_r = df["golden_rouge_l"].mean() if "golden_rouge_l" in df.columns and df["golden_rouge_l"].notna().any() else None
flagged_cnt  = int(cons_df["flagged"].sum()) if not cons_df.empty else 0
contradicts_cnt = int(df["contradicts_golden"].sum()) if "contradicts_golden" in df.columns else 0

st.markdown("#### Layer 1 & 2 — Grounded (Zero LLM)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Factual Anchor Score", f"{avg_factual:.2f}" if avg_factual is not None else "N/A",
          help="Pure code: facts in answer vs source context")
c2.metric("Golden ROUGE-L",       f"{avg_golden_r:.2f}" if avg_golden_r is not None else "N/A",
          help="Math: text overlap with golden reference answer")
c3.metric("Contradicts Golden",   contradicts_cnt,
          help="Runs where answer contradicts the ground truth")
c4.metric("⚠ Inconsistent Qs",   flagged_cnt)

st.markdown("#### Layer 3 — LLM Judge (Grounded by Golden Answer)")
c5, c6, c7, c8, c9 = st.columns(5)
c5.metric("Overall Score",  f"{avg_overall:.2f}")
c6.metric("Faithfulness",   f"{avg_faith:.2f}")
c7.metric("Relevancy",      f"{avg_relev:.2f}")
c8.metric("Completeness",   f"{avg_compl:.2f}")
c9.metric("Total Runs",     total_runs)

st.divider()

# ── score trend chart ─────────────────────────────────────────────────────────

st.markdown("### 📈 Score Trend Across All Runs")

fig = go.Figure()
fig.add_trace(go.Scatter(y=df["overall_score"],    name="Overall",             line=dict(color="#6366f1", width=3)))
if "factual_anchor_score" in df.columns:
    fig.add_trace(go.Scatter(y=df["factual_anchor_score"], name="Factual Anchors (L1)", line=dict(color="#dc2626", width=2)))
if "golden_rouge_l" in df.columns:
    fig.add_trace(go.Scatter(y=df["golden_rouge_l"],       name="Golden ROUGE-L (L2)", line=dict(color="#7c3aed", width=2)))
fig.add_trace(go.Scatter(y=df["faithfulness"],     name="Faithfulness (L3)",   line=dict(color="#22c55e", width=2)))
fig.add_trace(go.Scatter(y=df["relevancy"],        name="Relevancy (L3)",      line=dict(color="#f59e0b", width=2)))
fig.add_trace(go.Scatter(y=df["completeness"],     name="Completeness (L3)",   line=dict(color="#3b82f6", width=2)))
fig.add_hline(y=0.75, line_dash="dash", line_color="red", annotation_text="Threshold (0.75)")
fig.update_layout(
    height=320,
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    yaxis=dict(range=[0, 1.05]),
    xaxis_title="Run #",
    yaxis_title="Score",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── consistency alerts ────────────────────────────────────────────────────────

if not cons_df.empty:
    flagged = cons_df[cons_df["flagged"] == 1]
    if not flagged.empty:
        st.markdown("### ⚠ Consistency Alerts")
        for _, row in flagged.iterrows():
            with st.expander(f"🔴 {row['question'][:90]}... — Consistency: {row['consistency_score']:.2f}", expanded=False):
                col1, col2, col3 = st.columns(3)
                col1.metric("Consistency Score", f"{row['consistency_score']:.2f}")
                col2.metric("Contradiction Rate", f"{row['contradiction_rate']*100:.0f}%")
                col3.metric("Drift Score", f"{row['drift_score']:.2f}")

                details = row.get("contradiction_details", "[]")
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except Exception:
                        details = []
                if details:
                    st.markdown("**Contradictions detected:**")
                    for d in details:
                        st.error(f"Run {d.get('run_a')} vs Run {d.get('run_b')}: {d.get('detail', '')}")
        st.divider()

# ── per-question comparison ───────────────────────────────────────────────────

st.markdown("### 🔍 Per-Question Answer Comparison (All Runs)")

questions = df["question"].unique()

cons_map = {}
if not cons_df.empty:
    for _, row in cons_df.iterrows():
        cons_map[row["question"]] = row

for q in questions:
    q_df = df[df["question"] == q].reset_index(drop=True)
    cons = cons_map.get(q, {})
    cons_score = cons.get("consistency_score") if cons else None
    is_flagged = bool(cons.get("flagged", False)) if cons else False

    label = f"{'⚠ ' if is_flagged else '✅ '}{q[:85]}..."
    cons_text = f" | Consistency: {cons_score:.2f}" if cons_score is not None else ""

    with st.expander(f"{label}{cons_text} ({len(q_df)} runs)", expanded=is_flagged):

        if cons_score is not None:
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("Consistency", f"{cons_score:.2f}")
            cc2.metric("Contradiction Rate", f"{cons.get('contradiction_rate', 0)*100:.0f}%")
            cc3.metric("Drift", f"{cons.get('drift_score', 0):.2f}")
            cc4.metric("Total Runs", cons.get("total_runs", len(q_df)))

        golden = golden_map.get(q)
        if golden:
            with st.expander("📌 Golden Reference Answer (Ground Truth)", expanded=False):
                st.success(golden)
        st.markdown("---")

        for i, row in q_df.iterrows():
            run_label = f"**Run {i+1}**"
            contradicts = bool(row.get("contradicts_golden", 0))
            hallucinated = row.get("factual_hallucinated", "[]")
            try:
                hallucinated = json.loads(hallucinated) if isinstance(hallucinated, str) else hallucinated
            except Exception:
                hallucinated = []

            r1, r2, r3, r4, r5, r6, r7, r8 = st.columns([1, 3, 1, 1, 1, 1, 1, 1])

            r1.markdown(run_label)
            answer_text = row.get("answer", "")[:180]
            if contradicts:
                r2.caption(f"⚠ {answer_text}")
            else:
                r2.caption(answer_text)
            r3.markdown(score_badge(row.get("factual_anchor_score")), help=f"Hallucinated: {hallucinated[:2]}")
            r4.markdown(score_badge(row.get("golden_rouge_l")),       help="ROUGE-L vs golden answer")
            r5.markdown(score_badge(row.get("faithfulness")),         help=row.get("faithfulness_reason", ""))
            r6.markdown(score_badge(row.get("relevancy")),            help=row.get("relevancy_reason", ""))
            r7.markdown(score_badge(row.get("completeness")),         help=row.get("completeness_reason", ""))

            overall = row.get("overall_score")
            color = score_color(overall)
            bg = "#22c55e" if color == "green" else "#f59e0b" if color == "orange" else "#ef4444"
            r8.markdown(
                f'<div style="background:{bg};color:white;padding:4px 8px;'
                f'border-radius:6px;text-align:center;font-weight:700;">'
                f'{"N/A" if overall is None else f"{overall:.2f}"}</div>',
                unsafe_allow_html=True,
            )

            if contradicts:
                st.error(f"Run {i+1} contradicts golden answer: {row.get('contradiction_detail', '')}")
            if hallucinated:
                st.warning(f"Run {i+1} hallucinated facts not in source: {hallucinated}")

        st.markdown(
            "<div style='font-size:12px;color:#64748b;margin-top:4px;'>"
            "Columns: Run | Answer | 🔴Factual(L1) | 🟣GoldenROUGE(L2) | "
            "🟢Faithfulness(L3) | 🟡Relevancy(L3) | 🔵Completeness(L3) | Overall"
            "</div>",
            unsafe_allow_html=True,
        )

st.divider()

# ── radar chart ───────────────────────────────────────────────────────────────

st.markdown("### 🎯 Average Score Breakdown")

radar_r     = [avg_faith, avg_relev, avg_compl,
               avg_factual if avg_factual is not None else 0,
               avg_golden_r if avg_golden_r is not None else 0,
               avg_overall]
radar_theta = ["Faithfulness (L3)", "Relevancy (L3)", "Completeness (L3)",
               "Factual Anchors (L1)", "Golden ROUGE-L (L2)", "Overall"]

fig2 = go.Figure(go.Scatterpolar(
    r=radar_r,
    theta=radar_theta,
    fill="toself",
    line_color="#6366f1",
    fillcolor="rgba(99,102,241,0.2)",
))
fig2.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    height=350,
    margin=dict(l=40, r=40, t=20, b=20),
    paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig2, use_container_width=True)

# ── raw data table ────────────────────────────────────────────────────────────

with st.expander("📋 Raw Evaluation Data"):
    display_cols = ["run_id", "question", "faithfulness", "relevancy",
                    "completeness", "rouge_l", "overall_score", "timestamp"]
    st.dataframe(
        df[display_cols].rename(columns={
            "run_id": "Run", "question": "Question",
            "faithfulness": "Faith.", "relevancy": "Relev.",
            "completeness": "Compl.", "rouge_l": "ROUGE-L",
            "overall_score": "Overall", "timestamp": "Time"
        }),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ── metrics guide ─────────────────────────────────────────────────────────────

st.markdown("### 📖 Understanding the Metrics")
st.caption("A plain-English guide to every score shown on this dashboard.")

with st.expander("🟢 Overall Score — The Final Report Card", expanded=False):
    st.markdown("""
**What it is:** A single number (0 to 1) that combines all 5 evaluation metrics into one verdict.

**How it is calculated:**
| Metric | Weight | Why this weight |
|---|---|---|
| Factual Anchor Score | 25% | Most reliable — pure code, cannot be fooled |
| Golden ROUGE-L | 25% | Mathematical ground truth — no LLM bias |
| Faithfulness | 25% | Core RAG quality — is the answer grounded? |
| Relevancy | 15% | Important but secondary to accuracy |
| Completeness | 10% | Missing info is bad, but wrong info is worse |

**Hard rule:** If Factual Anchor Score falls below 0.30, the Overall Score is capped at 0.45 regardless of other scores. A factually wrong agent cannot be rated "Good."

**Score bands:**
- 🟢 0.80 – 1.00 : **Good** — Agent is answering correctly and completely
- 🟡 0.60 – 0.79 : **Warning** — Some issues detected, investigate flagged questions
- 🔴 0.00 – 0.59 : **Poor** — Serious problems, agent needs attention
    """)

with st.expander("🔴 Factual Anchor Score (Layer 1) — The Only Metric With No AI", expanded=False):
    st.markdown("""
**What it is:** A pure code check that extracts every number, dollar amount, percentage, and time period from the agent's answer and verifies each one exists in the source document.

**How it works (no LLM involved):**
```
Source says:  "Employees get 15 days of paid annual leave"
Agent says:   "Employees get 15 days of paid leave"   → 15 found in source ✓ Score: 1.00
Agent says:   "Employees get 30 days of paid leave"   → 30 NOT in source ✗ Score: 0.00
```

**Why it matters:** This is the only metric that cannot be fooled by a confident-sounding wrong answer. An LLM judge can be tricked; regex code cannot.

**What a low score means:** The agent stated specific facts (numbers, dates, amounts) that are not in the source documents — i.e., hallucination.

**What score 1.00 means:** Every specific fact in the answer came from the document. Note: 1.00 also appears when the answer has no specific facts to verify (e.g., "I don't know").
    """)

with st.expander("🟣 Golden ROUGE-L (Layer 2) — Math vs Ground Truth", expanded=False):
    st.markdown("""
**What it is:** A mathematical comparison between the agent's answer and a pre-generated "golden" reference answer created from the full policy document.

**How the golden answer is created:** The system sends the complete document (not just retrieved chunks) to the LLM once, generates the ideal answer, and caches it permanently as the benchmark.

**How ROUGE-L works:**
```
Golden:  "Employees receive 15 days of paid annual leave per calendar year"
Agent:   "Employees are entitled to 15 days of paid leave annually"

Longest Common Subsequence = "employees ... 15 days ... paid ... leave"
ROUGE-L = 0.67  (reasonable match — same facts, slightly different words)
```

**Why it matters:** Even if the agent gives consistently wrong answers, ROUGE-L against the golden answer will always be low. Consistency alone does not protect a wrong answer.

**What a low score means:** The agent's answer is very different from what the correct, complete answer should say — either wrong facts or missing key information.
    """)

with st.expander("🟢 Faithfulness (Layer 3) — Did the Agent Make Anything Up?", expanded=False):
    st.markdown("""
**What it is:** An LLM judge that compares the agent's answer against both the retrieved context AND the golden reference answer, checking for any invented or contradicted facts.

**What the judge checks:**
1. Does the agent's answer contradict the golden answer on any specific fact?
2. Are there claims in the answer not supported by the retrieved document chunks?
3. Is the answer overall faithful to the source material?

**Example — Faithfulness 1.00:**
> Agent says: "Failure to meet PIP targets may result in termination."
> Policy says: "Failure to meet PIP targets may result in termination."
> Verdict: Fully faithful ✓

**Example — Faithfulness 0.00:**
> Agent says: "Referrers are eligible for rewards even if hired for a different position."
> Policy: No referral policy exists in the documents.
> Verdict: Agent invented a policy ✗

**What "Contradicts Golden" flag means:** The agent's answer directly conflicts with the verified reference answer on a specific factual claim. This is the most serious finding.
    """)

with st.expander("🟡 Relevancy (Layer 3) — Did the Agent Answer the Right Question?", expanded=False):
    st.markdown("""
**What it is:** An LLM judge that checks whether the agent's answer actually addresses what was asked, using the golden answer as a reference for what a relevant answer looks like.

**Example — Relevancy 1.00:**
> Question: "What are the consequences of failing a PIP?"
> Agent: "Failure to meet PIP targets may result in termination."
> Verdict: Directly answers the question ✓

**Example — Relevancy 0.00:**
> Question: "What must hourly employees do for payroll?"
> Agent: "The policy context does not mention payroll requirements."
> Verdict: The answer does not help the user at all ✗

**What a low score means:** Two possible causes:
1. The agent said "I don't know" when it should have known (retrieval gap)
2. The agent answered a different question than what was asked

**Important distinction:** An agent can score high on Faithfulness (didn't lie) but low on Relevancy (didn't answer). Both must be high for a truly good response.
    """)

with st.expander("🔵 Completeness (Layer 3) — Did the Agent Cover Everything?", expanded=False):
    st.markdown("""
**What it is:** An LLM judge that compares the agent's answer to the golden reference answer and identifies what key details are missing.

**Example — Completeness 1.00:**
> Golden answer mentions: "Submit within 30 days. Receipts required over $25. Use expense management system."
> Agent answer covers: All three points ✓

**Example — Completeness 0.30:**
> Golden answer mentions: "Submit within 30 days. Receipts required over $25. Use expense management system."
> Agent answer covers: "Submit within 30 days." only
> Missing: Receipt requirement, submission system ✗

**What a low score means:** The agent gave a correct but incomplete answer — it answered part of the question but left out important details that a user would need.

**Why this has the lowest weight (10%):** Missing information is a problem, but providing wrong information is worse. An incomplete answer can be followed up; a wrong answer misleads the user.
    """)

with st.expander("📊 Consistency Score — Does the Agent Give the Same Answer Every Time?", expanded=False):
    st.markdown("""
**What it is:** A cross-run score that compares all answers to the same question across multiple test cycles and detects when the agent contradicts itself over time.

**How it is calculated:**
```
For every pair of answers to the same question:
  → Measure semantic similarity (0 to 1)
  → Check if they factually contradict each other (yes/no)

Consistency = avg_similarity × (1 − contradiction_rate) × (1 − drift)
```

**Three signals inside the consistency score:**
| Signal | What it measures |
|---|---|
| Consistency Score | Overall agreement across all runs |
| Contradiction Rate | % of run-pairs that factually conflict |
| Drift Score | How different the latest answer is from the first answer |

**Flagged if score < 0.75** — questions with a consistency score below 0.75 appear in the Consistency Alerts section with the specific contradiction highlighted.

**Why this matters:** An agent that gives the right answer 9 times and the wrong answer once is more dangerous than one that is consistently mediocre — because users build trust in it and the one wrong answer is unexpected.
    """)

with st.expander("📐 Score Interpretation Quick Reference", expanded=False):
    st.markdown("""
| Score | Color | Meaning | Recommended Action |
|---|---|---|---|
| 0.80 – 1.00 | 🟢 Green | Agent performing well | No action needed |
| 0.60 – 0.79 | 🟡 Yellow | Borderline — some issues | Review flagged questions |
| 0.00 – 0.59 | 🔴 Red | Serious problem | Investigate and fix immediately |

**Common patterns and what they mean:**

| Pattern | Likely cause |
|---|---|
| High Factual, Low ROUGE-L | Agent answers correctly but incompletely |
| High Faithfulness, Low Relevancy | Agent is honest but didn't answer the question |
| High all scores, Low Consistency | Agent is non-deterministic — same Q, different A |
| Low Factual (< 0.30) | Agent hallucinated specific facts — highest priority fix |
| CONTRADICTS flag | Agent's answer directly conflicts with ground truth |
| Context Precision low | Wrong document chunks being retrieved |
| Context Recall low | Right chunks exist but retrieval missed them |
    """)

st.divider()
st.caption("Dashboard auto-refreshes every 30 seconds | Evaluation powered by Groq / Azure OpenAI")
