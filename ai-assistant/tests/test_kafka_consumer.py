"""Tests for Kafka event deserialization and routing logic.

These tests exercise the ``OrderEventConsumer`` without a live Kafka broker
by feeding raw message dicts directly into the handler methods.
"""

import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.kafka_consumer import OrderEventConsumer
from src.models import OrderEvent, ProductEvent


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_indexer():
    indexer = MagicMock()
    indexer.index_single_product = MagicMock()
    return indexer


@pytest.fixture
def consumer(mock_indexer):
    return OrderEventConsumer(indexer=mock_indexer)


# ── Sample payloads (match the Java Kafka producer's JSON schema) ─────────────

def _order_event_payload(
    event_type: str = "ORDER_CREATED",
    order_id: int = 42,
    customer_id: str = "cust-100",
    status: str = "CONFIRMED",
    total_amount: float = 149.99,
    item_count: int = 2,
) -> dict:
    return {
        "eventType": event_type,
        "orderId": order_id,
        "customerId": customer_id,
        "status": status,
        "totalAmount": total_amount,
        "itemCount": item_count,
        "shippingAddress": "123 Test St, Testville",
        "timestamp": int(time.time() * 1000),
    }


def _product_event_payload(
    event_type: str = "PRODUCT_CREATED",
    product_id: int = 7,
    name: str = "Wireless Mouse",
    description: str = "Ergonomic wireless mouse with 2.4 GHz connectivity",
    category: str = "Electronics",
    price: float = 29.99,
) -> dict:
    return {
        "eventType": event_type,
        "productId": product_id,
        "name": name,
        "description": description,
        "category": category,
        "price": price,
        "timestamp": int(time.time() * 1000),
    }


# ── Order event tests ────────────────────────────────────────────────────────

class TestOrderEventDeserialization:
    """Verify that raw JSON dicts deserialize into ``OrderEvent`` correctly."""

    def test_parse_order_created(self):
        payload = _order_event_payload()
        event = OrderEvent(**payload)

        assert event.event_type == "ORDER_CREATED"
        assert event.order_id == 42
        assert event.customer_id == "cust-100"
        assert event.status == "CONFIRMED"
        assert event.total_amount == 149.99
        assert event.item_count == 2
        assert event.shipping_address == "123 Test St, Testville"

    def test_parse_order_status_updated(self):
        payload = _order_event_payload(
            event_type="ORDER_STATUS_UPDATED",
            status="SHIPPED",
        )
        event = OrderEvent(**payload)
        assert event.event_type == "ORDER_STATUS_UPDATED"
        assert event.status == "SHIPPED"

    def test_missing_optional_shipping_address(self):
        payload = _order_event_payload()
        del payload["shippingAddress"]
        event = OrderEvent(**payload)
        assert event.shipping_address is None


class TestOrderEventRouting:
    """Verify the consumer stores order events and routes them correctly."""

    def test_handle_order_event_stores_in_recent(self, consumer):
        payload = _order_event_payload(order_id=99)
        consumer._handle_order_event(payload)

        stored = consumer.get_recent_order(99)
        assert stored is not None
        assert stored.order_id == 99
        assert stored.event_type == "ORDER_CREATED"

    def test_handle_multiple_orders(self, consumer):
        consumer._handle_order_event(_order_event_payload(order_id=1))
        consumer._handle_order_event(_order_event_payload(order_id=2))
        consumer._handle_order_event(_order_event_payload(order_id=3))

        assert consumer.get_recent_order(1) is not None
        assert consumer.get_recent_order(2) is not None
        assert consumer.get_recent_order(3) is not None

    def test_later_event_overwrites_earlier(self, consumer):
        consumer._handle_order_event(
            _order_event_payload(order_id=10, status="CONFIRMED")
        )
        consumer._handle_order_event(
            _order_event_payload(order_id=10, status="SHIPPED",
                                 event_type="ORDER_STATUS_UPDATED")
        )
        stored = consumer.get_recent_order(10)
        assert stored.status == "SHIPPED"

    def test_get_recent_order_returns_none_for_unknown(self, consumer):
        assert consumer.get_recent_order(9999) is None

    def test_malformed_order_event_does_not_raise(self, consumer):
        # Missing required fields — handler should log a warning, not crash.
        consumer._handle_order_event({"garbage": True})
        assert consumer.get_recent_order(0) is None


# ── Product event tests ──────────────────────────────────────────────────────

class TestProductEventDeserialization:
    def test_parse_product_created(self):
        payload = _product_event_payload()
        event = ProductEvent(**payload)

        assert event.event_type == "PRODUCT_CREATED"
        assert event.product_id == 7
        assert event.name == "Wireless Mouse"
        assert event.category == "Electronics"
        assert event.price == 29.99

    def test_optional_fields_default_to_none(self):
        payload = {
            "eventType": "PRODUCT_DELETED",
            "productId": 5,
            "timestamp": int(time.time() * 1000),
        }
        event = ProductEvent(**payload)
        assert event.name is None
        assert event.description is None
        assert event.category is None
        assert event.price is None


class TestProductEventRouting:
    def test_product_created_triggers_indexing(self, consumer, mock_indexer):
        payload = _product_event_payload()
        consumer._handle_product_event(payload)

        mock_indexer.index_single_product.assert_called_once()
        product_doc = mock_indexer.index_single_product.call_args[0][0]
        assert product_doc.name == "Wireless Mouse"
        assert product_doc.category == "Electronics"
        assert product_doc.price == 29.99

    def test_non_create_event_does_not_index(self, consumer, mock_indexer):
        payload = _product_event_payload(event_type="PRODUCT_DELETED")
        consumer._handle_product_event(payload)

        mock_indexer.index_single_product.assert_not_called()

    def test_product_without_description_does_not_index(self, consumer, mock_indexer):
        payload = _product_event_payload()
        payload["description"] = None
        consumer._handle_product_event(payload)

        mock_indexer.index_single_product.assert_not_called()

    def test_malformed_product_event_does_not_raise(self, consumer, mock_indexer):
        consumer._handle_product_event({"not": "a product event"})
        mock_indexer.index_single_product.assert_not_called()


# ── Consumer lifecycle tests ─────────────────────────────────────────────────

class TestConsumerLifecycle:
    def test_initial_state(self, consumer):
        assert consumer._consumer is None
        assert consumer._running is False
        assert consumer.is_connected() is False

    def test_is_connected_when_running(self, consumer):
        consumer._consumer = MagicMock()
        consumer._running = True
        assert consumer.is_connected() is True

    def test_stop_when_not_started_is_safe(self, consumer):
        consumer.stop()  # Should not raise.

    @patch("src.kafka_consumer.Consumer")
    def test_start_creates_background_thread(self, mock_kafka_consumer_cls, consumer):
        mock_instance = MagicMock()
        mock_kafka_consumer_cls.return_value = mock_instance

        consumer.start()
        assert consumer._running is True
        assert consumer._thread is not None
        assert consumer._thread.daemon is True

        # Clean up.
        consumer.stop()
