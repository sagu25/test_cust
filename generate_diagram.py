"""
Run this script to generate the system architecture diagram as a PNG image.
Usage: python generate_diagram.py
Output: system_architecture.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(20, 14))
ax.set_xlim(0, 20)
ax.set_ylim(0, 14)
ax.axis("off")
fig.patch.set_facecolor("#0f1117")
ax.set_facecolor("#0f1117")

# ── Color palette ─────────────────────────────────────────────────────────────
C_DASH    = "#1f6feb"   # Dashboard - blue
C_ORCH    = "#388bfd"   # Orchestrator - light blue
C_TEST    = "#f78166"   # Test Agent - orange/red
C_CUSTOM  = "#3fb950"   # Custom Agent - green
C_EVAL    = "#d2a8ff"   # Evaluator - purple
C_RAG     = "#56d364"   # RAG/Retriever - green tint
C_DOC     = "#e3b341"   # Document Store - yellow
C_LLM     = "#ff7b72"   # LLM - red
C_DB      = "#8b949e"   # Database - grey
C_TEXT    = "#ffffff"
C_SUB     = "#8b949e"
BG_BOX    = "#161b22"

def box(ax, x, y, w, h, color, title, subtitles=(), radius=0.3):
    rect = FancyBboxPatch((x, y), w, h,
                           boxstyle=f"round,pad=0.05,rounding_size={radius}",
                           linewidth=2, edgecolor=color,
                           facecolor=BG_BOX, zorder=3)
    ax.add_patch(rect)
    # Color bar on left
    bar = FancyBboxPatch((x, y), 0.12, h,
                          boxstyle=f"round,pad=0,rounding_size=0.1",
                          linewidth=0, edgecolor=color,
                          facecolor=color, zorder=4)
    ax.add_patch(bar)
    # Title
    ty = y + h - 0.38
    ax.text(x + 0.28, ty, title, color=color, fontsize=10,
            fontweight="bold", va="center", zorder=5)
    # Subtitles
    for i, s in enumerate(subtitles):
        ax.text(x + 0.28, ty - 0.42*(i+1), s, color=C_SUB, fontsize=7.5,
                va="center", zorder=5)

def arrow(ax, x1, y1, x2, y2, color="#555555", label="", style="->"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color,
                                lw=1.8, connectionstyle="arc3,rad=0.0"),
                zorder=6)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx+0.05, my+0.1, label, color=color, fontsize=7,
                ha="center", zorder=7,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#0f1117",
                          edgecolor="none"))

def curved_arrow(ax, x1, y1, x2, y2, color, label="", rad=0.25):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color,
                                lw=1.8, connectionstyle=f"arc3,rad={rad}"),
                zorder=6)
    if label:
        mx = (x1+x2)/2 + (0.4 if rad > 0 else -0.4)
        my = (y1+y2)/2
        ax.text(mx, my, label, color=color, fontsize=7,
                ha="center", zorder=7,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="#0f1117",
                          edgecolor="none"))

# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(10, 13.5, "RAG Evaluation System — Architecture",
        color=C_TEXT, fontsize=16, fontweight="bold",
        ha="center", va="center", zorder=5)
ax.text(10, 13.1, "3 Agents  •  1 Orchestrator  •  1 Dashboard  •  1 RAG Pipeline  •  1 Database",
        color=C_SUB, fontsize=9, ha="center", va="center", zorder=5)

# ── DASHBOARD (top-left) ──────────────────────────────────────────────────────
box(ax, 0.3, 11.0, 4.2, 1.7, C_DASH, "STREAMLIT DASHBOARD",
    ("localhost:8501",
     "• Upload & select active documents",
     "• View scores & metrics",
     "• Reset questions"))

# ── ORCHESTRATOR (top-center) ─────────────────────────────────────────────────
box(ax, 7.5, 11.0, 5.0, 1.7, C_ORCH, "ORCHESTRATOR",
    ("orchestrator.py",
     "• Runs every 2 minutes (APScheduler)",
     "• Coordinates all 3 agents",
     "• Saves results to database"))

# ── DOCUMENT STORE (top-right) ────────────────────────────────────────────────
box(ax, 15.2, 11.0, 4.5, 1.7, C_DOC, "DOCUMENT STORE",
    ("document_store.py",
     "• Default policy docs (6 built-in)",
     "• Uploaded docs (any TXT / PDF)",
     "• active_docs.json — on/off switch"))

# ─── AGENT 1: TEST AGENT ─────────────────────────────────────────────────────
box(ax, 0.3, 8.2, 4.2, 2.4, C_TEST, "AGENT 1 — TEST AGENT  (Tester)",
    ("agents/test_agent.py",
     "ROLE: Generates & fires questions",
     "",
     "• Reads each document separately",
     "• Asks LLM to make 3 questions/doc",
     "• Fires questions → Custom Agent",
     "• Smart prioritization (weights)"))

# ─── AGENT 2: CUSTOM AGENT ───────────────────────────────────────────────────
box(ax, 7.5, 7.0, 5.0, 3.6, C_CUSTOM, "AGENT 2 — CUSTOM AGENT  (The one being tested)",
    ("custom_agent_connector.py",
     "ROLE: Answers questions using documents",
     "",
     "• Receives question from Test Agent",
     "• Calls Retriever → gets top 6 chunks",
     "• Builds prompt: STEP1 quote + STEP2 answer",
     "• Calls LLM → gets answer",
     "• Intercept: if no quote found → 'not covered'",
     "• Returns answer back to Orchestrator"))

# ─── AGENT 3: EVALUATOR ──────────────────────────────────────────────────────
box(ax, 0.3, 5.0, 4.2, 2.8, C_EVAL, "AGENT 3 — EVALUATOR  (The Judge)",
    ("agents/evaluator.py",
     "ROLE: Scores every answer",
     "",
     "• Layer 1: Factual Anchor (code check)",
     "• Layer 2: Golden ROUGE-L (vs 1st answer)",
     "• Layer 3: LLM Judge (faithfulness etc)",
     "• Layer 4: Consistency (same Q → same A?)"))

# ── RAG / RETRIEVER ───────────────────────────────────────────────────────────
box(ax, 15.2, 7.6, 4.5, 3.0, C_RAG, "RAG RETRIEVER",
    ("rag_app/retriever.py",
     "• Chunks documents into paragraphs",
     "• EMBEDDING mode (Azure): semantic",
     "  search — understands meaning",
     "• TF-IDF mode: keyword fallback",
     "• Returns top 6 matching chunks",
     "• Auto-reloads on doc change"))

# ── LLM CLIENT ───────────────────────────────────────────────────────────────
box(ax, 7.5, 4.0, 5.0, 2.6, C_LLM, "LLM CLIENT",
    ("llm_client.py",
     "Used by ALL 3 agents:",
     "• Test Agent — generate questions",
     "• Custom Agent — answer questions",
     "• Evaluator — score answers (LLM Judge)",
     "",
     "Azure OpenAI GPT-4.1  OR  Groq"))

# ── DATABASE ──────────────────────────────────────────────────────────────────
box(ax, 0.3, 2.0, 4.2, 2.6, C_DB, "SQLITE DATABASE",
    ("eval_results.db",
     "• test_runs — every Q&A pair",
     "• evaluations — 4-layer scores",
     "• golden_answers — ground truth",
     "• generated_questions — test bank",
     "• consistency_reports",
     "• dlq_questions — failed retries"))

# ── UPLOADS ───────────────────────────────────────────────────────────────────
box(ax, 15.2, 4.8, 4.5, 2.4, C_DOC, "UPLOADS FOLDER",
    ("uploads/",
     "• PDF / TXT files saved here",
     "• meta.json — file registry",
     "• active_docs.json — enabled docs"))

# ── ARROWS ───────────────────────────────────────────────────────────────────

# Dashboard → Document Store
arrow(ax, 4.5, 12.0, 15.2, 12.0, C_DASH, "upload / select docs")

# Dashboard → Orchestrator
arrow(ax, 4.5, 11.8, 7.5, 11.8, C_DASH, "view results")

# Orchestrator → Test Agent
arrow(ax, 9.0, 11.0, 3.0, 10.6, C_ORCH, "1. generate & fire questions")

# Orchestrator → Evaluator
arrow(ax, 7.8, 11.0, 2.5, 7.8, C_ORCH, "3. evaluate answers")

# Test Agent → Custom Agent
arrow(ax, 4.5, 9.2, 7.5, 9.2, C_TEST, "2. question")

# Custom Agent → Test Agent (answer back)
curved_arrow(ax, 7.5, 8.7, 4.5, 8.6, C_CUSTOM, "answer", rad=-0.2)

# Custom Agent → Retriever
arrow(ax, 12.5, 9.5, 15.2, 9.5, C_CUSTOM, "retrieve chunks")

# Retriever → Document Store
arrow(ax, 17.4, 10.6, 17.4, 11.0, C_RAG, "reads docs")

# Retriever → Custom Agent
curved_arrow(ax, 15.2, 8.8, 12.5, 8.5, C_RAG, "top 6 chunks", rad=-0.2)

# Document Store → Uploads Folder
arrow(ax, 17.4, 11.0, 17.4, 7.2, C_DOC, "")

# All agents → LLM
arrow(ax, 2.5, 8.2, 8.5, 6.6, C_TEST,   "gen questions")
arrow(ax, 10.0, 7.0, 10.0, 6.6, C_CUSTOM, "answer prompt")
arrow(ax, 2.5, 5.0, 8.5, 6.0, C_EVAL,   "LLM Judge scoring")

# Orchestrator / Evaluator → Database
arrow(ax, 2.5, 5.0, 2.5, 4.6, C_EVAL, "save scores")
arrow(ax, 2.5, 8.2, 2.5, 7.6, C_DB, "")

# Database → Dashboard
curved_arrow(ax, 0.8, 4.6, 0.8, 11.0, C_DB, "scores →\ndashboard", rad=-0.3)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_items = [
    (C_TEST,   "Test Agent — generates & fires questions"),
    (C_CUSTOM, "Custom Agent — answers using RAG (the one being tested)"),
    (C_EVAL,   "Evaluator — judges and scores every answer"),
    (C_ORCH,   "Orchestrator — runs everything every 2 minutes"),
    (C_RAG,    "RAG Retriever — finds relevant document chunks"),
    (C_LLM,    "LLM Client — Azure GPT-4.1 or Groq"),
]
for i, (color, label) in enumerate(legend_items):
    xi = 0.3 + (i % 3) * 6.5
    yi = 1.5 - (i // 3) * 0.55
    ax.plot(xi, yi, "s", color=color, markersize=9, zorder=5)
    ax.text(xi + 0.25, yi, label, color=C_TEXT, fontsize=7.5, va="center", zorder=5)

plt.tight_layout(pad=0.5)
plt.savefig("system_architecture.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved: system_architecture.png")
plt.close()
