import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
import random
import llm_client
import storage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

RAG_APP_URL = os.getenv("RAG_APP_URL", "http://localhost:8000")
QUESTIONS_PER_CYCLE = int(os.getenv("QUESTIONS_PER_CYCLE", "3"))


# ── Retry + Async HTTP ────────────────────────────────────────────────────────

async def _fire_async(session, question: str) -> dict | None:
    import aiohttp
    if RAG_APP_URL.lower() == "blueverse":
        import blueverse_connector
        return blueverse_connector.query(question)
    if RAG_APP_URL.lower() == "custom":
        import custom_agent_connector
        return custom_agent_connector.query(question)
    try:
        async with session.post(
            f"{RAG_APP_URL}/query",
            json={"question": question},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except Exception as e:
        return {"_error": str(e)}


async def fire_questions_parallel(questions: list[str]) -> list[dict]:
    """
    Fire multiple questions to the RAG app concurrently.
    Returns list of {question, result} dicts.
    """
    import aiohttp
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [_fire_async(session, q) for q in questions]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for question, response in zip(questions, responses):
            if isinstance(response, Exception):
                results.append({"question": question, "result": None,
                                 "error": str(response)})
            elif response and "_error" in response:
                results.append({"question": question, "result": None,
                                 "error": response["_error"]})
            else:
                results.append({"question": question, "result": response,
                                 "error": None})
    return results


# ── Smart Question Prioritization ─────────────────────────────────────────────

def get_prioritized_questions(all_questions: list[dict], n: int) -> list[str]:
    """
    Select n questions using weighted prioritization:
      - Never-asked questions:              weight 4.0 (highest)
      - Low-scoring questions (< 0.60):     weight 3.0
      - Flagged inconsistent questions:     weight 2.5
      - Medium-scoring (0.60 – 0.80):      weight 1.0
      - High-scoring questions (> 0.80):   weight 0.5
      - Dead letter queue (retry):         weight 3.5
    """
    past_scores  = storage.get_question_scores()
    dlq_items    = {d["question"] for d in storage.get_dlq_questions()}
    cons_data    = storage.get_all_evaluated_data()
    flagged      = {c["question"] for c in cons_data.get("consistency", [])
                    if c.get("flagged")}

    weighted = []
    for q_entry in all_questions:
        q = q_entry["question"] if isinstance(q_entry, dict) else q_entry
        info = past_scores.get(q)

        if q in dlq_items:
            weight = 3.5
        elif info is None:
            weight = 4.0  # never asked
        elif q in flagged:
            weight = 2.5  # inconsistent
        elif info["avg_score"] < 0.60:
            weight = 3.0  # poor performer
        elif info["avg_score"] < 0.80:
            weight = 1.0  # medium
        else:
            weight = 0.5  # good — test less often

        weighted.append((q, weight))

    if not weighted:
        return []

    questions_list = [q for q, _ in weighted]
    weights_list   = [w for _, w in weighted]
    k              = min(n, len(questions_list))
    selected       = random.choices(questions_list, weights=weights_list, k=k)
    # Deduplicate while preserving order
    seen, unique = set(), []
    for q in selected:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique


# ── Question Generation ───────────────────────────────────────────────────────

def _questions_from_one_doc(title: str, content: str, count: int = 3) -> list[dict]:
    """Generate `count` questions that are answerable ONLY from this single document."""
    import re
    prompt = f"""You are a QA engineer. Below is ONE policy document.
Generate exactly {count} test questions whose answers can be found as EXPLICIT sentences or numbers in this document.

DOCUMENT: {title}
---
{content[:3000]}
---

STRICT RULES:
1. Every answer must exist as a direct quote in the text above — NOT inferred or implied.
2. Only ask about specific numbers, names, limits, dates, percentages, or defined processes.
3. Do NOT ask vague questions (e.g. "how does the company support X?").
4. Do NOT ask yes/no questions.
5. Do NOT ask about anything not explicitly stated above.

Respond ONLY with a valid JSON array of exactly {count} items:
[
  {{"question": "...", "category": "factual"}},
  {{"question": "...", "category": "procedural"}}
]"""
    response = llm_client.chat([{"role": "user", "content": prompt}], temperature=0.2)
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if match:
        try:
            qs = json.loads(match.group())
            for q in qs:
                q["source_doc"] = title
            return qs
        except json.JSONDecodeError:
            pass
    return []


def _generate_questions_per_document(documents: list[dict]) -> list[dict]:
    """Generate questions document-by-document so every question is answerable."""
    total_target = 15
    per_doc = max(2, total_target // len(documents))
    all_questions = []

    for doc in documents:
        print(f"[TestAgent] Generating {per_doc} questions from: {doc['title']}")
        qs = _questions_from_one_doc(doc["title"], doc["content"], count=per_doc)
        print(f"[TestAgent]   -> Got {len(qs)} questions")
        all_questions.extend(qs)

    # Top up to 15 if we got fewer
    if len(all_questions) < total_target and documents:
        extra = total_target - len(all_questions)
        doc = documents[0]
        qs = _questions_from_one_doc(doc["title"], doc["content"], count=extra)
        all_questions.extend(qs)

    print(f"[TestAgent] Total questions generated: {len(all_questions)}")
    return all_questions[:total_target]


def analyze_app_and_generate_questions() -> list[dict]:
    import requests
    import re
    print("[TestAgent] Analyzing app to generate grounded questions...")

    content_block = ""

    if RAG_APP_URL.lower() == "blueverse":
        print("[TestAgent] Target is Blueverse — probing agent knowledge...")
        import blueverse_connector
        content_block = blueverse_connector.probe_agent_knowledge()
        source_label  = "Blueverse agent (self-reported knowledge)"

    elif RAG_APP_URL.lower() == "custom":
        print("[TestAgent] Target is Custom Agent — generating questions per document...")
        from rag_app.document_store import get_all_documents
        documents = get_all_documents()
        if not documents:
            print("[TestAgent] No documents found in document store.")
            return [{"question": "What topics does this system cover?",
                     "category": "general"}]
        return _generate_questions_per_document(documents)

    else:
        # ── Custom RAG App: fetch actual document content ─────────────────────
        documents = []
        try:
            resp = requests.get(
                f"{RAG_APP_URL}/content",
                params={"chars_per_doc": 800},
                timeout=15,
            )
            if resp.status_code == 200:
                documents = resp.json().get("documents", [])
        except Exception as e:
            print(f"[TestAgent] Could not fetch document content: {e}")

        if not documents:
            print("[TestAgent] No documents found — cannot generate grounded questions.")
            return [{"question": "What topics does this system cover?",
                     "category": "general"}]

        for doc in documents:
            content_block += f"\n\n--- {doc['title']} ---\n{doc['content']}"
        source_label = "RAG app document content"

    if not content_block.strip():
        print("[TestAgent] No content discovered. Using fallback question.")
        return [{"question": "What topics does this system cover?", "category": "general"}]

    print(f"[TestAgent] Generating questions from: {source_label}")

    prompt = f"""You are a QA engineer building a test suite for an AI assistant that answers ONLY from policy documents.

DOCUMENTS:
{content_block}

Your job: generate 15 questions where EACH answer can be found as an EXPLICIT sentence or number in the documents above.

STRICT RULES:
1. The answer must exist as a direct quote or explicit statement in the text — NOT inferred, NOT implied, NOT summarized.
2. Before writing each question, verify you can find an exact sentence in the text that answers it.
3. Prefer questions about specific numbers, limits, dates, names, percentages, and defined processes.
4. Do NOT ask about things the document only vaguely mentions, or things that require combining multiple ideas.
5. Do NOT ask about topics not mentioned at all.
6. Do NOT generate yes/no questions.

Good example: "What is the maximum reimbursement amount for training expenses per year?"
Bad example: "How does the company support employee wellbeing?" (too vague, answer requires inference)

Question types to include:
- factual     : exact numbers, limits, percentages, dates, names
- procedural  : explicit step-by-step process described in the text
- eligibility : exact criteria stated for who qualifies or is excluded
- adversarial : a question with a slightly wrong number/fact to test if agent corrects it

Respond ONLY with a valid JSON array:
[
  {{"question": "...", "category": "factual"}},
  {{"question": "...", "category": "procedural"}},
  ...15 total
]"""

    response = llm_client.chat([{"role": "user", "content": prompt}], temperature=0.3)
    match    = re.search(r"\[.*\]", response, re.DOTALL)
    if match:
        try:
            questions = json.loads(match.group())
            print(f"[TestAgent] Generated {len(questions)} grounded questions.")
            return questions
        except json.JSONDecodeError:
            pass

    print("[TestAgent] Failed to parse generated questions.")
    return [{"question": "What topics does this system cover?", "category": "general"}]


def get_or_generate_questions() -> list[dict]:
    existing = storage.get_generated_questions()
    if not existing:
        existing = analyze_app_and_generate_questions()
        storage.save_generated_questions(existing)

    manual = storage.get_manual_questions()
    manual_formatted = [
        {"question": m["question"], "category": m.get("question_type", "manual")}
        for m in manual
    ]
    all_q = existing + manual_formatted
    print(f"[TestAgent] {len(existing)} auto + {len(manual_formatted)} manual = {len(all_q)} total questions")
    return all_q


# ── Dead Letter Queue Retry ───────────────────────────────────────────────────

def retry_dead_letter_queue():
    dlq = storage.get_dlq_questions(max_attempts=3)
    if not dlq:
        return
    print(f"[TestAgent] Retrying {len(dlq)} failed question(s) from DLQ...")

    # Use the connector that matches the current target
    if RAG_APP_URL.lower() == "blueverse":
        import blueverse_connector
        _connector_query = blueverse_connector.query
    elif RAG_APP_URL.lower() == "custom":
        import custom_agent_connector
        _connector_query = custom_agent_connector.query
    else:
        _connector_query = None

    import requests
    for item in dlq:
        q = item["question"]
        try:
            if _connector_query:
                data = _connector_query(q)
                if data:
                    storage.save_test_run(
                        question          = q,
                        answer            = data.get("answer", ""),
                        retrieved_context = data.get("retrieved_context", []),
                        sources           = data.get("sources", []),
                    )
                    storage.remove_from_dlq(q)
                    print(f"[TestAgent] DLQ retry succeeded for: {q[:60]}")
                else:
                    storage.save_to_dlq(q, "No response from connector")
            else:
                resp = requests.post(f"{RAG_APP_URL}/query",
                                     json={"question": q}, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    storage.save_test_run(
                        question          = q,
                        answer            = data.get("answer", ""),
                        retrieved_context = data.get("retrieved_context", []),
                        sources           = data.get("sources", []),
                    )
                    storage.remove_from_dlq(q)
                    print(f"[TestAgent] DLQ retry succeeded for: {q[:60]}")
                else:
                    storage.save_to_dlq(q, f"HTTP {resp.status_code}")
        except Exception as e:
            storage.save_to_dlq(q, str(e))


# ── Main Run ──────────────────────────────────────────────────────────────────

def run():
    print(f"\n[TestAgent] Starting test run (parallel={QUESTIONS_PER_CYCLE} questions)...")

    # Retry any previously failed questions first
    retry_dead_letter_queue()

    all_questions = get_or_generate_questions()
    if not all_questions:
        print("[TestAgent] No questions available.")
        return

    # Smart prioritization
    selected = get_prioritized_questions(all_questions, n=QUESTIONS_PER_CYCLE)
    if not selected:
        selected = [all_questions[0]["question"] if isinstance(all_questions[0], dict)
                    else all_questions[0]]

    print(f"[TestAgent] Selected {len(selected)} questions to fire:")
    for q in selected:
        print(f"  -> {q[:80]}")

    # Parallel firing via asyncio + aiohttp
    results = asyncio.run(fire_questions_parallel(selected))

    saved = 0
    for item in results:
        question = item["question"]
        result   = item["result"]
        error    = item["error"]

        if error or not result:
            print(f"[TestAgent] FAILED: {question[:60]} — {error}")
            storage.save_to_dlq(question, error or "No response")
            continue

        run_id = storage.save_test_run(
            question          = question,
            answer            = result.get("answer", ""),
            retrieved_context = result.get("retrieved_context", []),
            sources           = result.get("sources", []),
        )
        print(f"[TestAgent] Saved run {run_id}: {question[:60]}")
        saved += 1

    print(f"[TestAgent] {saved}/{len(selected)} questions saved successfully.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    storage.init_db()
    run()
