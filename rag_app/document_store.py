"""
Dynamic document store.
Merges default policy docs with any user-uploaded documents.
Supports per-document enable/disable via active_docs.json.
"""
import os
import json
import hashlib
from rag_app.documents import POLICY_DOCUMENTS

UPLOADS_DIR       = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
UPLOADS_META      = os.path.join(UPLOADS_DIR, "meta.json")
ACTIVE_DOCS_FILE  = os.path.join(UPLOADS_DIR, "active_docs.json")

os.makedirs(UPLOADS_DIR, exist_ok=True)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_meta() -> list[dict]:
    if os.path.exists(UPLOADS_META):
        with open(UPLOADS_META, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_meta(meta: list[dict]):
    with open(UPLOADS_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


# ── Active document selection ─────────────────────────────────────────────────

def get_active_titles() -> set | None:
    """
    Returns the set of enabled document titles, or None if all are active
    (i.e. active_docs.json does not exist yet — backward compatible default).
    """
    if os.path.exists(ACTIVE_DOCS_FILE):
        with open(ACTIVE_DOCS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("active", []))
    return None


def set_active_titles(titles: list[str]):
    """Persist the selected document titles to active_docs.json."""
    with open(ACTIVE_DOCS_FILE, "w", encoding="utf-8") as f:
        json.dump({"active": list(titles)}, f, indent=2)


# ── Document access ───────────────────────────────────────────────────────────

def get_all_documents(active_only: bool = True) -> list[dict]:
    """
    Return default docs + all uploaded docs.
    When active_only=True (default), only returns documents the user has enabled.
    If active_docs.json does not exist, all documents are considered active.
    """
    docs = list(POLICY_DOCUMENTS)
    for entry in _load_meta():
        path = os.path.join(UPLOADS_DIR, entry["filename"])
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            docs.append({"title": entry["title"], "content": content})

    if active_only:
        active = get_active_titles()
        if active is not None:
            docs = [d for d in docs if d["title"] in active]

    return docs


def get_all_documents_unfiltered() -> list[dict]:
    """Return all documents regardless of active selection — used for UI."""
    return get_all_documents(active_only=False)


def add_document(title: str, content: str, original_filename: str) -> dict:
    """Save an uploaded document, register it, and mark it active."""
    file_id   = hashlib.md5(content.encode()).hexdigest()[:8]
    safe_name = f"{file_id}_{original_filename.replace(' ', '_')}.txt"
    path      = os.path.join(UPLOADS_DIR, safe_name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    meta = _load_meta()
    meta = [m for m in meta if m["title"] != title]
    meta.append({"title": title, "filename": safe_name, "original": original_filename})
    _save_meta(meta)

    # Auto-activate the new document
    active = get_active_titles()
    if active is not None:
        active.add(title)
        set_active_titles(list(active))

    return {"title": title, "filename": safe_name}


def remove_document(title: str):
    meta = _load_meta()
    for entry in [m for m in meta if m["title"] == title]:
        path = os.path.join(UPLOADS_DIR, entry["filename"])
        if os.path.exists(path):
            os.remove(path)
    meta = [m for m in meta if m["title"] != title]
    _save_meta(meta)

    # Remove from active list too
    active = get_active_titles()
    if active is not None:
        active.discard(title)
        set_active_titles(list(active))


def get_uploaded_documents() -> list[dict]:
    return _load_meta()


def clear_generated_questions():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import storage
        conn = storage.get_conn()
        conn.execute("DELETE FROM generated_questions")
        conn.execute("DELETE FROM golden_answers")
        conn.commit()
        conn.close()
    except Exception:
        pass
