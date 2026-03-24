import logging
from typing import Optional

import httpx
import weaviate
import weaviate.classes as wvc
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.weaviate import WeaviateVectorStore

from src.config import settings
from src.models import ProductDocument

logger = logging.getLogger(__name__)


class ProductIndexer:
    """Indexes the product catalog from the order service into Weaviate."""

    def __init__(self):
        self._client: Optional[weaviate.WeaviateClient] = None
        self._index: Optional[VectorStoreIndex] = None

    def _get_weaviate_client(self) -> weaviate.WeaviateClient:
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

    def _ensure_collection(self):
        """Create the Weaviate collection if it doesn't exist."""
        client = self._get_weaviate_client()
        collection_name = settings.weaviate_collection

        if not client.collections.exists(collection_name):
            client.collections.create(
                name=collection_name,
                vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_openai(
                    model="text-embedding-3-small",
                ),
                properties=[
                    wvc.config.Property(name="product_id", data_type=wvc.config.DataType.INT),
                    wvc.config.Property(name="name", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="description", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="category", data_type=wvc.config.DataType.TEXT),
                    wvc.config.Property(name="price", data_type=wvc.config.DataType.NUMBER),
                    wvc.config.Property(name="content", data_type=wvc.config.DataType.TEXT),
                ],
            )
            logger.info("Created Weaviate collection: %s", collection_name)

    async def fetch_products(self) -> list[ProductDocument]:
        """Fetch the full product catalog from the order service."""
        url = f"{settings.order_service_url}/api/products"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw = response.json()

        products = []
        for item in raw:
            products.append(ProductDocument(
                product_id=item["id"],
                name=item["name"],
                description=item.get("description", ""),
                category=item.get("category", ""),
                price=float(item.get("price", 0)),
            ))
        logger.info("Fetched %d products from order service", len(products))
        return products

    def index_products(self, products: list[ProductDocument]) -> int:
        """Index a list of products into Weaviate via LlamaIndex."""
        self._ensure_collection()
        client = self._get_weaviate_client()

        documents = []
        for p in products:
            doc = Document(
                text=p.to_text(),
                metadata={
                    "product_id": p.product_id,
                    "name": p.name,
                    "category": p.category,
                    "price": p.price,
                },
            )
            documents.append(doc)

        vector_store = WeaviateVectorStore(
            weaviate_client=client,
            index_name=settings.weaviate_collection,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
        embed_model = OpenAIEmbedding(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            transformations=[splitter],
            embed_model=embed_model,
        )

        logger.info("Indexed %d products into Weaviate", len(products))
        return len(products)

    def index_single_product(self, product: ProductDocument):
        """Index or update a single product (used by the Kafka consumer)."""
        self._ensure_collection()
        client = self._get_weaviate_client()

        vector_store = WeaviateVectorStore(
            weaviate_client=client,
            index_name=settings.weaviate_collection,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        embed_model = OpenAIEmbedding(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )

        doc = Document(
            text=product.to_text(),
            metadata={
                "product_id": product.product_id,
                "name": product.name,
                "category": product.category,
                "price": product.price,
            },
        )

        if self._index is None:
            self._index = VectorStoreIndex.from_documents(
                [doc],
                storage_context=storage_context,
                embed_model=embed_model,
            )
        else:
            self._index.insert(doc)

        logger.info("Indexed product %d: %s", product.product_id, product.name)

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None
