package com.ecommerce.orderservice.controller;

import com.ecommerce.orderservice.model.Product;
import com.ecommerce.orderservice.repository.ProductRepository;
import com.ecommerce.orderservice.service.KafkaProducerService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/products")
public class ProductController {

    private final ProductRepository productRepository;
    private final KafkaProducerService kafkaProducer;

    public ProductController(ProductRepository productRepository, KafkaProducerService kafkaProducer) {
        this.productRepository = productRepository;
        this.kafkaProducer = kafkaProducer;
    }

    @PostMapping
    public ResponseEntity<Product> createProduct(@Valid @RequestBody Product product) {
        Product saved = productRepository.save(product);

        kafkaProducer.publishProductEvent(saved.getId(), "PRODUCT_CREATED", Map.of(
                "name", saved.getName(),
                "description", saved.getDescription(),
                "category", saved.getCategory(),
                "price", saved.getPrice()
        ));

        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @GetMapping
    public ResponseEntity<List<Product>> getAllProducts(
            @RequestParam(required = false) String category) {
        if (category != null) {
            return ResponseEntity.ok(productRepository.findByCategory(category));
        }
        return ResponseEntity.ok(productRepository.findAll());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Product> getProduct(@PathVariable Long id) {
        return productRepository.findById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/search")
    public ResponseEntity<List<Product>> searchProducts(@RequestParam String q) {
        return ResponseEntity.ok(productRepository.findByNameContainingIgnoreCase(q));
    }
}
