import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


_vectorizer = None
_matrix     = None
_chunks     = []

# Synonym map for common policy terms that differ between questions and documents
_SYNONYMS = {
    "training":      ["learning", "professional development", "education", "courses"],
    "educational":   ["learning", "training", "professional development"],
    "expenses":      ["budget", "reimbursement", "allowance", "costs", "claims"],
    "expense":       ["budget", "reimbursement", "allowance", "cost", "claim"],
    "vacation":      ["annual leave", "leave", "holiday", "paid leave"],
    "sick":          ["medical", "illness", "health", "unwell"],
    "pay":           ["salary", "compensation", "remuneration"],
    "raise":         ["salary increase", "increment", "merit increase"],
    "fire":          ["termination", "dismissed", "terminate"],
    "fired":         ["terminated", "dismissed", "termination"],
    "bonus":         ["incentive", "reward", "allowance"],
    "work from home": ["remote work", "remote", "wfh"],
    "wfh":           ["remote work", "work from home", "remote"],
    "promotion":     ["career growth", "advancement", "rating"],
    "annual budget": ["yearly budget", "per year", "each year", "annual learning budget"],
}

_STOP = {
    "the", "and", "for", "are", "was", "were", "this", "that", "with",
    "have", "from", "they", "will", "what", "how", "when", "who", "can",
    "does", "did", "its", "per", "any", "all", "not", "but", "also",
    "their", "which", "has", "been", "should", "must", "may", "into",
    "according", "based", "give", "get", "make", "take",
}


def _expand_query(query: str) -> str:
    """Add synonym expansions so TF-IDF can bridge word mismatches."""
    q_lower = query.lower()
    extras  = []

    # Multi-word synonyms first
    for term, synonyms in _SYNONYMS.items():
        if term in q_lower:
            extras.extend(synonyms)

    # Single-word synonyms
    for word in re.findall(r"\b\w+\b", q_lower):
        if word in _SYNONYMS:
            extras.extend(_SYNONYMS[word])

    if extras:
        return query + " " + " ".join(extras)
    return query


def _keyword_overlap(query: str, chunk_text: str) -> float:
    """Fraction of meaningful query words that appear in the chunk."""
    words = {w.lower() for w in re.findall(r"\b\w{3,}\b", query)} - _STOP
    if not words:
        return 0.0
    chunk_lower = chunk_text.lower()
    hits = sum(1 for w in words if w in chunk_lower)
    return hits / len(words)


def _build_chunks(documents: list[dict]) -> list[dict]:
    chunks = []
    for doc in documents:
        paragraphs = [p.strip() for p in doc["content"].split("\n\n") if p.strip()]
        for para in paragraphs:
            chunks.append({"source": doc["title"], "text": para})
    return chunks


def _build_index(documents: list[dict]):
    global _vectorizer, _matrix, _chunks
    _chunks     = _build_chunks(documents)
    texts       = [c["text"] for c in _chunks]
    _vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    _matrix     = _vectorizer.fit_transform(texts)


def reload():
    """Rebuild index from current document store (call after upload)."""
    from rag_app.document_store import get_all_documents
    _build_index(get_all_documents())


def _ensure_index():
    if _vectorizer is None:
        reload()


def retrieve(query: str, top_k: int = 6) -> list[dict]:
    _ensure_index()

    # Expand query with synonyms to bridge vocabulary gaps
    expanded_query = _expand_query(query)

    query_vec = _vectorizer.transform([expanded_query])
    scores    = cosine_similarity(query_vec, _matrix).flatten()

    # Pull a larger candidate pool before re-ranking
    candidate_k = min(top_k * 3, len(_chunks))
    top_idx     = np.argsort(scores)[::-1][:candidate_k]

    candidates = []
    for idx in top_idx:
        if scores[idx] <= 0:
            continue
        kw_score = _keyword_overlap(query, _chunks[idx]["text"])
        # Combined: TF-IDF similarity weighted higher, keyword overlap as tiebreaker
        combined = 0.65 * float(scores[idx]) + 0.35 * kw_score
        candidates.append({
            "source":   _chunks[idx]["source"],
            "text":     _chunks[idx]["text"],
            "score":    float(scores[idx]),
            "combined": combined,
        })

    candidates.sort(key=lambda x: x["combined"], reverse=True)

    results = []
    for c in candidates[:top_k]:
        results.append({
            "source": c["source"],
            "text":   c["text"],
            "score":  round(c["combined"], 4),
        })
    return results
