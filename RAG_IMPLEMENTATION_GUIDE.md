# RAG Implementation in the Custom Agent — Technical Guide

**Audience:** Developers, technical leads, anyone who wants to understand exactly what happens under the hood  
**Covers:** How RAG works in this system, step-by-step data flow, and how often the orchestrator runs

---

## Part 1 — What Is RAG?

RAG stands for **Retrieval-Augmented Generation**. It means an AI does not answer from memory alone — it first searches a set of documents to find the most relevant passages, then uses those passages as context when generating the answer.

Without RAG:
```
User question --> LLM --> Answer from training data (may be wrong or outdated)
```

With RAG:
```
User question --> Search documents --> Retrieve top passages --> LLM + passages --> Grounded answer
```

In this system the "search" step uses **TF-IDF** (a mathematical text similarity algorithm) and the "LLM" step uses **Groq** (or Azure OpenAI if configured).

---

## Part 2 — The 6 Documents Loaded into the Custom Agent

The custom agent has access to exactly 6 company policy documents, defined in `rag_app/documents.py`:

| # | Document Title | Key Facts It Contains |
|---|---|---|
| 1 | Annual Leave Policy | 15 days/year, 1.25 days/month accrual, 5-day carry-forward, 5-day advance notice |
| 2 | Remote Work Policy | 3 days/week max remote, 6 months service to qualify, 10 AM–4 PM core hours |
| 3 | Code of Conduct | No gifts > $50, VPN required, unauthorized software prohibited |
| 4 | Employee Benefits Policy | $1,500 learning budget, $100/month wellness, 16 weeks primary parental leave, 401(k) 5% match |
| 5 | Performance Review Policy | Reviews in June & December, 5-point scale, 15% max raise, 60-day PIP |
| 6 | Expense Reimbursement Policy | Dinner limit $50, receipts required over $25, submit within 30 days, hotel cap $200/night |

**What the agent does NOT know** (no document exists for these):
- Payroll or timesheets
- Employee referral rewards
- Medical leave or sick leave
- Recruitment process
- Termination procedures beyond PIP

When asked about these topics, a well-behaved agent should say "I don't have information on this." If it invents an answer, the Factual Anchor Score catches it immediately.

---

## Part 3 — How RAG Is Implemented: Step-by-Step

### Step 1: Document Loading and Chunking

When the system starts (or when `retriever.reload()` is called), the retriever reads all documents and splits them into **paragraphs** (chunks separated by blank lines).

```
File: rag_app/retriever.py → _build_chunks()

Annual Leave Policy
  Chunk 1: "All full-time employees are entitled to 15 days..."
  Chunk 2: "Leave accrues at a rate of 1.25 days per month..."
  Chunk 3: "Employees must apply for leave at least 5 working days..."
  Chunk 4: "If a public holiday falls within a period of annual leave..."
  Chunk 5: "Employees may be required to use accrued leave..."

Remote Work Policy
  Chunk 6: "Permanent employees who have completed 6 months..."
  ...and so on for all 6 documents
```

Each chunk gets tagged with its source document title. All chunks are stored in memory as a flat list.

### Step 2: Building the TF-IDF Index

All chunks are passed to `TfidfVectorizer` from scikit-learn. This converts each chunk into a numerical vector based on word frequency and rarity.

```
File: rag_app/retriever.py → _build_index()

TF-IDF = Term Frequency × Inverse Document Frequency

TF  = how often a word appears in this chunk
IDF = log(total chunks / chunks containing the word)

Words that are rare across all chunks (e.g., "accrual", "VPN", "reimbursable")
get a high weight. Common words (e.g., "the", "is", "a") get near-zero weight.
```

The result is a matrix where every row is a chunk and every column is a word — a mathematical fingerprint of the entire document collection. This index is built once and kept in memory.

### Step 3: Question Arrives

The evaluation pipeline picks a question (e.g., *"How many days of annual leave do full-time employees get per year?"*) and calls:

```python
File: custom_agent_connector.py → _query_local()

context_chunks = retriever.retrieve(question, top_k=4)
```

### Step 4: TF-IDF Retrieval (Finding the Right Chunks)

The question itself is converted to the same TF-IDF vector format. The retriever then computes **cosine similarity** between the question vector and every chunk vector.

```
File: rag_app/retriever.py → retrieve()

Cosine similarity = how closely aligned two vectors are in direction
                  = 1.0 means identical topics, 0.0 means no overlap

Question: "How many days of annual leave..."
  vs Chunk 1 (Annual Leave Policy, entitlement):  score 0.82  ← HIGH MATCH
  vs Chunk 2 (Annual Leave Policy, accrual):      score 0.61
  vs Chunk 6 (Remote Work Policy, eligibility):   score 0.08  ← LOW MATCH
  vs Chunk 18 (Expense, receipts):                score 0.02

Top 4 by score → returned as retrieved_context
```

