import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from src.config import settings
from src.kafka_consumer import OrderEventConsumer
from src.models import ChatRequest, ChatResponse, HealthResponse
from src.rag.assistant import ECommerceAssistant
from src.rag.indexer import ProductIndexer
from src.rag.retriever import HybridRetriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Shared instances -- initialized on startup, torn down on shutdown.
indexer = ProductIndexer()
retriever = HybridRetriever()
assistant = ECommerceAssistant(retriever)
consumer = OrderEventConsumer(indexer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting AI Assistant service")
    try:
        consumer.start()
        logger.info("Kafka consumer started")
    except Exception as e:
        logger.warning("Could not start Kafka consumer (will retry on messages): %s", e)

    yield

    # Shutdown
    logger.info("Shutting down AI Assistant service")
    consumer.stop()
    indexer.close()
    retriever.close()


app = FastAPI(
    title="E-Commerce AI Assistant",
    description="RAG-powered assistant for product recommendations and order explanations",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Ask the AI assistant a question about products or orders."""
    try:
        response = await assistant.chat(request.message, request.user_id)
        return response
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process your question")


@app.post("/index/products")
async def index_products():
    """Trigger a full re-index of the product catalog from the order service."""
    try:
        products = await indexer.fetch_products()
        count = indexer.index_products(products)
        return {"indexed": count, "status": "ok"}
    except Exception as e:
        logger.error("Indexing error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Service health check."""
    return HealthResponse(
        status="ok",
        weaviate_connected=retriever.is_connected(),
        kafka_connected=consumer.is_connected(),
    )
