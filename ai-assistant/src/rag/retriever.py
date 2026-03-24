import logging
from typing import Optional

import weaviate
import weaviate.classes as wvc
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.weaviate import WeaviateVectorStore

from src.config import settings
from src.rag.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Retrieves product information from Weaviate using hybrid search
    (dense vector + BM25 keyword matching), with optional cross-encoder
    reranking for improved precision.
    """

    def __init__(self):
        self._client: Optional[weaviate.WeaviateClient] = None
        self._index: Optional[VectorStoreIndex] = None
        self._reranker: Optional[CrossEncoderReranker] = None

        if settings.reranker_enabled:
            self._reranker = CrossEncoderReranker(
                model_name=settings.reranker_model,
                top_n=settings.reranker_top_n,
            )
            logger.info(
                "Cross-encoder reranking enabled (model=%s, top_n=%d)",
                settings.reranker_model,
                settings.reranker_top_n,
            )

    def _get_client(self) -> weaviate.WeaviateClient:
        if self._client is None or not self._client.is_connected():
            self._client = weaviate.connect_to_custom(
                http_host=settings.weaviate_url.replace("http://", "").split(":")[0],
                http_port=int(settings.weaviate_url.split(":")[-1]),
                http_secure=False,
                grpc_host=settings.weaviate_url.replace("http://", "").split(":")[0],
                grpc_port=50051,
                grpc_secure=False,
            )
        return self._client

    def _get_index(self) -> VectorStoreIndex:
        if self._index is None:
            client = self._get_client()
            vector_store = WeaviateVectorStore(
                weaviate_client=client,
                index_name=settings.weaviate_collection,
            )
            embed_model = OpenAIEmbedding(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key,
            )
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=embed_model,
            )
        return self._index

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[NodeWithScore]:
        """Run hybrid retrieval combining vector similarity and keyword search.

        When reranking is enabled the first stage over-fetches candidates
        (``top_k * 3``) so the cross-encoder has a richer pool to score,
        then the reranker trims back to the requested ``top_k``.
        """
        k = top_k or settings.similarity_top_k

        # Over-fetch when reranking so the cross-encoder sees more candidates.
        fetch_k = k * 3 if self._reranker is not None else k

        index = self._get_index()
        retriever = index.as_retriever(
            similarity_top_k=fetch_k,
            vector_store_query_mode="hybrid",
            alpha=settings.hybrid_alpha,
        )

        nodes = retriever.retrieve(query)
        logger.info(
            "Retrieved %d nodes for query: '%s' (fetch_k=%d, alpha=%.2f)",
            len(nodes), query[:80], fetch_k, settings.hybrid_alpha,
        )

        if self._reranker is not None:
            nodes = self._reranker.rerank(query, nodes, top_n=k)

        return nodes

    def retrieve_by_category(self, query: str, category: str, top_k: int = 5) -> list[NodeWithScore]:
        """Retrieve products filtered by category using Weaviate metadata filtering."""
        client = self._get_client()
        collection = client.collections.get(settings.weaviate_collection)

        results = collection.query.hybrid(
            query=query,
            alpha=settings.hybrid_alpha,
            limit=top_k,
            filters=wvc.query.Filter.by_property("category").equal(category),
        )

        nodes = []
        for obj in results.objects:
            node = NodeWithScore(
                node=type("Node", (), {
                    "text": obj.properties.get("content", ""),
                    "metadata": obj.properties,
                })(),
                score=obj.metadata.score if obj.metadata and obj.metadata.score else 0.0,
            )
            nodes.append(node)

        logger.info("Retrieved %d products in category '%s'", len(nodes), category)
        return nodes

    def is_connected(self) -> bool:
        try:
            client = self._get_client()
            return client.is_ready()
        except Exception:
            return False

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