Only chunks with a score above 0 are returned. If nothing matches, the retriever returns an empty list and the connector warns: `[CustomAgent] WARNING: Retriever returned 0 chunks`.

### Step 5: Context Assembly

The top 4 chunks are joined into a single context string, each labelled with its source:

```
File: custom_agent_connector.py

[Annual Leave Policy] All full-time employees are entitled to 15 days of paid annual
leave per calendar year. Part-time employees receive leave on a pro-rata basis...

[Annual Leave Policy] Leave accrues at a rate of 1.25 days per month. Unused leave
can be carried forward up to a maximum of 5 days...

[Annual Leave Policy] Employees must apply for leave at least 5 working days in advance...

[Remote Work Policy] Permanent employees who have completed 6 months of service...
```

### Step 6: LLM Call with Context

The context is inserted into the LLM prompt:

```python
File: custom_agent_connector.py

messages = [
    {"role": "system", "content": "You are a knowledgeable assistant. Answer questions
      strictly using the provided context. If the answer is not in the context, say so clearly."},
    {"role": "user", "content":
      f"Context:\n{context_text}\n\nQuestion: {question}\n\nAnswer based only on the context above."}
]

answer = llm_client.chat(messages, temperature=0.2)
```

`temperature=0.2` means the LLM is almost deterministic — minimal randomness in word choice — which helps consistency across repeated runs of the same question.

### Step 7: Answer Returned

The connector returns a structured response:

```python
{
    "question": "How many days of annual leave do full-time employees get per year?",
    "answer":   "Full-time employees are entitled to 15 days of paid annual leave per calendar year.",
    "retrieved_context": [
        {"source": "Annual Leave Policy", "text": "All full-time employees...", "score": 0.82},
        {"source": "Annual Leave Policy", "text": "Leave accrues at...",        "score": 0.61},
        ...
    ],
    "sources": ["Annual Leave Policy", "Annual Leave Policy", "Remote Work Policy", ...]
}
```

This full response goes to the evaluator for scoring.

---

## Part 4 — Why TF-IDF and Not a Vector Embedding Model?

| Feature | TF-IDF (this system) | Vector Embeddings (e.g., OpenAI text-embedding) |
|---|---|---|
| Cost | Free, runs locally | Paid API call per chunk |
| Speed | Milliseconds | 100ms–500ms per call |
| Setup | Zero — already in scikit-learn | Requires embedding model or API key |
| Keyword match | Excellent | Good |
| Semantic match | Limited | Excellent |
| Handles synonyms | No | Yes |

For policy documents with specific terminology (exact numbers, specific rules), TF-IDF works well because the key terms in the question usually appear in the right paragraph. A question about "annual leave entitlement" will match a paragraph containing those exact words.

A production deployment would use vector embeddings for better semantic understanding (e.g., "vacation days" matching "annual leave"). TF-IDF was chosen here to keep the system fully self-contained with no extra API dependencies.

---

## Part 5 — The Full Data Flow Diagram

```
ORCHESTRATOR (every 2 minutes)
         |
         |── TEST AGENT ──────────────────────────────────────────────────────
         |    |
         |    ├─ 1. Load question bank (15 auto-generated + any manual)
         |    ├─ 2. Smart prioritisation → pick 3 questions this cycle
         |    |      Weight 4.0 = never asked before
         |    |      Weight 3.0 = previously scored below 0.60
         |    |      Weight 2.5 = flagged inconsistent
         |    |      Weight 1.0 = medium scorer (0.60–0.80)
         |    |      Weight 0.5 = already scoring well (> 0.80)
         |    |
         |    └─ 3. For each question → CUSTOM AGENT (RAG pipeline):
         |              │
         |              ├─ TF-IDF retriever.retrieve(question, top_k=4)
         |              │     └─ cosine_similarity(question_vec, all_chunk_vecs)
         |              │     └─ returns top 4 paragraphs from 6 documents
         |              │
         |              ├─ Assemble context string from 4 chunks
         |              │
         |              └─ llm_client.chat(system_prompt + context + question)
         |                    └─ Groq API → LLM generates grounded answer
         |                    └─ answer + retrieved_context saved to DB
         |
         |── EVALUATOR AGENT ──────────────────────────────────────────────────
              |
              ├─ 4. Pick any unevaluated runs from DB
              |
              ├─ 5. For each run, run 4-layer evaluation:
              |      Layer 1 — Factual Anchor (code): extract numbers from answer,
              |                check each exists in retrieved_context
              |      Layer 2 — Golden ROUGE-L (math): compare answer to golden
              |                reference answer generated from full document
              |      Layer 3 — LLM Judge (3 calls):
              |                  → Faithfulness: did agent hallucinate?
              |                  → Relevancy: did agent answer the question?
              |                  → Completeness: did agent cover everything?
              |      Overall = 0.25×Factual + 0.25×ROUGE-L + 0.25×Faith
              |                + 0.15×Relevancy + 0.10×Completeness
              |
              └─ 6. Consistency check:
                     compare last 10 answers to each question pairwise
                     flag if consistency_score < 0.75
                     detect exact contradictions between any two answers
```

