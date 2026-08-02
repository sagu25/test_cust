# RAG Evaluation System — Architecture & Flow Document

---

## 1. What the System Does

This system automatically tests an AI agent (your Custom Agent) that answers questions from uploaded documents. It:
- Uploads any document and makes it searchable
- Generates test questions from those documents
- Asks the agent those questions and records its answers
- Evaluates answer quality using 4 different scoring methods
- Shows results on a live dashboard

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        STREAMLIT DASHBOARD                       │
│              (dashboard.py  —  localhost:8501)                   │
│                                                                   │
│   ┌─────────────────┐          ┌────────────────────────────┐   │
│   │  Document        │          │   Metrics & Results        │   │
│   │  Management      │          │   • Scores over time       │   │
│   │  • Upload docs   │          │   • Per-question detail    │   │
│   │  • Select active │          │   • Consistency reports    │   │
│   │  • Remove docs   │          │   • Golden answer compare  │   │
│   └────────┬─────────┘          └────────────────────────────┘   │
└────────────┼────────────────────────────────────────────────────┘
             │ Upload / Select
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DOCUMENT STORE                               │
│              (rag_app/document_store.py)                         │
│                                                                   │
│   Default Policy Docs (code)    +    Uploaded Docs (uploads/)   │
│   • Annual Leave Policy              • Any TXT or PDF file      │
│   • Remote Work Policy               • Stored in uploads/        │
│   • Training & Development           • Listed in meta.json       │
│   • Code of Conduct                                              │
│   • Performance Review                                           │
│   • Expense Policy               Active Selection: active_docs.json│
└─────────────────────────────────────────────────────────────────┘
             │ Documents loaded
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RETRIEVER                                   │
│                 (rag_app/retriever.py)                           │
│                                                                   │
│   Mode selected automatically based on .env config:             │
│                                                                   │
│   EMBEDDING MODE (Azure)          TF-IDF MODE (Fallback)        │
│   • text-embedding-3-small        • Keyword-based search        │
│   • Semantic understanding        • Synonym expansion            │
│   • Finds "budget" when           • Bigram indexing             │
│     asked about "expenses"        • Free, no API needed         │
│                                                                   │
│   Auto-reloads when meta.json or active_docs.json changes       │
└─────────────────────────────────────────────────────────────────┘
             │
             │                    Runs every 2 minutes
             ▼                           │
┌───────────────────────┐    ┌───────────┴──────────────────────┐
│   CUSTOM AGENT        │◄───│         ORCHESTRATOR             │
│   CONNECTOR           │    │         (orchestrator.py)        │
│                       │    │                                   │
│   (custom_agent_      │    │  • APScheduler triggers cycle    │
│    connector.py)      │    │  • Calls Test Agent              │
│                       │    │  • Calls Evaluator               │
│   1. Retrieve chunks  │    │  • Saves to SQLite DB            │
│   2. Build prompt     │    └──────────────────────────────────┘
│   3. Call LLM                        │
│   4. Intercept check  │              │
│   5. Return answer    │    ┌─────────┴────────────────────────┐
└───────────┬───────────┘    │         TEST AGENT               │
            │                │      (agents/test_agent.py)      │
            │                │                                   │
            │                │  • Generates questions per doc   │
            │                │  • Smart prioritization          │
            │                │  • Fires questions in parallel   │
            │                │  • Dead Letter Queue (DLQ)       │
            ▼                └──────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                        LLM CLIENT                               │
│                      (llm_client.py)                            │
│                                                                  │
│         Azure OpenAI (GPT-4.1)    OR    Groq                   │
│         Controlled by LLM_PROVIDER in .env                      │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EVALUATOR                                   │
│                  (agents/evaluator.py)                           │
│                                                                   │
│   4-Layer Scoring System:                                        │
│   ┌──────────────────┐  ┌──────────────────┐                   │
│   │ 1. Factual Anchor│  │ 2. Golden ROUGE-L│                   │
│   │  Code-based check│  │  Compare vs first│                   │
│   │  numbers/dates   │  │  correct answer  │                   │
│   └──────────────────┘  └──────────────────┘                   │
│   ┌──────────────────┐  ┌──────────────────┐                   │
│   │ 3. LLM Judge     │  │ 4. Consistency   │                   │
│   │  Faithfulness    │  │  Same Q asked    │                   │
│   │  Relevancy       │  │  multiple times  │                   │
│   │  Completeness    │  │  → same answer?  │                   │
│   └──────────────────┘  └──────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE                               │
│                   (eval_results.db)                              │
│                                                                   │
│  test_runs │ evaluations │ golden_answers │ generated_questions  │
│  consistency_reports │ eval_cache │ dlq_questions               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Document Upload Flow

