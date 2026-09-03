"""
One-time (or on-demand) script to build the RAG vector index from the
knowledge documents in app/knowledge/.

Run this manually whenever the knowledge documents change:
    python scripts/build_index.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.rag import rag_service  # noqa: E402


def main() -> None:
    print("Building RAG knowledge index...")
    collection = rag_service.build_index()
    count = collection.count()
    print(f"Done. Indexed {count} chunks into Chroma collection.")


if __name__ == "__main__":
    main()