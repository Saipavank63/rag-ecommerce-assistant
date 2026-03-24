import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models import ChatResponse
from src.rag.assistant import ECommerceAssistant
from src.rag.retriever import HybridRetriever


@pytest.fixture
def mock_retriever():
    retriever = MagicMock(spec=HybridRetriever)
    retriever.retrieve.return_value = []
    return retriever


@pytest.fixture
def assistant(mock_retriever):
    return ECommerceAssistant(mock_retriever)


class TestOrderIdExtraction:
    def test_extracts_order_hash(self, assistant):
        assert assistant._extract_order_id("What's the status of order #42?") == 42

    def test_extracts_order_word(self, assistant):
        assert assistant._extract_order_id("Check order 1001 please") == 1001

    def test_extracts_standalone_number(self, assistant):
        assert assistant._extract_order_id("Where is 55?") == 55

    def test_returns_none_for_no_number(self, assistant):
        assert assistant._extract_order_id("Tell me about laptops") is None


class TestMessageRouting:
    @pytest.mark.asyncio
    async def test_order_keywords_route_to_order_handler(self, assistant):
        with patch.object(assistant, "_handle_order_query", new_callable=AsyncMock) as mock_order:
            mock_order.return_value = ChatResponse(response="order info", sources=[])
            await assistant.chat("What is the status of my order?")
            mock_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_product_query_routes_to_product_handler(self, assistant):
        with patch.object(assistant, "_handle_product_query", new_callable=AsyncMock) as mock_product:
            mock_product.return_value = ChatResponse(response="product info", sources=[])
            await assistant.chat("I need a new laptop")
            mock_product.assert_called_once()


class TestProductContext:
    def test_format_product_context_empty(self, assistant):
        result = assistant._format_product_context([])
        assert result == ""

    def test_format_product_context_with_nodes(self, assistant):
        node = MagicMock()
        node.node.text = "Product: Test\nPrice: $10.00"
        node.score = 0.95

        result = assistant._format_product_context([node])
        assert "Test" in result
        assert "0.950" in result


class TestOrderFormatting:
    def test_format_order_json(self, assistant):
        order = {
            "id": 1,
            "status": "SHIPPED",
            "customerId": "cust-1",
            "totalAmount": 99.99,
            "shippingAddress": "123 Main St",
            "items": [
                {
                    "productName": "Widget",
                    "quantity": 2,
                    "unitPrice": 49.995,
                }
            ],
            "createdAt": "2024-01-15T10:00:00Z",
        }
        result = assistant._format_order_json(order)
        assert "Order #1" in result
        assert "SHIPPED" in result
        assert "Widget" in result

    def test_format_orders_list(self, assistant):
        orders = [
            {"id": 1, "status": "SHIPPED", "totalAmount": 50.0, "createdAt": "2024-01-15"},
            {"id": 2, "status": "DELIVERED", "totalAmount": 75.0, "createdAt": "2024-01-16"},
        ]
        result = assistant._format_orders_list(orders)
        assert "Order #1" in result
        assert "Order #2" in result
        assert "Recent orders" in result
