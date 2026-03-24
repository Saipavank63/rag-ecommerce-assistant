import logging
from typing import Optional

import weaviate
import weaviate.classes as wvc
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.weaviate import WeaviateVectorStore

from src.config import settings

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Retrieves product information from Weaviate using hybrid search
    (dense vector + BM25 keyword matching).
    """

    def __init__(self):
        self._client: Optional[weaviate.WeaviateClient] = None
        self._index: Optional[VectorStoreIndex] = None

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
        """Run hybrid retrieval combining vector similarity and keyword search."""
        k = top_k or settings.similarity_top_k
        index = self._get_index()

        retriever = index.as_retriever(
            similarity_top_k=k,
            vector_store_query_mode="hybrid",
            alpha=settings.hybrid_alpha,
        )

        nodes = retriever.retrieve(query)
        logger.info(
            "Retrieved %d nodes for query: '%s' (top_k=%d, alpha=%.2f)",
            len(nodes), query[:80], k, settings.hybrid_alpha,
        )
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
