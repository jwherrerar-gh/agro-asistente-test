from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.domain.ports.output.vector_store_port import VectorRecord, VectorSearchHit, VectorStorePort

DEFAULT_COLLECTION = "agro_knowledge_pmv1"


class QdrantVectorStoreAdapter(VectorStorePort):
    """Adaptador concreto de VectorStorePort sobre Qdrant Cloud."""

    def __init__(
        self,
        url: str,
        api_key: str,
        collection_name: str = DEFAULT_COLLECTION,
        vector_size: int = 128,
        client: QdrantClient | None = None,
    ) -> None:
        self._url = (url or "").strip()
        self._api_key = (api_key or "").strip()
        self._collection_name = (collection_name or DEFAULT_COLLECTION).strip() or DEFAULT_COLLECTION
        self._vector_size = int(vector_size or 128)
        self._client = client or QdrantClient(url=self._url, api_key=self._api_key, timeout=30)
        self._ensure_collection()

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def _ensure_collection(self) -> None:
        self._client.get_or_create_collection(
            collection_name=self._collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=self._vector_size,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        points = [
            qdrant_models.PointStruct(
                id=str(record.id),
                vector=list(record.embedding),
                payload={
                    "content": record.content,
                    "document_id": str(record.metadata.get("document_id", "")),
                    "document_title": str(record.metadata.get("document_title", "")),
                    "topic": str(record.metadata.get("topic", "")),
                    "content_hash": str(record.metadata.get("content_hash", "")),
                    "chunk_index": int(record.metadata.get("chunk_index", 0) or 0),
                    "source_path": str(record.metadata.get("source_path", "")),
                    **{key: _qdrant_scalar(value) for key, value in record.metadata.items()},
                },
            )
            for record in records
        ]
        self._client.upsert(collection_name=self._collection_name, points=points)

    def similarity_search(self, embedding: list[float], top_k: int) -> list[VectorSearchHit]:
        if top_k < 1 or not embedding:
            return []
        results = self._client.search(
            collection_name=self._collection_name,
            query_vector=list(embedding),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        hits: list[VectorSearchHit] = []
        for item in results:
            payload = item.payload or {}
            hits.append(
                VectorSearchHit(
                    id=str(item.id),
                    content=str(payload.get("content") or ""),
                    metadata={
                        key: _python_scalar(value)
                        for key, value in payload.items()
                        if key not in {"content"}
                    },
                    similarity=float(item.score or 0.0),
                )
            )
        return hits


def _qdrant_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _python_scalar(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
