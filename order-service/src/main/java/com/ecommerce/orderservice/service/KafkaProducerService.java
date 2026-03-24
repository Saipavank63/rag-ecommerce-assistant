package com.ecommerce.orderservice.service;

import com.ecommerce.orderservice.config.KafkaConfig;
import com.ecommerce.orderservice.model.Order;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

@Service
public class KafkaProducerService {

    private static final Logger log = LoggerFactory.getLogger(KafkaProducerService.class);

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    public KafkaProducerService(KafkaTemplate<String, String> kafkaTemplate, ObjectMapper objectMapper) {
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
    }

    public void publishOrderEvent(Order order, String eventType) {
        Map<String, Object> event = new HashMap<>();
        event.put("eventType", eventType);
        event.put("orderId", order.getId());
        event.put("customerId", order.getCustomerId());
        event.put("status", order.getStatus().name());
        event.put("totalAmount", order.getTotalAmount());
        event.put("itemCount", order.getItems().size());
        event.put("shippingAddress", order.getShippingAddress());
        event.put("timestamp", System.currentTimeMillis());

        try {
            String payload = objectMapper.writeValueAsString(event);
            String key = order.getId().toString();

            CompletableFuture<SendResult<String, String>> future =
                    kafkaTemplate.send(KafkaConfig.ORDER_EVENTS_TOPIC, key, payload);

            future.whenComplete((result, ex) -> {
                if (ex != null) {
                    log.error("Failed to publish order event for order {}: {}", order.getId(), ex.getMessage());
                } else {
                    log.info("Published {} event for order {} to partition {} offset {}",
                            eventType, order.getId(),
                            result.getRecordMetadata().partition(),
                            result.getRecordMetadata().offset());
                }
            });
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize order event for order {}: {}", order.getId(), e.getMessage());
        }
    }

    public void publishProductEvent(Long productId, String eventType, Map<String, Object> data) {
        Map<String, Object> event = new HashMap<>(data);
        event.put("eventType", eventType);
        event.put("productId", productId);
        event.put("timestamp", System.currentTimeMillis());

        try {
            String payload = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(KafkaConfig.PRODUCT_EVENTS_TOPIC, productId.toString(), payload);
            log.info("Published {} event for product {}", eventType, productId);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize product event for product {}: {}", productId, e.getMessage());
        }
    }
}
