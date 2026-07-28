"""
Run this whenever you change documents.py (add, edit, or remove documents).

What it does:
  1. Clears generated test questions  → will regenerate from new docs on next run
  2. Clears golden reference answers  → will regenerate from new docs on next run
  3. Clears the eval cache            → forces fresh evaluations
  4. Leaves all historical test runs and scores intact

What it does NOT do:
  - Delete your score history (test_runs + evaluations tables are untouched)
  - Touch your .env or any code files
  - Stop a running orchestrator (restart it manually after running this)

Usage:
  1. Edit rag_app/documents.py with your new content
  2. Run:  python reset_for_new_docs.py
  3. Restart the orchestrator: python orchestrator.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "eval_results.db")


def reset():
    if not os.path.exists(DB_PATH):
        print("[Reset] No database found — nothing to clear. Fresh start when orchestrator runs.")
        return

    conn = sqlite3.connect(DB_PATH)

    # Count what we're clearing so user can see the impact
    q_count = conn.execute("SELECT COUNT(*) FROM generated_questions").fetchone()[0]
    g_count = conn.execute("SELECT COUNT(*) FROM golden_answers").fetchone()[0]
    c_count = conn.execute("SELECT COUNT(*) FROM eval_cache").fetchone()[0] if _table_exists(conn, "eval_cache") else 0

    print(f"[Reset] Found:")
    print(f"  {q_count} generated questions  → will be regenerated from new documents")
    print(f"  {g_count} golden answers        → will be regenerated from new documents")
    print(f"  {c_count} cache entries         → will be cleared")
    print()

    conn.execute("DELETE FROM generated_questions")
    conn.execute("DELETE FROM golden_answers")
    if _table_exists(conn, "eval_cache"):
        conn.execute("DELETE FROM eval_cache")
    conn.commit()

    # Verify the TF-IDF index will reload correctly
    from rag_app.document_store import get_all_documents
    docs = get_all_documents()
    total_chars = sum(len(d["content"]) for d in docs)

    conn.close()

    print(f"[Reset] Cleared successfully.")
    print()
    print(f"[Reset] New document set ready:")
    for doc in docs:
        print(f"  - {doc['title']}  ({len(doc['content'])} chars)")
    print(f"  Total: {len(docs)} documents, {total_chars:,} characters")
    print()
    print("[Reset] Next steps:")
    print("  1. Restart the orchestrator:  python orchestrator.py")
    print("  2. On first cycle, it will:")
    print("     - Rebuild the TF-IDF index from your new documents")
    print("     - Probe the agent to discover what it now knows")
    print("     - Generate 15 fresh test questions grounded in new content")
    print("     - Generate new golden reference answers")
    print("  3. Open dashboard:  streamlit run dashboard.py")


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


if __name__ == "__main__":
    reset()
