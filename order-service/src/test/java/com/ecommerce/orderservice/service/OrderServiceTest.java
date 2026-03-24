package com.ecommerce.orderservice.service;

import com.ecommerce.orderservice.dto.OrderRequest;
import com.ecommerce.orderservice.dto.OrderResponse;
import com.ecommerce.orderservice.model.Order;
import com.ecommerce.orderservice.model.OrderItem;
import com.ecommerce.orderservice.model.OrderStatus;
import com.ecommerce.orderservice.model.Product;
import com.ecommerce.orderservice.repository.OrderRepository;
import com.ecommerce.orderservice.repository.ProductRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private ProductRepository productRepository;

    @Mock
    private KafkaProducerService kafkaProducer;

    @InjectMocks
    private OrderService orderService;

    private Product testProduct;

    @BeforeEach
    void setUp() {
        testProduct = new Product("Test Laptop", "A great laptop", "Electronics",
                new BigDecimal("999.99"), 10);
        testProduct.setId(1L);
    }

    @Test
    void createOrder_success() {
        OrderRequest request = new OrderRequest();
        request.setCustomerId("cust-1");
        request.setShippingAddress("123 Main St");

        OrderRequest.ItemRequest itemReq = new OrderRequest.ItemRequest();
        itemReq.setProductId(1L);
        itemReq.setQuantity(2);
        request.setItems(List.of(itemReq));

        when(productRepository.findById(1L)).thenReturn(Optional.of(testProduct));
        when(productRepository.save(any(Product.class))).thenReturn(testProduct);
        when(orderRepository.save(any(Order.class))).thenAnswer(invocation -> {
            Order order = invocation.getArgument(0);
            order.setId(100L);
            return order;
        });

        OrderResponse response = orderService.createOrder(request);

        assertNotNull(response);
        assertEquals("cust-1", response.getCustomerId());
        assertEquals(OrderStatus.CONFIRMED, response.getStatus());
        assertEquals(1, response.getItems().size());

        // Stock should be decremented
        assertEquals(8, testProduct.getStockQuantity());

        // Kafka event should be published
        verify(kafkaProducer).publishOrderEvent(any(Order.class), eq("ORDER_CREATED"));
    }

    @Test
    void createOrder_insufficientStock_throws() {
        testProduct.setStockQuantity(1);

        OrderRequest request = new OrderRequest();
        request.setCustomerId("cust-1");
        request.setShippingAddress("123 Main St");

        OrderRequest.ItemRequest itemReq = new OrderRequest.ItemRequest();
        itemReq.setProductId(1L);
        itemReq.setQuantity(5);
        request.setItems(List.of(itemReq));

        when(productRepository.findById(1L)).thenReturn(Optional.of(testProduct));

        assertThrows(IllegalStateException.class, () -> orderService.createOrder(request));
        verify(kafkaProducer, never()).publishOrderEvent(any(), anyString());
    }

    @Test
    void createOrder_productNotFound_throws() {
        OrderRequest request = new OrderRequest();
        request.setCustomerId("cust-1");
        request.setShippingAddress("123 Main St");

        OrderRequest.ItemRequest itemReq = new OrderRequest.ItemRequest();
        itemReq.setProductId(999L);
        itemReq.setQuantity(1);
        request.setItems(List.of(itemReq));

        when(productRepository.findById(999L)).thenReturn(Optional.empty());

        assertThrows(IllegalArgumentException.class, () -> orderService.createOrder(request));
    }

    @Test
    void updateOrderStatus_validTransition() {
        Order order = new Order();
        order.setId(1L);
        order.setCustomerId("cust-1");
        order.setStatus(OrderStatus.CONFIRMED);
        order.setTotalAmount(new BigDecimal("100.00"));

        OrderItem item = new OrderItem(testProduct, 1);
        order.addItem(item);

        when(orderRepository.findByIdWithItems(1L)).thenReturn(order);
        when(orderRepository.save(any(Order.class))).thenReturn(order);

        OrderResponse response = orderService.updateOrderStatus(1L, OrderStatus.PROCESSING);

        assertEquals(OrderStatus.PROCESSING, response.getStatus());
        verify(kafkaProducer).publishOrderEvent(any(Order.class), eq("ORDER_STATUS_UPDATED"));
    }

    @Test
    void updateOrderStatus_invalidTransition_throws() {
        Order order = new Order();
        order.setId(1L);
        order.setStatus(OrderStatus.DELIVERED);

        when(orderRepository.findByIdWithItems(1L)).thenReturn(order);

        assertThrows(IllegalStateException.class,
                () -> orderService.updateOrderStatus(1L, OrderStatus.PROCESSING));
    }

    @Test
    void updateOrderStatus_cancel_restoresStock() {
        Order order = new Order();
        order.setId(1L);
        order.setCustomerId("cust-1");
        order.setStatus(OrderStatus.CONFIRMED);
        order.setTotalAmount(new BigDecimal("999.99"));

        OrderItem item = new OrderItem(testProduct, 3);
        order.addItem(item);
        testProduct.setStockQuantity(7); // was 10, bought 3

        when(orderRepository.findByIdWithItems(1L)).thenReturn(order);
        when(orderRepository.save(any(Order.class))).thenReturn(order);
        when(productRepository.save(any(Product.class))).thenReturn(testProduct);

        orderService.updateOrderStatus(1L, OrderStatus.CANCELLED);

        assertEquals(10, testProduct.getStockQuantity());
    }
}
