import logging
from typing import Optional

import httpx
from llama_index.core import PromptTemplate
from llama_index.core.schema import NodeWithScore
from llama_index.llms.openai import OpenAI

from src.config import settings
from src.models import ChatResponse
from src.rag.retriever import HybridRetriever

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a helpful e-commerce assistant. You help customers find products, \
understand their orders, and make purchase decisions.

When recommending products, use ONLY the product information provided in the context below. \
Do not make up products or prices. If the context doesn't contain relevant products, \
say so honestly.

When explaining order status, interpret the status codes and provide a friendly, \
easy-to-understand explanation of what the status means and what the customer can expect next.
"""

PRODUCT_QA_TEMPLATE = PromptTemplate(
    "You are a helpful e-commerce assistant.\n\n"
    "Product catalog context:\n"
    "-----\n"
    "{context_str}\n"
    "-----\n\n"
    "Customer question: {query_str}\n\n"
    "Based on the product information above, provide helpful recommendations. "
    "Include product names and prices. If no products match, say so honestly."
)

ORDER_EXPLANATION_TEMPLATE = PromptTemplate(
    "You are a helpful e-commerce assistant.\n\n"
    "Order information:\n"
    "-----\n"
    "{context_str}\n"
    "-----\n\n"
    "Customer question: {query_str}\n\n"
    "Explain the order status in a friendly way. Tell the customer what this "
    "status means and what they can expect next."
)


class ECommerceAssistant:
    """LLM assistant that uses RAG to answer product and order questions."""

    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.llm = OpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
            system_prompt=SYSTEM_PROMPT,
        )

    async def chat(self, message: str, user_id: Optional[str] = None) -> ChatResponse:
        """Route the user's message to the appropriate handler."""
        lower = message.lower()

        if any(kw in lower for kw in ["order", "status", "tracking", "shipped", "delivered"]):
            return await self._handle_order_query(message, user_id)
        else:
            return await self._handle_product_query(message)

    async def _handle_product_query(self, query: str) -> ChatResponse:
        """Use RAG to find relevant products and generate a recommendation."""
        nodes = self.retriever.retrieve(query)

        if not nodes:
            response_text = (
                "I couldn't find any products matching your query in our catalog. "
                "Could you try rephrasing or being more specific about what you're looking for?"
            )
            return ChatResponse(response=response_text, sources=[])

        context = self._format_product_context(nodes)
        sources = self._extract_sources(nodes)

        prompt = PRODUCT_QA_TEMPLATE.format(context_str=context, query_str=query)
        response = self.llm.complete(prompt)

        return ChatResponse(
            response=str(response),
            sources=sources,
        )

    async def _handle_order_query(self, query: str, user_id: Optional[str] = None) -> ChatResponse:
        """Fetch order data from the order service and explain it."""
        order_context = await self._fetch_order_context(query, user_id)

        if order_context is None:
            # Fall back to product search if no order context found
            return await self._handle_product_query(query)

        prompt = ORDER_EXPLANATION_TEMPLATE.format(
            context_str=order_context,
            query_str=query,
        )
        response = self.llm.complete(prompt)

        return ChatResponse(
            response=str(response),
            sources=["order-service"],
        )

    async def _fetch_order_context(self, query: str, user_id: Optional[str] = None) -> Optional[str]:
        """Try to fetch order information from the order service."""
        # Extract order ID from the query if present
        order_id = self._extract_order_id(query)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if order_id:
                    resp = await client.get(
                        f"{settings.order_service_url}/api/orders/{order_id}"
                    )
                    if resp.status_code == 200:
                        return self._format_order_json(resp.json())

                if user_id:
                    resp = await client.get(
                        f"{settings.order_service_url}/api/orders",
                        params={"customerId": user_id},
                    )
                    if resp.status_code == 200:
                        orders = resp.json()
                        if orders:
                            return self._format_orders_list(orders)
        except httpx.RequestError as e:
            logger.warning("Failed to reach order service: %s", e)

        return None

    @staticmethod
    def _extract_order_id(query: str) -> Optional[int]:
        """Try to find an order ID number in the query string."""
        import re
        match = re.search(r"(?:order\s*#?\s*|#)(\d+)", query, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Also try standalone numbers if the query is about orders
        match = re.search(r"\b(\d{1,10})\b", query)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _format_product_context(nodes: list[NodeWithScore]) -> str:
        parts = []
        for i, node in enumerate(nodes, 1):
            text = node.node.text if hasattr(node.node, "text") else str(node.node)
            score = f" (relevance: {node.score:.3f})" if node.score else ""
            parts.append(f"[{i}]{score}\n{text}")
        return "\n\n".join(parts)

    @staticmethod
    def _extract_sources(nodes: list[NodeWithScore]) -> list[str]:
        sources = []
        for node in nodes:
            metadata = getattr(node.node, "metadata", {})
            name = metadata.get("name", "Unknown Product")
            sources.append(name)
        return sources

    @staticmethod
    def _format_order_json(order: dict) -> str:
        items_desc = []
        for item in order.get("items", []):
            items_desc.append(
                f"  - {item.get('productName', 'Unknown')} "
                f"(qty: {item.get('quantity', 0)}, "
                f"${item.get('unitPrice', 0):.2f} each)"
            )
        items_str = "\n".join(items_desc) if items_desc else "  (no items)"

        return (
            f"Order #{order.get('id')}\n"
            f"Status: {order.get('status')}\n"
            f"Customer: {order.get('customerId')}\n"
            f"Total: ${order.get('totalAmount', 0):.2f}\n"
            f"Shipping to: {order.get('shippingAddress', 'N/A')}\n"
            f"Items:\n{items_str}\n"
            f"Created: {order.get('createdAt', 'N/A')}"
        )

    @staticmethod
    def _format_orders_list(orders: list[dict]) -> str:
        parts = []
        for order in orders[:5]:  # Show at most 5 recent orders
            parts.append(
                f"Order #{order.get('id')} — {order.get('status')} — "
                f"${order.get('totalAmount', 0):.2f} — "
                f"{order.get('createdAt', 'N/A')}"
            )
        return "Recent orders:\n" + "\n".join(parts)
