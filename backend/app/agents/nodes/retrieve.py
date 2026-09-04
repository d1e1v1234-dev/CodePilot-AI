"""
retrieve_context node: runs RAG retrieval against the existing
RAGService — but ONLY for Python, since the current knowledge base
(PEP 8, Python common errors, OWASP, FastAPI) is Python/backend
specific. Attaching this context to a C++/Java/JS/etc. review would
inject irrelevant or misleading "supporting knowledge" into the
prompt.

For any non-Python language, this node returns an empty context list
so the review proceeds using Gemini's own language-aware knowledge
only, without RAG grounding.
"""

import logging
import time

from app.agents.state import ReviewState
from app.services.rag import rag_service, RAGServiceError

logger = logging.getLogger("codepilot.agents.retrieve")

# The current knowledge base is Python/FastAPI/OWASP-specific. Only
# attach RAG context for languages it actually applies to.
LANGUAGES_WITH_RAG_SUPPORT = {"python"}


def retrieve_context(state: ReviewState) -> ReviewState:
    start = time.perf_counter()
    language = state.get("language", "python")

    if language not in LANGUAGES_WITH_RAG_SUPPORT:
        elapsed = time.perf_counter() - start
        logger.info("[PERF] RAG retrieval: %.2fs", elapsed)
        return {"retrieved_chunks": []}

    code = state.get("code", "")

    try:
        chunks = rag_service.retrieve(code, top_k=4)
    except RAGServiceError:
        chunks = []
    except Exception:  # noqa: BLE001 - never let RAG break the workflow
        chunks = []

    elapsed = time.perf_counter() - start
    logger.info("[PERF] RAG retrieval: %.2fs", elapsed)

    return {"retrieved_chunks": chunks}