```
User uploads PDF/TXT in Dashboard
            │
            ▼
    Extract Text
    (pypdf for PDF, decode for TXT)
            │
            ▼
    Save file to uploads/
    Update uploads/meta.json
    Auto-add to active_docs.json
            │
            ▼
    Clear generated_questions
    Clear golden_answers
    Clear eval_cache
    (so fresh questions are made from new doc)
            │
            ▼
    Retriever reloads index
    (detects meta.json change)
            │
            ▼
    Next orchestrator cycle picks up new doc ✓
```

---

## 4. RAG Query Flow (How the Agent Answers)

```
Question comes in
        │
        ▼
Retriever finds most relevant chunks
(top 6 chunks from active documents)
        │
        ├─── EMBEDDING MODE ──────────────────────┐
        │    • Embed question using Azure API       │
        │    • Compute cosine similarity            │
        │    • Returns semantically matching chunks │
        │                                          │
        └─── TF-IDF MODE (fallback) ──────────────┘
             • Expand query with synonyms
             • Keyword + bigram matching
             • Returns keyword-matching chunks
                      │
                      ▼
        Build Prompt with chunks:
        ┌─────────────────────────────┐
        │ DOCUMENT EXCERPTS:          │
        │ [SOURCE: Policy Doc]        │
        │ <chunk text>                │
        │                             │
        │ QUESTION: <question>        │
        │                             │
        │ STEP 1 — Quote the most     │
        │ relevant passage from above │
        │                             │
        │ STEP 2 — Answer using ONLY  │
        │ what you quoted in Step 1   │
        └─────────────────────────────┘
                      │
                      ▼
              LLM generates answer
                      │
                      ▼
        Post-processing intercept check:
        Did LLM say "No relevant sentence
        found in excerpts" in Step 1?
                      │
              YES ────┤──── NO
               │      │      │
               ▼      │      ▼
        Return:        │  Return LLM answer ✓
        "This is not   │
        covered in     │
        policy docs"   │
```

---

## 5. Question Generation Flow

```
Orchestrator cycle starts
        │
        ▼
Are questions already in DB?
        │
   YES ─┤─ NO
   │    │   │
   │    │   ▼
   │    │  Load all active documents
   │    │        │
   │    │        ▼
   │    │  For EACH document separately:
   │    │  ┌─────────────────────────────────┐
   │    │  │  Send document text to LLM       │
   │    │  │  "Generate 3 questions whose     │
   │    │  │   answers exist as EXPLICIT      │
   │    │  │   sentences in this document"    │
   │    │  │                                  │
   │    │  │  LLM returns:                    │
   │    │  │  [{"question": "...",            │
   │    │  │    "category": "factual"}]       │
   │    │  └─────────────────────────────────┘
   │    │        │
   │    │        ▼
   │    │  Combine all questions (15 total)
   │    │  Save to generated_questions table
   │    │        │
   └────┘        ▼
        Smart Prioritization:
        • Never-asked: weight 4.0 (highest)
        • Low scoring (<0.60): weight 3.0
        • Inconsistent: weight 2.5
        • Medium (0.60-0.80): weight 1.0
        • High scoring (>0.80): weight 0.5
                │
                ▼
        Select 3 questions per cycle
        Fire in parallel → get answers
```

---

## 6. Evaluation Flow (4-Layer Scoring)

