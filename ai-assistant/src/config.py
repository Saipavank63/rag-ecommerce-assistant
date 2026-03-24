from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "ai-assistant-group"
    kafka_order_topic: str = "order-events"
    kafka_product_topic: str = "product-events"

    # Weaviate
    weaviate_url: str = "http://localhost:8081"
    weaviate_collection: str = "Product"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Order Service
    order_service_url: str = "http://localhost:8080"

    # RAG
    similarity_top_k: int = 5
    hybrid_alpha: float = 0.5  # 0 = pure BM25, 1 = pure vector

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
