"""
Document retriever — two modes selected automatically:

  EMBEDDING mode  (recommended)
    Activated when AZURE_EMBEDDING_DEPLOYMENT_NAME is set in .env
    Uses Azure OpenAI text-embedding model for semantic search.
    "training expenses" correctly matches "learning budget" because
    embeddings understand meaning, not just keywords.

  TF-IDF mode  (fallback)
    Used when Azure embedding credentials are not configured.
    Keyword-based search — fast, free, no API needed.
    Includes synonym expansion and hybrid re-ranking to compensate
    for vocabulary gaps.

No code changes needed when switching modes — just set or unset
AZURE_EMBEDDING_DEPLOYMENT_NAME in your .env file.
"""
import os
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as _sklearn_cosine

from dotenv import load_dotenv
load_dotenv()

_PLACEHOLDER = {"your_azure", "your-resource", "placeholder", ""}


def _use_embedding() -> bool:
    """Check at runtime (not import time) so .env is always fully loaded."""
    key      = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "").strip()
    api_key  = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()

    print(f"[Retriever] DEBUG _use_embedding check:")
    print(f"  EMBED_DEPLOYMENT : '{key}'")
    print(f"  API_KEY (first 8): '{api_key[:8] if api_key else 'EMPTY'}'")
    print(f"  ENDPOINT         : '{endpoint[:40] if endpoint else 'EMPTY'}'")

    result = bool(
        key and api_key and endpoint
        and not any(p in api_key.lower()  for p in _PLACEHOLDER)
        and not any(p in endpoint.lower() for p in _PLACEHOLDER)
    )
    print(f"  USE_EMBEDDING    : {result}")
    return result

# ── Shared state ──────────────────────────────────────────────────────────────
_chunks: list[dict] = []

# TF-IDF state
_vectorizer  = None
_tfidf_matrix = None

# Embedding state
_chunk_embeddings: np.ndarray | None = None   # shape (n_chunks, dim)

# ── TF-IDF synonyms (only used in TF-IDF fallback mode) ──────────────────────
_SYNONYMS = {
    "training":       ["learning", "professional development", "education", "courses"],
    "educational":    ["learning", "training", "professional development"],
    "expenses":       ["budget", "reimbursement", "allowance", "costs", "claims"],
    "expense":        ["budget", "reimbursement", "allowance", "cost", "claim"],
    "vacation":       ["annual leave", "leave", "holiday", "paid leave"],
    "sick":           ["medical", "illness", "health"],
    "pay":            ["salary", "compensation", "remuneration"],
    "raise":          ["salary increase", "increment"],
    "fire":           ["termination", "dismissed", "terminate"],
    "fired":          ["terminated", "dismissed", "termination"],
    "bonus":          ["incentive", "reward", "allowance"],
    "wfh":            ["remote work", "work from home", "remote"],
    "work from home": ["remote work", "wfh", "remote"],
    "promotion":      ["career growth", "advancement", "rating"],
}

_STOP = {
    "the", "and", "for", "are", "was", "were", "this", "that", "with",
    "have", "from", "they", "will", "what", "how", "when", "who", "can",
    "does", "did", "its", "per", "any", "all", "not", "but", "also",
    "their", "which", "has", "been", "should", "must", "may", "into",
    "according", "based", "give", "get", "make", "take",
}


# ── Chunk building ────────────────────────────────────────────────────────────

def _build_chunks(documents: list[dict]) -> list[dict]:
    chunks = []
    for doc in documents:
        paragraphs = [p.strip() for p in doc["content"].split("\n\n") if p.strip()]
        for para in paragraphs:
            chunks.append({"source": doc["title"], "text": para})
    return chunks


# ── Embedding helpers ─────────────────────────────────────────────────────────

def _get_embed_client():
    from openai import AzureOpenAI
    return AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    )


def _embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts in batches of 16. Returns (n, dim) array."""
    client  = _get_embed_client()
    vectors = []
    batch_size = 16
    for i in range(0, len(texts), batch_size):
        batch    = texts[i : i + batch_size]
        response = client.embeddings.create(
            input=batch,
            model=os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "").strip()
        )
        vectors.extend([item.embedding for item in response.data])
    return np.array(vectors, dtype=np.float32)


def _cosine_sim(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between a single query vector and a matrix of vectors."""
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    norms  = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
    normed = matrix / norms
    return normed @ q_norm


# ── TF-IDF helpers ────────────────────────────────────────────────────────────

