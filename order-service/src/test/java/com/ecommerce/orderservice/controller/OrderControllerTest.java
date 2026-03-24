package com.ecommerce.orderservice.controller;

import com.ecommerce.orderservice.dto.OrderRequest;
import com.ecommerce.orderservice.dto.OrderResponse;
import com.ecommerce.orderservice.exception.GlobalExceptionHandler;
import com.ecommerce.orderservice.exception.InsufficientStockException;
import com.ecommerce.orderservice.exception.OrderNotFoundException;
import com.ecommerce.orderservice.model.Order;
import com.ecommerce.orderservice.model.OrderItem;
import com.ecommerce.orderservice.model.OrderStatus;
import com.ecommerce.orderservice.model.Product;
import com.ecommerce.orderservice.service.OrderService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.bean.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.util.List;

import static org.hamcrest.Matchers.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * MockMvc integration tests for {@link OrderController}.
 * <p>
 * The Spring context is limited to the web layer ({@code @WebMvcTest}) so
 * no real database or Kafka broker is needed.  The {@link OrderService}
 * dependency is replaced with a Mockito mock.
 */
@WebMvcTest(OrderController.class)
@Import(GlobalExceptionHandler.class)
class OrderControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private OrderService orderService;

    private OrderResponse sampleResponse;

    @BeforeEach
    void setUp() {
        Product product = new Product("Test Laptop", "A great laptop",
                "Electronics", new BigDecimal("999.99"), 10);
        product.setId(1L);

        Order order = new Order();
        order.setId(100L);
        order.setCustomerId("cust-1");
        order.setStatus(OrderStatus.CONFIRMED);
        order.setShippingAddress("123 Main St");

        OrderItem item = new OrderItem(product, 2);
        order.addItem(item);
        order.recalculateTotal();

        sampleResponse = OrderResponse.from(order);
    }

    // ── POST /api/orders ─────────────────────────────────────────────────────

    @Test
    void createOrder_returnsCreated() throws Exception {
        when(orderService.createOrder(any(OrderRequest.class))).thenReturn(sampleResponse);

        String body = """
            {
                "customerId": "cust-1",
                "shippingAddress": "123 Main St",
                "items": [
                    { "productId": 1, "quantity": 2 }
                ]
            }
            """;

        mockMvc.perform(post("/api/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.customerId").value("cust-1"))
                .andExpect(jsonPath("$.status").value("CONFIRMED"))
                .andExpect(jsonPath("$.items", hasSize(1)));
    }

    @Test
    void createOrder_missingCustomerId_returns400() throws Exception {
        String body = """
            {
                "shippingAddress": "123 Main St",
                "items": [
                    { "productId": 1, "quantity": 2 }
                ]
            }
            """;

        mockMvc.perform(post("/api/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.customerId").exists());
    }

    @Test
    void createOrder_emptyItems_returns400() throws Exception {
        String body = """
            {
                "customerId": "cust-1",
                "shippingAddress": "123 Main St",
                "items": []
            }
            """;

        mockMvc.perform(post("/api/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.items").exists());
    }

    @Test
    void createOrder_insufficientStock_returns409() throws Exception {
        when(orderService.createOrder(any(OrderRequest.class)))
                .thenThrow(new InsufficientStockException("Test Laptop", 20, 5));

        String body = """
            {
                "customerId": "cust-1",
                "shippingAddress": "123 Main St",
                "items": [
                    { "productId": 1, "quantity": 20 }
                ]
            }
            """;

        mockMvc.perform(post("/api/orders")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.error").value("Insufficient Stock"))
                .andExpect(jsonPath("$.message", containsString("Test Laptop")));
    }

    // ── GET /api/orders/{id} ─────────────────────────────────────────────────

    @Test
    void getOrder_returnsOk() throws Exception {
        when(orderService.getOrder(100L)).thenReturn(sampleResponse);

        mockMvc.perform(get("/api/orders/100"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(100))
                .andExpect(jsonPath("$.customerId").value("cust-1"))
                .andExpect(jsonPath("$.status").value("CONFIRMED"));
    }

    @Test
    void getOrder_notFound_returns404() throws Exception {
        when(orderService.getOrder(999L)).thenThrow(new OrderNotFoundException(999L));

        mockMvc.perform(get("/api/orders/999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("Not Found"))
                .andExpect(jsonPath("$.message", containsString("999")));
    }

    // ── GET /api/orders ──────────────────────────────────────────────────────

    @Test
    void getAllOrders_returnsList() throws Exception {
        when(orderService.getAllOrders()).thenReturn(List.of(sampleResponse));

        mockMvc.perform(get("/api/orders"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].id").value(100));
    }

    @Test
    void getOrdersByCustomer_filtersCorrectly() throws Exception {
        when(orderService.getOrdersByCustomer("cust-1")).thenReturn(List.of(sampleResponse));

        mockMvc.perform(get("/api/orders").param("customerId", "cust-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].customerId").value("cust-1"));
    }

    // ── PATCH /api/orders/{id}/status ────────────────────────────────────────

    @Test
    void updateStatus_returnsOk() throws Exception {
        OrderResponse updatedResponse = OrderResponse.from(createOrderWithStatus(OrderStatus.PROCESSING));
        when(orderService.updateOrderStatus(eq(100L), eq(OrderStatus.PROCESSING)))
                .thenReturn(updatedResponse);

        String body = """
            { "status": "PROCESSING" }
            """;

        mockMvc.perform(patch("/api/orders/100/status")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("PROCESSING"));
    }

    @Test
    void updateStatus_invalidEnum_returns400() throws Exception {
        String body = """
            { "status": "NOT_A_REAL_STATUS" }
            """;

        mockMvc.perform(patch("/api/orders/100/status")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // ── Helper ───────────────────────────────────────────────────────────────

    private Order createOrderWithStatus(OrderStatus status) {
        Product product = new Product("Test Laptop", "A great laptop",
                "Electronics", new BigDecimal("999.99"), 10);
        product.setId(1L);

        Order order = new Order();
        order.setId(100L);
        order.setCustomerId("cust-1");
        order.setStatus(status);
        order.setShippingAddress("123 Main St");

        OrderItem item = new OrderItem(product, 2);
        order.addItem(item);
        order.recalculateTotal();

        return order;
    }
}
