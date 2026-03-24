package com.ecommerce.orderservice.exception;

import com.ecommerce.orderservice.model.OrderStatus;

public class InvalidStatusTransitionException extends RuntimeException {

    private final OrderStatus currentStatus;
    private final OrderStatus targetStatus;

    public InvalidStatusTransitionException(OrderStatus currentStatus, OrderStatus targetStatus) {
        super("Cannot transition from " + currentStatus + " to " + targetStatus);
        this.currentStatus = currentStatus;
        this.targetStatus = targetStatus;
    }

    public OrderStatus getCurrentStatus() {
        return currentStatus;
    }

    public OrderStatus getTargetStatus() {
        return targetStatus;
    }
}
