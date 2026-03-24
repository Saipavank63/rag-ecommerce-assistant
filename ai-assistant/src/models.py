from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProductDocument(BaseModel):
    product_id: int
    name: str
    description: str
    category: str
    price: float

    def to_text(self) -> str:
        return (
            f"Product: {self.name}\n"
            f"Category: {self.category}\n"
            f"Price: ${self.price:.2f}\n"
            f"Description: {self.description}"
        )


class OrderEvent(BaseModel):
    event_type: str = Field(alias="eventType")
    order_id: int = Field(alias="orderId")
    customer_id: str = Field(alias="customerId")
    status: str
    total_amount: float = Field(alias="totalAmount")
    item_count: int = Field(alias="itemCount")
    shipping_address: Optional[str] = Field(None, alias="shippingAddress")
    timestamp: int

    model_config = {"populate_by_name": True}


class ProductEvent(BaseModel):
    event_type: str = Field(alias="eventType")
    product_id: int = Field(alias="productId")
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    timestamp: int

    model_config = {"populate_by_name": True}


class IndexRequest(BaseModel):
    """Request body for triggering product indexing from the order service."""
    pass


class HealthResponse(BaseModel):
    status: str = "ok"
    weaviate_connected: bool = False
    kafka_connected: bool = False
