import json
import logging
import threading
from typing import Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

from src.config import settings
from src.models import OrderEvent, ProductDocument, ProductEvent
from src.rag.indexer import ProductIndexer

logger = logging.getLogger(__name__)


class OrderEventConsumer:
    """Consumes order and product events from Kafka topics.

    Product events trigger re-indexing into Weaviate so the RAG assistant
    always has up-to-date catalog data. Order events are logged and stored
    in memory for quick lookups (a production system would use Redis or
    a proper cache here).
    """

    def __init__(self, indexer: ProductIndexer):
        self.indexer = indexer
        self._consumer: Optional[Consumer] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._recent_orders: dict[int, OrderEvent] = {}

    def _create_consumer(self) -> Consumer:
        conf = {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "session.timeout.ms": 30000,
        }
        consumer = Consumer(conf)
        consumer.subscribe([settings.kafka_order_topic, settings.kafka_product_topic])
        return consumer

    def start(self):
        """Start consuming in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        logger.info("Kafka consumer started for topics: %s, %s",
                     settings.kafka_order_topic, settings.kafka_product_topic)

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None
        logger.info("Kafka consumer stopped")

    def _consume_loop(self):
        self._consumer = self._create_consumer()

        while self._running:
            try:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka error: %s", msg.error())
                    continue

                topic = msg.topic()
                value = json.loads(msg.value().decode("utf-8"))

                if topic == settings.kafka_order_topic:
                    self._handle_order_event(value)
                elif topic == settings.kafka_product_topic:
                    self._handle_product_event(value)

            except KafkaException as e:
                logger.error("Kafka consumer exception: %s", e)
            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON message: %s", e)
            except Exception as e:
                logger.error("Unexpected error in consumer loop: %s", e, exc_info=True)

    def _handle_order_event(self, data: dict):
        try:
            event = OrderEvent(**data)
            self._recent_orders[event.order_id] = event
            logger.info("Processed order event: %s for order #%d (status: %s)",
                         event.event_type, event.order_id, event.status)
        except Exception as e:
            logger.warning("Failed to parse order event: %s", e)

    def _handle_product_event(self, data: dict):
        try:
            event = ProductEvent(**data)

            if event.event_type == "PRODUCT_CREATED" and event.name and event.description:
                product = ProductDocument(
                    product_id=event.product_id,
                    name=event.name,
                    description=event.description,
                    category=event.category or "",
                    price=event.price or 0.0,
                )
                self.indexer.index_single_product(product)
                logger.info("Indexed new product from event: %s", event.name)
        except Exception as e:
            logger.warning("Failed to handle product event: %s", e)

    def get_recent_order(self, order_id: int) -> Optional[OrderEvent]:
        return self._recent_orders.get(order_id)

    def is_connected(self) -> bool:
        return self._consumer is not None and self._running
