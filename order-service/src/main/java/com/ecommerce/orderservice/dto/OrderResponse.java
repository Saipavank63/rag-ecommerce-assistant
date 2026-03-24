package com.ecommerce.orderservice.dto;

import com.ecommerce.orderservice.model.Order;
import com.ecommerce.orderservice.model.OrderItem;
import com.ecommerce.orderservice.model.OrderStatus;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public class OrderResponse {

    private Long id;
    private String customerId;
    private OrderStatus status;
    private BigDecimal totalAmount;
    private String shippingAddress;
    private List<ItemResponse> items;
    private Instant createdAt;
    private Instant updatedAt;

    public static OrderResponse from(Order order) {
        OrderResponse resp = new OrderResponse();
        resp.id = order.getId();
        resp.customerId = order.getCustomerId();
        resp.status = order.getStatus();
        resp.totalAmount = order.getTotalAmount();
        resp.shippingAddress = order.getShippingAddress();
        resp.createdAt = order.getCreatedAt();
        resp.updatedAt = order.getUpdatedAt();
        resp.items = order.getItems().stream()
                .map(ItemResponse::from)
                .toList();
        return resp;
    }

    public Long getId() { return id; }
    public String getCustomerId() { return customerId; }
    public OrderStatus getStatus() { return status; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public String getShippingAddress() { return shippingAddress; }
    public List<ItemResponse> getItems() { return items; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }

    public static class ItemResponse {
        private Long productId;
        private String productName;
        private Integer quantity;
        private BigDecimal unitPrice;
        private BigDecimal subtotal;

        public static ItemResponse from(OrderItem item) {
            ItemResponse resp = new ItemResponse();
            resp.productId = item.getProduct().getId();
            resp.productName = item.getProduct().getName();
            resp.quantity = item.getQuantity();
            resp.unitPrice = item.getUnitPrice();
            resp.subtotal = item.getSubtotal();
            return resp;
        }

        public Long getProductId() { return productId; }
        public String getProductName() { return productName; }
        public Integer getQuantity() { return quantity; }
        public BigDecimal getUnitPrice() { return unitPrice; }
        public BigDecimal getSubtotal() { return subtotal; }
    }
}
