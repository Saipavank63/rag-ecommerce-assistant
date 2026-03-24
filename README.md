# RAG-Powered E-Commerce Assistant

An event-driven e-commerce platform with an AI assistant that provides product recommendations and order status explanations using Retrieval-Augmented Generation (RAG) over a Weaviate vector store.

## Architecture

```
                                  +-------------------+
                                  |   Client / API    |
                                  +--------+----------+
                                           |
                          +----------------+----------------+
                          |                                 |
                 +--------v---------+            +----------v----------+
                 |  Order Service   |            |    AI Assistant     |
                 |  (Spring Boot)   |            |  (FastAPI + RAG)    |
                 +--------+---------+            +----------+----------+
                          |                                 |
                          |    +-------------+              |
                          +--->|    Kafka    |<-------------+
                               |  (Events)  |
                               +-------------+
                          |                                 |
                 +--------v---------+            +----------v----------+
                 |   PostgreSQL     |            |     Weaviate        |
                 |  (Orders, OLTP)  |            |  (Vector Store)     |
                 +------------------+            +---------------------+
```

## Features

- **Event-Driven Order Processing** -- Orders flow through Kafka topics, decoupling the write path from downstream consumers.
- **RAG-Powered Product Recommendations** -- LlamaIndex queries a Weaviate vector store to find semantically similar products based on user intent.
- **Cross-Encoder Reranking** -- Optional second-stage reranking with a cross-encoder model for higher precision results.
- **Natural Language Order Explanations** -- Ask the assistant about your order status and get a human-friendly explanation instead of raw JSON.
- **Hybrid Search** -- Combines dense vector similarity with BM25 keyword matching in Weaviate for better retrieval accuracy.
- **Structured Error Handling** -- Global exception handler returns consistent JSON error responses with status codes and field-level validation details.
- **Kubernetes Autoscaling** -- HPA configuration scales the payment/order service based on CPU utilization during peak load.

## Tech Stack

| Layer           | Technology                        |
|-----------------|-----------------------------------|
| Order Service   | Java 17, Spring Boot 3, JPA       |
| Messaging       | Apache Kafka                      |
| AI Assistant    | Python 3.11, FastAPI, LlamaIndex  |
| Reranking       | sentence-transformers (cross-encoder) |
| Vector Store    | Weaviate                          |
| Database        | PostgreSQL 15                     |
| Orchestration   | Kubernetes, Docker Compose        |

## Project Structure

```
rag-ecommerce-assistant/
├── order-service/            # Spring Boot microservice
│   ├── src/main/java/...     # Controllers, services, models, exceptions
│   ├── src/test/java/...     # Unit + MockMvc integration tests
│   ├── Dockerfile
│   └── pom.xml
├── ai-assistant/             # Python RAG service
│   ├── src/
│   │   ├── main.py           # FastAPI application
│   │   ├── rag/              # Indexer, retriever, reranker, assistant
│   │   ├── kafka_consumer.py
│   │   └── models.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── k8s/                      # Kubernetes manifests
│   ├── order-service-deployment.yml
│   ├── ai-assistant-deployment.yml
│   └── hpa.yml
├── Makefile                  # Build, test, and run targets
├── .env.example              # Environment variable template
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Java 17+ (for local order-service development)
- Python 3.11+ (for local ai-assistant development)
- An OpenAI API key (set as `OPENAI_API_KEY`)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/rag-ecommerce-assistant.git
cd rag-ecommerce-assistant

# Copy and edit the environment template
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start the full stack
make docker-up
```

Services will be available at:
- Order Service API: `http://localhost:8080`
- AI Assistant API: `http://localhost:8000`
- Weaviate: `http://localhost:8081`

### Running Locally

**Order Service:**
```bash
make run-order
# or: cd order-service && ./mvnw spring-boot:run
```

**AI Assistant:**
```bash
make run-ai
# or: cd ai-assistant && uvicorn src.main:app --reload --port 8000
```

### Running Tests

```bash
# Run all tests
make test-all

# Run order-service tests only
make test-order

# Run AI assistant tests only
make test-ai
```

## API Reference

### Order Service (`localhost:8080`)

| Method  | Endpoint                   | Description              | Request Body                        | Response           |
|---------|----------------------------|--------------------------|-------------------------------------|--------------------|
| POST    | `/api/orders`              | Create a new order       | `OrderRequest` (JSON)               | `201` OrderResponse |
| GET     | `/api/orders/{id}`         | Get order by ID          | --                                  | `200` OrderResponse |
| GET     | `/api/orders`              | List all orders          | --                                  | `200` OrderResponse[] |
| GET     | `/api/orders?customerId=X` | List orders by customer  | --                                  | `200` OrderResponse[] |
| PATCH   | `/api/orders/{id}/status`  | Update order status      | `{"status": "PROCESSING"}`          | `200` OrderResponse |
| POST    | `/api/products`            | Create a product         | `Product` (JSON)                    | `201` Product      |
| GET     | `/api/products`            | List products            | --                                  | `200` Product[]    |
| GET     | `/api/products/{id}`       | Get product by ID        | --                                  | `200` Product      |
| GET     | `/api/products/search?q=X` | Search products by name  | --                                  | `200` Product[]    |

**Create order example:**
```json
POST /api/orders
{
  "customerId": "cust-123",
  "shippingAddress": "123 Main St, Springfield",
  "items": [
    { "productId": 1, "quantity": 2 },
    { "productId": 3, "quantity": 1 }
  ]
}
```

