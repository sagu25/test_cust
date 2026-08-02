"""
Custom Agent Connector

Two modes (set CUSTOM_AGENT_MODE in .env):
  "local"  — LLM-powered agent using your existing llm_client + document store
             (works immediately with no extra config beyond your LLM key)
  "api"    — POST questions to any external REST endpoint
             (set CUSTOM_AGENT_URL + optionally CUSTOM_AGENT_API_KEY)
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv("CUSTOM_AGENT_MODE", "local").lower()

# API mode
AGENT_URL      = os.getenv("CUSTOM_AGENT_URL", "")
API_KEY        = os.getenv("CUSTOM_AGENT_API_KEY", "")
AUTH_HEADER    = os.getenv("CUSTOM_AGENT_AUTH_HEADER", "Authorization")
AUTH_PREFIX    = os.getenv("CUSTOM_AGENT_AUTH_PREFIX", "Bearer")
REQUEST_FIELD  = os.getenv("CUSTOM_AGENT_REQUEST_FIELD", "question")
RESPONSE_FIELD = os.getenv("CUSTOM_AGENT_RESPONSE_FIELD", "answer")

# Local mode
SYSTEM_PROMPT = os.getenv(
    "CUSTOM_AGENT_SYSTEM_PROMPT",
    (
        "You are a knowledgeable and concise assistant. "
        "Answer the question strictly using the context provided. "
        "If the answer is not in the context, say so clearly."
    ),
)
AGENT_DESCRIPTION = os.getenv("CUSTOM_AGENT_DESCRIPTION", "Custom LLM-based agent")


def query(question: str) -> dict | None:
    if MODE == "api":
        return _query_api(question)
    return _query_local(question)


def _query_api(question: str) -> dict | None:
    if not AGENT_URL:
        raise ValueError("CUSTOM_AGENT_URL not set. Add it to your .env file.")

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers[AUTH_HEADER] = f"{AUTH_PREFIX} {API_KEY}".strip()

    try:
        resp = requests.post(
            AGENT_URL,
            json={REQUEST_FIELD: question},
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        answer = (
            data.get(RESPONSE_FIELD)
            or data.get("answer")
            or data.get("output")
            or data.get("text")
            or data.get("content")
            or str(data)
        )

        raw_sources = data.get("sources", data.get("source_docs", data.get("references", [])))
        contexts = []
        for s in raw_sources if isinstance(raw_sources, list) else []:
            if isinstance(s, dict):
                contexts.append({
                    "source": s.get("title", s.get("name", "Custom Agent")),
                    "text":   s.get("content", s.get("text", str(s))),
                    "score":  float(s.get("score", 1.0)),
                })
            elif isinstance(s, str):
                contexts.append({"source": "Custom Agent", "text": s, "score": 1.0})

        return {
            "question":          question,
            "answer":            answer,
            "retrieved_context": contexts,
            "sources":           [c["source"] for c in contexts] or ["Custom Agent"],
        }

    except requests.HTTPError as e:
        print(f"[CustomAgent] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[CustomAgent] API error: {e}")
        return None


def _query_local(question: str) -> dict | None:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import llm_client

    # Pull context from the local document store
    try:
        from rag_app import retriever

        # Confidence gate threshold differs by retrieval mode:
        # Embedding cosine similarity: even unrelated chunks score 0.20-0.40
        # TF-IDF: unrelated chunks score near 0.00-0.08
        use_embedding = retriever._use_embedding()
        gate_threshold = 0.50 if use_embedding else 0.08

        context_chunks = retriever.retrieve(question, top_k=4)
        if not context_chunks:
            print("[CustomAgent] WARNING: Retriever returned 0 chunks.")
        elif context_chunks[0]["score"] < gate_threshold:
            print(f"[CustomAgent] Confidence gate triggered "
                  f"(best score {context_chunks[0]['score']:.3f} < {gate_threshold} "
                  f"[{'embedding' if use_embedding else 'tfidf'} mode]) — "
                  f"topic not covered in documents.")
            return {
                "question":          question,
                "answer":            "This topic is not covered in the policy documents.",
                "retrieved_context": [],
                "sources":           [],
            }
    except Exception as e:
        print(f"[CustomAgent] ERROR loading documents from rag_app: {e}")
        context_chunks = []

    # Log exactly what was retrieved so retrieval issues are visible
    if context_chunks:
        print(f"[CustomAgent] Retrieved {len(context_chunks)} chunks:")
        for c in context_chunks:
            print(f"  [{c['score']:.3f}] {c['source']}: {c['text'][:80].strip()}...")

    context_text = "\n\n".join(
        f"[SOURCE: {c['source']}]\n{c['text']}" for c in context_chunks
    )

    if context_text:
        user_content = (
            f"POLICY DOCUMENT EXCERPTS:\n\n"
            f"{context_text}\n\n"
            f"---\n"
            f"QUESTION: {question}\n\n"
            f"STEP 1 — Find and quote the exact sentence(s) from the excerpts above "
            f"that contain the answer. Copy them word for word. "
            f"If no sentence answers the question, write: "
            f"'No relevant sentence found in excerpts.'\n\n"
            f"STEP 2 — Using ONLY what you quoted in Step 1, write a clear answer. "
            f"Do not add, change, or remove any number, date, or amount from the quote. "
            f"Do not use your training knowledge. "
            f"If Step 1 found nothing, say: 'This is not covered in the policy documents.'"
        )
    else:
        user_content = (
            f"QUESTION: {question}\n\n"
            "There are no policy document excerpts available for this question.\n"
            "You MUST say: 'This is not covered in the policy documents.'\n"
            "Do not attempt to answer from your own knowledge."
        )

    # Build dynamic system prompt that reflects current document titles
    try:
        from rag_app.document_store import get_all_documents
        titles       = [d["title"] for d in get_all_documents()]
        dynamic_prompt = (
            SYSTEM_PROMPT +
            f" Your knowledge base covers these documents: {', '.join(titles)}."
        )
    except Exception:
        dynamic_prompt = SYSTEM_PROMPT

    messages = [
        {"role": "system", "content": dynamic_prompt},
        {"role": "user",   "content": user_content},
    ]

    try:
        answer = llm_client.chat(messages, temperature=0.0)

        # If Step 1 found no quote, the LLM sometimes still answers from memory in Step 2.
        # Intercept and enforce the "not covered" response.
        answer_lower = answer.lower()
        if (
            "no relevant sentence found" in answer_lower
            or "not found in excerpts" in answer_lower
            or "cannot find" in answer_lower
            or "no sentence" in answer_lower
        ):
            answer = "This is not covered in the policy documents."

        return {
            "question":          question,
            "answer":            answer,
            "retrieved_context": context_chunks,
            "sources":           [c["source"] for c in context_chunks] or ["Custom Agent"],
        }
    except Exception as e:
        print(f"[CustomAgent] LLM error: {e}")
        return None


def is_online() -> bool:
    if MODE == "api":
        try:
            base = AGENT_URL.rsplit("/", 1)[0] if "/" in AGENT_URL else AGENT_URL
            requests.get(base, timeout=5)
            return True
        except Exception:
            return False
    else:
        try:
            import llm_client
            llm_client.get_client()
            return True
        except Exception:
            return False


def probe_agent_knowledge() -> str:
    """Ask discovery questions to understand what the agent knows."""
    probe_questions = [
        "What topics and subjects can you help me with? Please be specific.",
        "What kind of information do you have access to? List all areas you cover.",
        "Give me a summary of the policies and rules you know about, "
        "including any specific numbers, limits, or percentages.",
    ]

    print("[CustomAgent] Probing agent to discover what it knows...")
    responses = []

    for q in probe_questions:
        result = query(q)
        if result and result.get("answer"):
            responses.append(result["answer"])
            print(f"[CustomAgent] Probe: {result['answer'][:100]}...")

    if responses:
        combined = "\n\n".join(responses)
        print(f"[CustomAgent] Knowledge discovered from {len(responses)} probe questions.")
        return combined

    fallback = AGENT_DESCRIPTION
    print("[CustomAgent] Probing failed. Using CUSTOM_AGENT_DESCRIPTION from .env.")
    return fallback
