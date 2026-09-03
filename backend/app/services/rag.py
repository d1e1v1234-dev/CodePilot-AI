"""
RAGService: builds/loads a local Chroma vector store from the
knowledge documents and retrieves relevant context for a given query.

Design:
- Indexing (embedding all knowledge docs) happens once via the
  `scripts/build_index.py` script, or lazily on first use if the
  persisted index doesn't exist yet.
- Retrieval at request time only queries the already-built index —
  it never re-embeds the whole knowledge base per request.
- Any failure (missing index, embedding API error, etc.) is caught by
  the caller (ReviewService) and treated as "no context available",
  never as a hard failure of the review itself.
"""

import os
from dataclasses import dataclass

import chromadb
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")
PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
COLLECTION_NAME = "codepilot_knowledge"

# Human-readable source names, keyed by filename.
SOURCE_NAMES = {
    "python_best_practices.md": "Python Best Practices",
    "python_common_errors.md": "Python Common Errors",
    "owasp_security_basics.md": "OWASP Security Basics",
    "fastapi_best_practices.md": "FastAPI Best Practices",
}


class RAGServiceError(Exception):
    """Raised when the RAG pipeline cannot build or query the index."""


@dataclass
class RetrievedChunk:
    text: str
    source: str
    relevance: float  # 0.0 - 1.0, higher = more relevant


class RAGService:
    def __init__(self) -> None:
        self._collection = None
        self._embeddings: GoogleGenerativeAIEmbeddings | None = None

    def _get_embeddings(self) -> GoogleGenerativeAIEmbeddings:
        if self._embeddings is None:
            if not settings.GEMINI_API_KEY:
                raise RAGServiceError("GEMINI_API_KEY is not configured.")
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.GEMINI_EMBEDDING_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
            )
        return self._embeddings

    def _get_collection(self):
        """
        Lazily open the persisted Chroma collection. If it doesn't
        exist yet, build it on the spot (first-run convenience) —
        after that, it's just loaded from disk, not rebuilt.
        """
        if self._collection is not None:
            return self._collection

        client = chromadb.PersistentClient(path=PERSIST_DIR)

        try:
            collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            collection = self.build_index(client=client)

        self._collection = collection
        return self._collection

    def _load_and_chunk_documents(self) -> list[dict]:
        """
        Load every .md file in the knowledge directory and split it
        into overlapping chunks for embedding.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
        )

        chunks: list[dict] = []
        for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(KNOWLEDGE_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                raw_text = f.read()

            source_name = SOURCE_NAMES.get(filename, filename)

            for i, chunk_text in enumerate(splitter.split_text(raw_text)):
                chunks.append(
                    {
                        "id": f"{filename}-{i}",
                        "text": chunk_text,
                        "source": source_name,
                    }
                )

        return chunks

    def build_index(self, client: chromadb.ClientAPI | None = None):
        """
        Build (or rebuild) the vector store from the knowledge docs.
        This is the only place embeddings are computed for the whole
        knowledge base. Safe to call manually via the indexing script.
        """
        if client is None:
            client = chromadb.PersistentClient(path=PERSIST_DIR)

        # Drop any existing collection so re-running is idempotent.
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        collection = client.create_collection(COLLECTION_NAME)

        chunks = self._load_and_chunk_documents()
        if not chunks:
            raise RAGServiceError("No knowledge documents found to index.")

        embeddings_model = self._get_embeddings()
        texts = [c["text"] for c in chunks]

        vectors = embeddings_model.embed_documents(texts)

        collection.add(
            ids=[c["id"] for c in chunks],
            documents=texts,
            embeddings=vectors,
            metadatas=[{"source": c["source"]} for c in chunks],
        )

        self._collection = collection
        return collection

    def retrieve(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        """
        Retrieve the top_k most relevant knowledge chunks for the
        given query (e.g. the user's submitted code).

        Raises:
            RAGServiceError: if the index or embedding call fails.
        """
        if not query or not query.strip():
            return []

        collection = self._get_collection()
        embeddings_model = self._get_embeddings()

        try:
            query_vector = embeddings_model.embed_query(query)
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
            )
        except Exception as exc:  # noqa: BLE001
            raise RAGServiceError("Failed to retrieve knowledge context.") from exc

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks: list[RetrievedChunk] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # Chroma returns a distance (lower = more similar) for the
            # default cosine/L2 space; convert to a 0-1 relevance score.
            relevance = max(0.0, min(1.0, 1.0 - dist))
            chunks.append(
                RetrievedChunk(
                    text=doc,
                    source=meta.get("source", "Unknown"),
                    relevance=round(relevance, 2),
                )
            )

        return chunks


# Single shared instance used across the app.
rag_service = RAGService()