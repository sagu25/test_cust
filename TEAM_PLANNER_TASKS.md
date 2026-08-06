# Team Planner — RAG Evaluation System
## Task Breakdown (Main Tasks + Sub Tasks)

---

## TASK 1 — Project Setup & Infrastructure

| ID | Task | Status |
|---|---|---|
| 1.1 | Set up project folder structure and Git repository | Done |
| 1.2 | Configure environment variables (.env) for LLM provider, API keys | Done |
| 1.3 | Build LLM Client supporting Azure OpenAI and Groq | Done |
| 1.4 | Set up SQLite database with all required tables | Done |
| 1.5 | Build Orchestrator with APScheduler (auto-runs every 2 minutes) | Done |
| 1.6 | Set up storage.py for all database read/write operations | Done |

---

## TASK 2 — Blueverse Integration

| ID | Task | Status |
|---|---|---|
| 2.1 | Build Blueverse connector to communicate with Blueverse RAG API | Done |
| 2.2 | Implement probe agent knowledge (ask Blueverse what it knows) | Done |
| 2.3 | Integrate Blueverse with orchestrator pipeline | Done |
| 2.4 | Test Blueverse responses through evaluation system | Done |
| 2.5 | Add Blueverse mode toggle via RAG_APP_URL environment variable | Done |

---

## TASK 3 — Test Agent & Evaluation Engine

| ID | Task | Status |
|---|---|---|
| 3.1 | Build Test Agent to generate questions from document content | Done |
| 3.2 | Implement smart question prioritization (weight by past scores) | Done |
| 3.3 | Add parallel question firing using asyncio + aiohttp | Done |
| 3.4 | Build Dead Letter Queue (DLQ) — retry failed questions | Done |
| 3.5 | Build 4-layer Evaluator — Factual Anchor scoring (code-based) | Done |
| 3.6 | Build 4-layer Evaluator — Golden ROUGE-L (compare vs first answer) | Done |
| 3.7 | Build 4-layer Evaluator — LLM Judge (faithfulness, relevancy, completeness) | Done |
| 3.8 | Build 4-layer Evaluator — Consistency tracking across runs | Done |
| 3.9 | Add eval_cache to avoid re-scoring same answers | Done |
| 3.10 | Fix question generation — read documents directly instead of probing agent | Done |
| 3.11 | Improve question generation — per-document (guarantees answerability) | Done |
| 3.12 | Tighten question prompt — require explicit verbatim answers only | Done |

---

## TASK 4 — Streamlit Dashboard

| ID | Task | Status |
|---|---|---|
| 4.1 | Build main dashboard with score charts and trend graphs | Done |
| 4.2 | Add per-question detail view (expand to see all runs) | Done |
| 4.3 | Add Golden Answer comparison view | Done |
| 4.4 | Add Consistency report section with flagged questions | Done |
| 4.5 | Add "Understanding the Metrics" expandable section | Done |
| 4.6 | Add auto-refresh every 30 seconds | Done |
| 4.7 | Add manual Refresh Now button | Done |
| 4.8 | Fix ValueError — pandas Series ambiguity in consistency map | Done |

---

## TASK 5 — Custom Agent & RAG Pipeline

| ID | Task | Status |
|---|---|---|
| 5.1 | Build Custom Agent Connector (local LLM mode + API mode) | Done |
| 5.2 | Implement TF-IDF retrieval with synonym expansion | Done |
| 5.3 | Add bigram indexing (ngram_range 1-2) for better phrase matching | Done |
| 5.4 | Add keyword overlap hybrid re-ranking on TF-IDF results | Done |
| 5.5 | Implement Azure OpenAI Embedding retrieval (semantic search) | Done |
| 5.6 | Fix embedding mode activation bugs (import-time vs runtime, .env path, placeholder check) | Done |
| 5.7 | Implement adaptive score threshold ratio (drop chunks below 35% of top score) | Done |
| 5.8 | Add confidence gate — block out-of-scope questions before LLM call | Done |
| 5.9 | Implement quote-then-answer 2-step prompt (prevents LLM memory hallucination) | Done |
| 5.10 | Add post-processing intercept — override LLM answer if no quote found in Step 1 | Done |
| 5.11 | Fix chunking — merge short paragraphs under 200 chars to avoid header-only chunks | Done |
| 5.12 | Increase top_k from 4 to 6 for better chunk coverage | Done |
| 5.13 | Add dynamic system prompt showing active document titles | Done |
| 5.14 | Set temperature=0.0 for deterministic answers | Done |
| 5.15 | Add chunk score logging for every retrieval call | Done |
| 5.16 | Fix auto-reload — retriever watches meta.json and active_docs.json for changes | Done |

---

## TASK 6 — Document Management System

| ID | Task | Status |
|---|---|---|
| 6.1 | Build dynamic document store (default docs + uploaded docs) | Done |
| 6.2 | Add PDF text extraction using pypdf | Done |
| 6.3 | Add TXT file upload support | Done |
| 6.4 | Build document upload UI in dashboard sidebar | Done |
| 6.5 | Auto-reset generated questions when new document is uploaded | Done |
| 6.6 | Auto-reload retriever index when documents change | Done |
| 6.7 | Add document removal (delete uploaded docs) | Done |
| 6.8 | Build document selection checkboxes — enable/disable per document | Done |
| 6.9 | Save active document selection to active_docs.json | Done |
| 6.10 | Auto-activate new uploaded documents in selection | Done |
| 6.11 | Auto-deactivate removed documents from selection | Done |

---

## TASK 7 — Documentation & Architecture

| ID | Task | Status |
|---|---|---|
| 7.1 | Create RAG Implementation Guide (how RAG works in this system) | Done |
| 7.2 | Create Leadership Scenario Document (3 business scenarios with scores) | Done |
| 7.3 | Create Orchestrator Run Frequency document | Done |
| 7.4 | Create Architecture document (ARCHITECTURE.md) with ASCII flow diagrams | Done |
| 7.5 | Generate system architecture PNG diagram | Done |
| 7.6 | Create interactive HTML architecture diagram (architecture.html) | Done |
| 7.7 | Create animated 9-slide demo HTML (demo.html) | Done |
| 7.8 | Push all code to GitHub (test_cust repository) | Done |

---

## Summary

| Task | Area | Sub-tasks |
|---|---|---|
| Task 1 | Project Setup & Infrastructure | 6 |
| Task 2 | Blueverse Integration | 5 |
| Task 3 | Test Agent & Evaluation Engine | 12 |
| Task 4 | Streamlit Dashboard | 8 |
| Task 5 | Custom Agent & RAG Pipeline | 16 |
| Task 6 | Document Management System | 11 |
| Task 7 | Documentation & Architecture | 8 |
| **Total** | | **66 sub-tasks** |
