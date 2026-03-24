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
- **Natural Language Order Explanations** -- Ask the assistant about your order status and get a human-friendly explanation instead of raw JSON.
- **Hybrid Search** -- Combines dense vector similarity with BM25 keyword matching in Weaviate for better retrieval accuracy.
- **Kubernetes Autoscaling** -- HPA configuration scales the payment/order service based on CPU utilization during peak load.

## Tech Stack

| Layer           | Technology                        |
|-----------------|-----------------------------------|
| Order Service   | Java 17, Spring Boot 3, JPA       |
| Messaging       | Apache Kafka                      |
| AI Assistant    | Python 3.11, FastAPI, LlamaIndex  |
| Vector Store    | Weaviate                          |
| Database        | PostgreSQL 15                     |
| Orchestration   | Kubernetes, Docker Compose        |

## Project Structure

```
rag-ecommerce-assistant/
├── order-service/          # Spring Boot microservice
│   ├── src/main/java/...   # Controllers, services, models
│   ├── src/test/java/...   # Unit tests
│   ├── Dockerfile
│   └── pom.xml
├── ai-assistant/           # Python RAG service
│   ├── src/
│   │   ├── main.py         # FastAPI application
│   │   ├── rag/            # Indexer, retriever, assistant
│   │   ├── kafka_consumer.py
│   │   └── models.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── k8s/                    # Kubernetes manifests
│   ├── order-service-deployment.yml
│   ├── ai-assistant-deployment.yml
│   └── hpa.yml
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Java 17+ (for local order-service development)
- Python 3.11+ (for local ai-assistant development)
- An OpenAI API key (set as `OPENAI_API_KEY`)

### Running with Docker Compose

```bash
# Clone the repository
git clone https://github.com/yourusername/rag-ecommerce-assistant.git
cd rag-ecommerce-assistant

# Set your OpenAI API key
export OPENAI_API_KEY=sk-...

# Start the full stack
docker-compose up --build
```

Services will be available at:
- Order Service API: `http://localhost:8080`
- AI Assistant API: `http://localhost:8000`
- Weaviate: `http://localhost:8081`

### Running Locally

**Order Service:**
```bash
cd order-service
./mvnw spring-boot:run
```

**AI Assistant:**
```bash
cd ai-assistant
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

## API Reference

### Order Service

| Method | Endpoint              | Description            |
|--------|-----------------------|------------------------|
| POST   | `/api/orders`         | Create a new order     |
| GET    | `/api/orders/{id}`    | Get order by ID        |
| GET    | `/api/orders`         | List all orders        |
| GET    | `/api/products`       | List products          |
| GET    | `/api/products/{id}`  | Get product by ID      |
| POST   | `/api/products`       | Create a product       |

### AI Assistant

| Method | Endpoint                  | Description                             |
|--------|---------------------------|-----------------------------------------|
| POST   | `/chat`                   | Ask the assistant a question            |
| POST   | `/index/products`         | Trigger product catalog indexing         |
| GET    | `/health`                 | Health check                            |

**Chat example:**
```json
POST /chat
{
  "message": "I'm looking for a lightweight laptop for travel",
  "user_id": "user-123"
}
```

## Kubernetes Deployment

```bash
# Apply all manifests
kubectl apply -f k8s/

# Verify HPA is active
kubectl get hpa
```

The HPA scales the order-service between 2 and 10 replicas based on CPU utilization, targeting 60% average usage.

## License

MIT