---

## Part 6 — How Many Times Will the Orchestrator Run?

### Default Settings

```
TRIGGER_INTERVAL_SECONDS = 120   (2 minutes — set in orchestrator.py line 14)
QUESTIONS_PER_CYCLE      = 3     (set in test_agent.py line 13)
```

Both can be overridden in `.env`:
```env
TRIGGER_INTERVAL_SECONDS=120
QUESTIONS_PER_CYCLE=3
```

### Run Count if Left Running

| Time running | Pipeline triggers | Questions fired | Total runs in DB |
|---|---|---|---|
| First start | 1 (immediate) | 3 | 3 |
| 10 minutes | 1 + 4 = **5** | 15 | ~15 |
| 1 hour | 1 + 29 = **30** | 90 | ~90 |
| 8 hours (workday) | 1 + 239 = **240** | 720 | ~720 |
| 24 hours | 1 + 719 = **720** | 2,160 | ~2,160 |
| 1 week | 1 + 5,039 = **5,040** | 15,120 | ~15,120 |

**Formula:** `triggers = 1 + floor(minutes × 60 / 120)` then `total_runs = triggers × QUESTIONS_PER_CYCLE`

### What Happens Each Trigger

Every 2 minutes, one **pipeline** runs which does two things in sequence:

1. **Test Agent** — fires 3 questions at the custom agent and saves answers to DB (~5–15 seconds)
2. **Evaluator Agent** — evaluates any unevaluated runs using 5 LLM calls each, then runs consistency check (~30–120 seconds depending on Groq rate limits)

One full pipeline therefore takes roughly **1 to 3 minutes** end-to-end. Since the scheduler fires on a 2-minute interval (not 2 minutes after the previous run finishes), back-to-back cycles can overlap if evaluation is slow. The system handles this safely — each run is independently identified by `run_id`.

### Groq Free Tier Limits and Their Effect

Groq's free tier allows approximately **30 requests/minute**. Each evaluation uses up to 5 LLM calls (3 for Layer 3 judge, 1 for golden answer generation if not cached, 1 for consistency check). At 3 questions per cycle, that is up to **15 LLM calls per pipeline trigger**.

In practice:
- The evaluator has an 8-second sleep buffer between runs to spread calls
- The consistency check uses cached results and is capped at 10 pairwise comparisons (45 pairs max)
- The golden answers are cached permanently — generated once per question, never repeated

If Groq rate limits are hit, the LLM client retries automatically with exponential backoff (10s → 20s → 40s → 80s).

### Stopping the Orchestrator

The only way to stop it is **Ctrl+C** in the terminal where it's running. The scheduler catches this cleanly:

```
[Orchestrator] Stopped by user.
```

No data is lost. The database is a plain SQLite file (`eval_results.db`) and every completed write is already committed. Restarting the orchestrator picks up exactly where it left off — unevaluated runs get evaluated on the next cycle.

### Recommended Running Strategy

| Goal | Setting | Expected throughput |
|---|---|---|
| Quick demo / first run | Default (120s, 3 questions) | 90 runs/hour |
| Faster data collection | `TRIGGER_INTERVAL_SECONDS=60`, `QUESTIONS_PER_CYCLE=5` | 300 runs/hour |
| Overnight soak test | Default — leave running 8 hours | ~720 runs |
| Rate-limit safe | `TRIGGER_INTERVAL_SECONDS=180`, `QUESTIONS_PER_CYCLE=2` | 40 runs/hour |

For a leadership demo with fresh data, running for **2–4 hours at default settings** gives you 180–360 runs, which is enough to see meaningful consistency patterns and score distributions on the dashboard.

---

## Part 7 — What Gets Stored in the Database

Every run adds rows to these tables:

| Table | What is stored | When written |
|---|---|---|
| `test_runs` | question, answer, retrieved_context JSON, sources, timestamp | After test agent fires a question |
| `evaluations` | all 6 metric scores, contradiction flags, missing details, overall score | After evaluator scores a run |
| `golden_answers` | one cached ideal answer per question (permanent) | First time a question is evaluated |
| `generated_questions` | the 15 auto-generated questions | Once, on first pipeline cycle |
| `consistency_reports` | consistency score, contradiction rate, drift, details per question | After each consistency check |
| `eval_cache` | hash of (question+answer) → scores (skips re-evaluation of identical answers) | After evaluating any run |

The database file is `eval_results.db` in the `eval_system/` directory. It can be inspected directly with any SQLite browser.

---

*File: `RAG_IMPLEMENTATION_GUIDE.md` — part of the eval_system documentation suite*  
*Related files: `SETUP.md`, `CUSTOM_AGENT_EXPLAINER.md`, `LEADERSHIP_SCENARIO_DOCUMENT.md`*