**Error response format:**
```json
{
  "status": 404,
  "error": "Not Found",
  "message": "Order not found: 999",
  "path": "/api/orders/999",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### AI Assistant (`localhost:8000`)

| Method | Endpoint                 | Description                             | Request Body            | Response             |
|--------|--------------------------|-----------------------------------------|-------------------------|----------------------|
| POST   | `/chat`                  | Ask the assistant a question            | `ChatRequest` (JSON)    | `200` ChatResponse   |
| POST   | `/index/products`        | Trigger product catalog indexing         | --                      | `200` IndexResult    |
| GET    | `/health`                | Health check                            | --                      | `200` HealthResponse |

**Chat example:**
```json
POST /chat
{
  "message": "I'm looking for a lightweight laptop for travel",
  "user_id": "user-123"
}
```

**Response:**
```json
{
  "response": "Based on our catalog, I'd recommend the UltraBook Air...",
  "sources": ["UltraBook Air", "TravelPro Slim"],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Environment Variables

| Variable                      | Service       | Default                                  | Description                            |
|-------------------------------|---------------|------------------------------------------|----------------------------------------|
| `OPENAI_API_KEY`              | AI Assistant  | --                                       | OpenAI API key (required)              |
| `OPENAI_MODEL`                | AI Assistant  | `gpt-4o-mini`                            | Chat completion model                  |
| `OPENAI_EMBEDDING_MODEL`      | AI Assistant  | `text-embedding-3-small`                 | Embedding model for vector search      |
| `KAFKA_BOOTSTRAP_SERVERS`     | Both          | `localhost:9092`                         | Kafka broker connection string         |
| `WEAVIATE_URL`                | AI Assistant  | `http://localhost:8081`                  | Weaviate vector store URL              |
| `WEAVIATE_COLLECTION`         | AI Assistant  | `Product`                                | Weaviate collection name               |
| `ORDER_SERVICE_URL`           | AI Assistant  | `http://localhost:8080`                  | Order service base URL                 |
| `SIMILARITY_TOP_K`            | AI Assistant  | `5`                                      | Number of candidates to retrieve       |
| `HYBRID_ALPHA`                | AI Assistant  | `0.5`                                    | Blend ratio (0=BM25, 1=vector)         |
| `RERANKER_ENABLED`            | AI Assistant  | `false`                                  | Enable cross-encoder reranking         |
| `RERANKER_MODEL`              | AI Assistant  | `cross-encoder/ms-marco-MiniLM-L-6-v2`  | Cross-encoder model name               |
| `RERANKER_TOP_N`              | AI Assistant  | `3`                                      | Results to keep after reranking        |
| `SPRING_DATASOURCE_URL`       | Order Service | `jdbc:postgresql://localhost:5432/ecommerce` | PostgreSQL JDBC URL               |
| `SPRING_DATASOURCE_USERNAME`  | Order Service | `ecommerce`                              | Database username                      |
| `SPRING_DATASOURCE_PASSWORD`  | Order Service | `ecommerce`                              | Database password                      |

## Order Status Flow

```
PENDING  -->  CONFIRMED  -->  PROCESSING  -->  SHIPPED  -->  DELIVERED  -->  REFUNDED
   |              |                |
   +--> CANCELLED +---> CANCELLED +---> CANCELLED
```

## Kubernetes Deployment

```bash
# Apply all manifests
kubectl apply -f k8s/

# Verify HPA is active
kubectl get hpa
```

The HPA scales the order-service between 2 and 10 replicas based on CPU utilization, targeting 60% average usage.

## Troubleshooting

### Docker Compose startup issues

| Problem                            | Cause                                      | Fix                                                  |
|------------------------------------|--------------------------------------------|------------------------------------------------------|
| `ai-assistant` exits immediately   | Missing `OPENAI_API_KEY`                   | Set in `.env` or export before `docker-compose up`   |
| Kafka connection refused           | Kafka not ready when services start        | Restart: `make docker-down && make docker-up`        |
| Weaviate timeout                   | gRPC port 50051 not exposed                | Ensure `docker-compose.yml` maps `50051:50051`       |
| Order service DB error             | Postgres not ready or wrong credentials    | Check `SPRING_DATASOURCE_*` variables                |

### AI Assistant issues

| Problem                            | Cause                                      | Fix                                                  |
|------------------------------------|--------------------------------------------|------------------------------------------------------|
| Empty retrieval results            | Products not indexed yet                   | Call `POST /index/products` after adding products    |
| Slow first query                   | Reranker loading cross-encoder model       | Expected on first request; subsequent queries faster |
| `sentence-transformers` not found  | Missing dependency                         | Run `pip install sentence-transformers`              |
| Kafka consumer not receiving events| Wrong topic name or broker address         | Check `KAFKA_*` env vars match `docker-compose.yml`  |

### Order Service issues

| Problem                            | Cause                                      | Fix                                                  |
|------------------------------------|--------------------------------------------|------------------------------------------------------|
| 409 Insufficient Stock             | Product stock below requested quantity     | Check stock via `GET /api/products/{id}`             |
| 409 Invalid Status Transition      | Business rule violation                    | See status flow diagram above                        |
| 404 Order Not Found                | Wrong order ID                             | List orders with `GET /api/orders`                   |
| Validation errors (400)            | Missing required fields                    | Check `fieldErrors` in the response body             |

## License

MIT
