from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.rag.local_vector_store import LocalVectorStore

logger = get_logger(__name__)

_rag_instance: "RAGKnowledgeEngine | None" = None


class EmbeddingService:
    _instance: "EmbeddingService | None" = None

    def __init__(self) -> None:
        settings = get_settings()
        self.dimension = settings.embedding_dimension
        self._model = None
        self._model_name = settings.embedding_model

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("loading_embedding_model", model=self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class RAGKnowledgeEngine:
    def __init__(self) -> None:
        settings = get_settings()
        self.collection = settings.qdrant_collection
        self.embedder = EmbeddingService.get_instance()
        self.mode = self._resolve_mode(settings)
        self.local_store = LocalVectorStore(settings.local_vector_path)
        self._qdrant = None
        if self.mode == "qdrant":
            self._init_qdrant(settings.qdrant_url)
        logger.info("rag_engine_ready", mode=self.mode)

    @staticmethod
    def _resolve_mode(settings) -> str:
        if settings.vector_store_mode == "local":
            return "local"
        if settings.vector_store_mode == "qdrant":
            return "qdrant"
        try:
            import httpx

            resp = httpx.get(f"{settings.qdrant_url}/readyz", timeout=2.0)
            if resp.status_code == 200:
                return "qdrant"
        except Exception:
            pass
        return "local"

    def _init_qdrant(self, url: str) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        self._qdrant = QdrantClient(url=url)
        collections = [c.name for c in self._qdrant.get_collections().collections]
        if self.collection not in collections:
            self._qdrant.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.embedder.dimension, distance=Distance.COSINE),
            )

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunks.append(" ".join(words[i : i + chunk_size]))
            i += chunk_size - overlap
        return chunks if chunks else [text]

    def index_document(
        self,
        doc_id: int,
        title: str,
        content: str,
        document_type: str,
        equipment_type: str | None = None,
    ) -> int:
        chunks = self.chunk_text(content)
        count = 0
        for idx, chunk in enumerate(chunks):
            vector = self.embedder.embed([chunk])[0]
            payload = {
                "doc_id": doc_id,
                "title": title,
                "document_type": document_type,
                "equipment_type": equipment_type,
                "chunk_index": idx,
                "text": chunk,
            }
            point_id = int(hashlib.md5(f"{doc_id}-{idx}".encode()).hexdigest()[:15], 16)
            if self.mode == "qdrant" and self._qdrant:
                from qdrant_client.http.models import PointStruct

                self._qdrant.upsert(
                    collection_name=self.collection,
                    points=[PointStruct(id=point_id, vector=vector, payload=payload)],
                )
            else:
                self.local_store.upsert(point_id, vector, payload)
            count += 1
        logger.info("document_indexed", doc_id=doc_id, chunks=count, mode=self.mode)
        return count

    def hybrid_search(
        self,
        query: str,
        limit: int = 5,
        document_type: str | None = None,
        equipment_type: str | None = None,
    ) -> list[dict[str, Any]]:
        vector = self.embedder.embed([query])[0]

        if self.mode == "qdrant" and self._qdrant:
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue

            filters = []
            if document_type:
                filters.append(FieldCondition(key="document_type", match=MatchValue(value=document_type)))
            if equipment_type:
                filters.append(FieldCondition(key="equipment_type", match=MatchValue(value=equipment_type)))
            query_filter = Filter(must=filters) if filters else None
            raw = self._qdrant.search(
                collection_name=self.collection,
                query_vector=vector,
                query_filter=query_filter,
                limit=limit * 2,
            )
            hits = [{"score": float(h.score), "payload": h.payload} for h in raw]
        else:
            hits = self.local_store.search(vector, limit * 2, document_type, equipment_type)

        boosted = self._keyword_boost(query, hits)
        return sorted(boosted, key=lambda x: x["score"], reverse=True)[:limit]

    def _keyword_boost(self, query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        query_terms = set(re.findall(r"\w+", query.lower()))
        boosted = []
        for hit in results:
            payload = hit["payload"]
            text = payload.get("text", "").lower()
            term_hits = sum(1 for t in query_terms if t in text)
            boosted.append(
                {
                    "source": payload.get("title", "Unknown"),
                    "document_type": payload.get("document_type", "document"),
                    "equipment_type": payload.get("equipment_type"),
                    "excerpt": payload.get("text", "")[:500],
                    "score": float(hit["score"]) + term_hits * 0.05,
                    "doc_id": payload.get("doc_id"),
                }
            )
        return boosted


def get_rag_engine() -> RAGKnowledgeEngine:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGKnowledgeEngine()
    return _rag_instance


def load_text_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")