```
Agent answer received
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  LAYER 1: FACTUAL ANCHOR (Code-based)                 │
│  Extract numbers/dates from answer                    │
│  Check if they appear in retrieved document chunks    │
│  Score: 1.0 if all facts grounded, 0.0 if none       │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  LAYER 2: GOLDEN ROUGE-L (Math-based)                 │
│  Is this the FIRST time this question was asked?      │
│  YES → Store this answer as the Golden Answer         │
│  NO  → Compare new answer vs Golden Answer            │
│        using ROUGE-L (longest common subsequence)     │
│        Score: 0.0 (different) to 1.0 (identical)     │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  LAYER 3: LLM JUDGE (AI-based)                        │
│  Send question + answer + context to LLM              │
│  LLM scores 3 dimensions (0.0 to 1.0 each):          │
│  • Faithfulness: Is answer supported by context?      │
│  • Relevancy: Does it actually answer the question?   │
│  • Completeness: Is it a full answer?                 │
│  Overall = average of the 3                           │
└───────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│  LAYER 4: CONSISTENCY (Tracked over time)             │
│  Same question asked in multiple cycles               │
│  Are all answers saying the same thing?               │
│  Flagged ⚠ if answers contradict each other          │
└───────────────────────────────────────────────────────┘
        │
        ▼
Overall Score = weighted average of all layers
Save to SQLite → Dashboard shows results
```

---

## 7. Orchestrator Cycle (Runs Every 2 Minutes)

```
T+0:00  Orchestrator wakes up
           │
           ▼
        Retry any failed questions (DLQ)
           │
           ▼
        Get/generate questions
           │
           ▼
        Select 3 priority questions
           │
           ▼
        Fire all 3 in parallel to Custom Agent
           │
           ▼
        Save answers to test_runs table
           │
           ▼
        Run 4-layer evaluation on each answer
           │
           ▼
        Save scores to evaluations table
           │
           ▼
        Run consistency check across all runs
           │
           ▼
T+2:00  Sleep until next cycle
```

---

## 8. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Dashboard UI | Streamlit | Live visualization, document upload |
| LLM (Azure) | GPT-4.1 (Azure OpenAI) | Answering questions, LLM Judge |
| LLM (Local) | Groq (Llama/Mixtral) | Cheaper alternative for development |
| Embeddings | Azure text-embedding-3-small | Semantic document search |
| Fallback Search | TF-IDF (scikit-learn) | Keyword search when no Azure embedding |
| Database | SQLite | Storing all runs, scores, golden answers |
| Scheduler | APScheduler | Triggering evaluation cycles every 2 min |
| PDF Parsing | pypdf | Extracting text from uploaded PDFs |
| Async Requests | aiohttp + asyncio | Firing multiple questions in parallel |
| Retry Logic | tenacity | Retrying failed LLM calls |

---

## 9. Key Design Decisions

**Why per-document question generation?**
When all documents are sent together, the LLM mixes topics and creates questions that span multiple documents — retrieval then fails to find a single chunk with the full answer. Per-document generation guarantees every question has an explicit answer in one document.

**Why embedding over TF-IDF?**
TF-IDF matches exact keywords. If a question says "training expenses" but the document says "learning budget," TF-IDF scores near zero and retrieves the wrong chunk. Embeddings understand meaning, so "training expenses" and "learning budget" map to similar vectors.

**Why quote-then-answer prompt?**
GPT-4.1 has strong training knowledge. If asked "What is the learning budget?" it might answer "typically $1,000-$2,000" from general HR knowledge rather than from your document. Forcing Step 1 (find a quote) before Step 2 (answer) anchors the response to document text.

**Why golden answers reset on document change?**
Golden answers capture what the agent said when the system was working correctly. If you change the documents or fix the retrieval, the agent's correct answer changes too — old golden answers become stale and cause false contradiction scores.

---

## 10. File Structure

```
eval_system/
├── dashboard.py              # Streamlit UI
├── orchestrator.py           # Scheduler + pipeline coordinator
├── custom_agent_connector.py # RAG query handler + prompt builder
├── llm_client.py             # Azure / Groq LLM wrapper
├── storage.py                # SQLite read/write helpers
├── eval_results.db           # SQLite database (auto-created)
├── .env                      # API keys and config (not in git)
│
├── agents/
│   ├── test_agent.py         # Question generation + firing
│   └── evaluator.py          # 4-layer scoring engine
│
├── rag_app/
│   ├── document_store.py     # Document CRUD + active selection
│   ├── retriever.py          # Embedding/TF-IDF search engine
│   ├── documents.py          # Default policy documents (code)
│   └── main.py               # FastAPI app (optional REST mode)
│
└── uploads/                  # User-uploaded documents
    ├── meta.json             # Registry of uploaded files
    └── active_docs.json      # Which documents are currently active
```
