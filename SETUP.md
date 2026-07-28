# RAG Evaluation System — Setup Guide

## What This System Does

An autonomous evaluation framework that continuously tests an AI agent, scores every answer across 6 metrics, detects hallucinations, and flags when the agent gives contradictory answers across runs — all without any hardcoded expected answers.

**What is being tested:** A custom LLM-powered RAG agent (retrieves policy documents → calls an LLM → returns an answer).

**What does the testing:** An automated pipeline that fires questions, evaluates responses, and displays results on a live dashboard.

---

## Prerequisites

- Python 3.11+
- One of the following API keys:
  - **Groq** (free) — get at [console.groq.com](https://console.groq.com)
  - **Azure OpenAI** (recommended for no rate limits) — from Azure Portal

---

## Step 1 — Install Dependencies

```bash
cd eval_system
pip install -r requirements.txt
```

---

## Step 2 — Configure Environment

Copy the template and fill in your key:

```bash
cp .env.example .env
```

Open `.env` and set your provider:

**Option A — Groq (free tier, has rate limits):**
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

**Option B — Azure OpenAI (recommended, no rate limits):**
```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
```

Keep the rest of the `.env` as-is — custom agent mode is already configured:

```env
RAG_APP_URL=custom
CUSTOM_AGENT_MODE=local
CUSTOM_AGENT_SYSTEM_PROMPT=You are a knowledgeable assistant. Answer questions strictly using the provided context. If the answer is not in the context, say so clearly.
```

---

## Step 3 — Run the System

Open **two terminals**, both inside `eval_system/`.

### Terminal 1 — Orchestrator (the engine)

```bash
python orchestrator.py
```

This runs the full pipeline immediately, then repeats every 2 minutes:
1. Picks 3 questions (prioritises questions the agent scored lowest on)
2. Sends them to the custom agent
3. Custom agent retrieves context from policy docs → calls LLM → returns answer
4. Evaluator scores each answer across 6 metrics
5. Saves everything to `eval_results.db`

**What you'll see:**
```
============================================================
  RAG Evaluation System
  Trigger interval: every 120 seconds
  Provider: GROQ
  RAG App: custom
============================================================

[TestAgent] Selected 3 questions to fire:
  -> How many days of annual leave do full-time employees get?
  -> Can contract employees work remotely?
  -> What is the dinner meal allowance during business travel?

[LLMClient] Provider: GROQ | Model: llama-3.1-8b-instant

[EvaluatorAgent] Evaluating run 1...
  Layer 0 Retrieval: 4 chunks scored
  Context Precision: 0.75
  Layer 1 Factual: 1.00 | supported=3 hallucinated=0
  Layer 2 Golden ROUGE-L: 0.61
  Layer 3 [Single Judge]: faith=0.90 relev=0.90 compl=0.80
  [OK] Overall: 0.82

[EvaluatorAgent] Evaluation complete. Report updated.
```

Press `Ctrl+C` to stop.

---

### Terminal 2 — Dashboard (live results)

```bash
streamlit run dashboard.py
```

Opens at **http://localhost:8501**

---

## What the Dashboard Shows

| Section | What It Tells You |
|---|---|
| Top metrics | Overall score, faithfulness, relevancy, completeness across all runs |
| Score trend chart | How the custom agent's quality changes over time |
| Consistency alerts | Questions where the agent gave contradictory answers across runs |
| Per-question breakdown | Every answer the agent gave, with scores for each metric |
| Radar chart | Visual summary of average performance across all 6 dimensions |

---

## The 6 Evaluation Metrics

| Layer | Metric | Method | What It Catches |
|---|---|---|---|
| L1 | Factual Anchor Score | Pure code (no LLM) | Facts in the answer not present in the source |
| L2 | Golden ROUGE-L | Math formula | How closely the answer matches the reference answer |
| L2 | Context Precision | LLM | Whether retrieved chunks were actually relevant |
| L2 | Context Recall | LLM | Whether the retrieval missed key information |
| L3 | Faithfulness | LLM judge | Claims made up / not supported by documents |
| L3 | Relevancy | LLM judge | Whether the answer addresses the actual question |
| L3 | Completeness | LLM judge | Whether important details from context were left out |

**Overall score formula:**
```
Overall = 0.30 × Faithfulness + 0.25 × Relevancy + 0.25 × Completeness
        + 0.10 × ROUGE-L     + 0.10 × Factual Anchor Score

Score guide:  0.80–1.00 = Good   0.60–0.79 = Warning   0.00–0.59 = Poor
```

---

## Switching to Azure Later

When you have your Azure key, update `.env`:

```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your_real_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
```

Then restart the orchestrator. No code changes required. Azure has no rate limits on the paid tier, so you can also increase `QUESTIONS_PER_CYCLE` to 5 or higher for faster coverage.

---

## Customising the Custom Agent

All custom agent settings are in `.env`:

| Variable | What It Controls |
|---|---|
| `CUSTOM_AGENT_MODE` | `local` (built-in LLM+docs) or `api` (external REST endpoint) |
| `CUSTOM_AGENT_SYSTEM_PROMPT` | The instructions given to the LLM when answering questions |
| `CUSTOM_AGENT_DESCRIPTION` | Used as fallback when the system probes the agent for its knowledge |

**To point at your own external agent API instead:**
```env
CUSTOM_AGENT_MODE=api
CUSTOM_AGENT_URL=https://your-agent-api.com/chat
CUSTOM_AGENT_API_KEY=your_api_key_here
CUSTOM_AGENT_REQUEST_FIELD=question
CUSTOM_AGENT_RESPONSE_FIELD=answer
```

---

## Project Structure

```
eval_system/
│
├── custom_agent_connector.py   ← The custom agent being tested
├── blueverse_connector.py      ← Alternative: connect to Blueverse agent
│
├── agents/
│   ├── test_agent.py           ← Generates & fires questions at the agent
│   └── evaluator_agent.py      ← Scores answers, runs consistency checks
│
├── rag_app/
│   ├── documents.py            ← 6 employee policy documents (knowledge base)
│   ├── retriever.py            ← TF-IDF document search
│   └── main.py                 ← FastAPI server (used only in local RAG mode)
│
├── orchestrator.py             ← Scheduler: runs test + eval every 2 minutes
├── dashboard.py                ← Streamlit live dashboard
├── llm_client.py               ← Unified LLM client (Groq / Azure / Grok)
├── metrics.py                  ← All scoring logic
├── storage.py                  ← SQLite database operations
├── multi_judge.py              ← Runs evaluation using multiple LLM judges
├── golden_answer_generator.py  ← Auto-generates reference answers
├── retrieval_metrics.py        ← Context precision & recall scoring
├── cache.py                    ← Caches LLM evaluation results
│
├── .env                        ← Your live config (never commit this)
├── .env.example                ← Config template
└── eval_results.db             ← SQLite database (auto-created)
```

---

## Target Modes at a Glance

| `RAG_APP_URL` value | What gets tested |
|---|---|
| `custom` | Your custom agent (`custom_agent_connector.py`) — default |
| `http://localhost:8000` | Built-in mock RAG app (requires `python start_rag_app.py`) |
| `blueverse` | Blueverse Foundry agent (requires Blueverse credentials in `.env`) |

---

## Troubleshooting

**Rate limit errors (Groq)**
> Groq free tier allows ~30 requests/minute. If you see `Max retries exceeded`, switch to Azure or reduce `QUESTIONS_PER_CYCLE=1` in `.env`.

**`ModuleNotFoundError`**
> Run `pip install -r requirements.txt` again from inside the `eval_system/` folder.

**Dashboard shows "No evaluation data yet"**
> The orchestrator hasn't completed its first cycle. Wait 2–3 minutes or check Terminal 1 for errors.

**Custom agent returns no context chunks**
> This is normal for questions outside the 6 policy documents. The agent will answer from LLM knowledge and the factual anchor score will reflect that.
