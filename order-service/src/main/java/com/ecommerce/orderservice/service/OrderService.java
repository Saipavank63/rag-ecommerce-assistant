package com.ecommerce.orderservice.service;

import com.ecommerce.orderservice.dto.OrderRequest;
import com.ecommerce.orderservice.dto.OrderResponse;
import com.ecommerce.orderservice.model.Order;
import com.ecommerce.orderservice.model.OrderItem;
import com.ecommerce.orderservice.model.OrderStatus;
import com.ecommerce.orderservice.model.Product;
import com.ecommerce.orderservice.repository.OrderRepository;
import com.ecommerce.orderservice.repository.ProductRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final ProductRepository productRepository;
    private final KafkaProducerService kafkaProducer;

    public OrderService(OrderRepository orderRepository,
                        ProductRepository productRepository,
                        KafkaProducerService kafkaProducer) {
        this.orderRepository = orderRepository;
        this.productRepository = productRepository;
        this.kafkaProducer = kafkaProducer;
    }

    @Transactional
    public OrderResponse createOrder(OrderRequest request) {
        Order order = new Order();
        order.setCustomerId(request.getCustomerId());
        order.setShippingAddress(request.getShippingAddress());

        for (OrderRequest.ItemRequest itemReq : request.getItems()) {
            Product product = productRepository.findById(itemReq.getProductId())
                    .orElseThrow(() -> new IllegalArgumentException(
                            "Product not found: " + itemReq.getProductId()));

            if (product.getStockQuantity() < itemReq.getQuantity()) {
                throw new IllegalStateException(
                        "Insufficient stock for product '" + product.getName() +
                        "': requested " + itemReq.getQuantity() +
                        ", available " + product.getStockQuantity());
            }

            product.setStockQuantity(product.getStockQuantity() - itemReq.getQuantity());
            productRepository.save(product);

            OrderItem item = new OrderItem(product, itemReq.getQuantity());
            order.addItem(item);
        }

        order.recalculateTotal();
        order.setStatus(OrderStatus.CONFIRMED);
        Order saved = orderRepository.save(order);

        log.info("Created order {} for customer {} with {} items, total: {}",
                saved.getId(), saved.getCustomerId(), saved.getItems().size(), saved.getTotalAmount());

        kafkaProducer.publishOrderEvent(saved, "ORDER_CREATED");

        return OrderResponse.from(saved);
    }

    @Transactional(readOnly = true)
    public OrderResponse getOrder(Long id) {
        Order order = orderRepository.findByIdWithItems(id);
        if (order == null) {
            throw new IllegalArgumentException("Order not found: " + id);
        }
        return OrderResponse.from(order);
    }

    @Transactional(readOnly = true)
    public List<OrderResponse> getOrdersByCustomer(String customerId) {
        return orderRepository.findByCustomerIdOrderByCreatedAtDesc(customerId).stream()
                .map(OrderResponse::from)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<OrderResponse> getAllOrders() {
        return orderRepository.findAll().stream()
                .map(OrderResponse::from)
                .toList();
    }

    @Transactional
    public OrderResponse updateOrderStatus(Long id, OrderStatus newStatus) {
        Order order = orderRepository.findByIdWithItems(id);
        if (order == null) {
            throw new IllegalArgumentException("Order not found: " + id);
        }

        OrderStatus currentStatus = order.getStatus();
        validateStatusTransition(currentStatus, newStatus);

        order.setStatus(newStatus);
        Order saved = orderRepository.save(order);

        log.info("Order {} status changed from {} to {}", id, currentStatus, newStatus);
        kafkaProducer.publishOrderEvent(saved, "ORDER_STATUS_UPDATED");

        if (newStatus == OrderStatus.CANCELLED) {
            restoreStock(order);
        }

        return OrderResponse.from(saved);
    }

    private void validateStatusTransition(OrderStatus current, OrderStatus next) {
        boolean valid = switch (current) {
            case PENDING -> next == OrderStatus.CONFIRMED || next == OrderStatus.CANCELLED;
            case CONFIRMED -> next == OrderStatus.PROCESSING || next == OrderStatus.CANCELLED;
            case PROCESSING -> next == OrderStatus.SHIPPED || next == OrderStatus.CANCELLED;
            case SHIPPED -> next == OrderStatus.DELIVERED;
            case DELIVERED -> next == OrderStatus.REFUNDED;
            case CANCELLED, REFUNDED -> false;
        };

        if (!valid) {
            throw new IllegalStateException(
                    "Cannot transition from " + current + " to " + next);
        }
    }

    private void restoreStock(Order order) {
        for (OrderItem item : order.getItems()) {
            Product product = item.getProduct();
            product.setStockQuantity(product.getStockQuantity() + item.getQuantity());
            productRepository.save(product);
        }
        log.info("Restored stock for cancelled order {}", order.getId());
    }
}