def _expand_query(query: str) -> str:
    q_lower = query.lower()
    extras  = []
    for term, synonyms in _SYNONYMS.items():
        if term in q_lower:
            extras.extend(synonyms)
    for word in re.findall(r"\b\w+\b", q_lower):
        if word in _SYNONYMS:
            extras.extend(_SYNONYMS[word])
    return (query + " " + " ".join(extras)) if extras else query


def _keyword_overlap(query: str, chunk_text: str) -> float:
    words = {w.lower() for w in re.findall(r"\b\w{3,}\b", query)} - _STOP
    if not words:
        return 0.0
    chunk_lower = chunk_text.lower()
    return sum(1 for w in words if w in chunk_lower) / len(words)


# ── Index building ────────────────────────────────────────────────────────────

def _build_index(documents: list[dict]):
    global _vectorizer, _tfidf_matrix, _chunk_embeddings, _chunks
    _chunks = _build_chunks(documents)
    texts   = [c["text"] for c in _chunks]

    if _use_embedding():
        deploy = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "").strip()
        print(f"[Retriever] Building EMBEDDING index ({len(_chunks)} chunks) "
              f"using deployment: {deploy}")
        try:
            _chunk_embeddings = _embed_texts(texts)
            print(f"[Retriever] Embedding index ready — shape {_chunk_embeddings.shape}")
        except Exception as e:
            print(f"[Retriever] Embedding failed ({e}). Falling back to TF-IDF.")
            _chunk_embeddings = None
            _build_tfidf(texts)
    else:
        print(f"[Retriever] Building TF-IDF index ({len(_chunks)} chunks)")
        _build_tfidf(texts)


def _build_tfidf(texts: list[str]):
    global _vectorizer, _tfidf_matrix
    _vectorizer   = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    _tfidf_matrix = _vectorizer.fit_transform(texts)


def reload():
    """Rebuild index from current document store."""
    from rag_app.document_store import get_all_documents
    _build_index(get_all_documents())


def _ensure_index():
    if not _chunks:
        reload()


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str, top_k: int = 4,
             score_threshold_ratio: float = 0.35) -> list[dict]:
    _ensure_index()

    if _use_embedding() and _chunk_embeddings is not None:
        return _retrieve_embedding(query, top_k, score_threshold_ratio)
    return _retrieve_tfidf(query, top_k, score_threshold_ratio)


def _retrieve_embedding(query: str, top_k: int,
                        score_threshold_ratio: float) -> list[dict]:
    try:
        query_vec = _embed_texts([query])[0]
        scores    = _cosine_sim(query_vec, _chunk_embeddings)

        top_idx = np.argsort(scores)[::-1][:top_k * 4]
        candidates = [
            {
                "source": _chunks[i]["source"],
                "text":   _chunks[i]["text"],
                "score":  float(scores[i]),
            }
            for i in top_idx if scores[i] > 0
        ]
    except Exception as e:
        print(f"[Retriever] Embedding retrieval error ({e}). Falling back to TF-IDF.")
        return _retrieve_tfidf(query, top_k, score_threshold_ratio)

    return _apply_threshold(candidates, top_k, score_threshold_ratio)


def _retrieve_tfidf(query: str, top_k: int,
                    score_threshold_ratio: float) -> list[dict]:
    if _vectorizer is None:
        _build_tfidf([c["text"] for c in _chunks])

    expanded  = _expand_query(query)
    query_vec = _vectorizer.transform([expanded])
    scores    = _sklearn_cosine(query_vec, _tfidf_matrix).flatten()

    candidate_k = min(top_k * 4, len(_chunks))
    top_idx     = np.argsort(scores)[::-1][:candidate_k]

    candidates = []
    for idx in top_idx:
        if scores[idx] <= 0:
            continue
        kw    = _keyword_overlap(query, _chunks[idx]["text"])
        combined = 0.65 * float(scores[idx]) + 0.35 * kw
        candidates.append({
            "source": _chunks[idx]["source"],
            "text":   _chunks[idx]["text"],
            "score":  combined,
        })
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return _apply_threshold(candidates, top_k, score_threshold_ratio)


def _apply_threshold(candidates: list[dict], top_k: int,
                     ratio: float) -> list[dict]:
    if not candidates:
        return []
    min_score = candidates[0]["score"] * ratio
    results   = []
    for c in candidates:
        if len(results) >= top_k:
            break
        if c["score"] < min_score:
            break
        results.append({
            "source": c["source"],
            "text":   c["text"],
            "score":  round(c["score"], 4),
        })
    return results
