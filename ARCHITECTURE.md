# Cryptocurrency Matching Engine - Architecture Documentation

## System Overview

This cryptocurrency matching engine implements REG NMS-inspired principles with price-time priority matching and comprehensive order management.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  REST API Clients  │  WebSocket Clients  │  Demo Client         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                      │
├─────────────────────────────────────────────────────────────────┤
│  Order Submission  │  Market Data       │  Trade Stream         │
│  /orders           │  /market-data      │  /ws/trades           │
│  /orders/{id}      │  /bbo              │  /ws/market-data      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MatchingEngine Core                         │
├─────────────────────────────────────────────────────────────────┤
│  • Order Processing & Validation                                │
│  • REG NMS Compliance Logic                                     │
│  • Trade Execution & Settlement                                 │
│  • Event Broadcasting                                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OrderBook Management                         │
├─────────────────────────────────────────────────────────────────┤
│  BTC-USDT Book     │  ETH-USDT Book     │  ... Other Books      │ 
│  ┌─────────────┐   │  ┌─────────────┐   │  ┌─────────────┐      │
│  │ Price Levels│   │  │ Price Levels│   │  │ Price Levels│      │
│  │ FIFO Queues │   │  │ FIFO Queues │   │  │ FIFO Queues │      │
│  │ BBO Calc    │   │  │ BBO Calc    │   │  │ BBO Calc    │      │
│  └─────────────┘   │  └─────────────┘   │  └─────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Structures Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Order Objects     │  Trade Records     │  Market Data          │
│  Price Levels      │  BBO Snapshots     │  Event Logs           │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. MatchingEngine
**Responsibility**: Central orchestrator for all order processing and trade execution.

**Key Features**:
- Thread-safe order processing with RLock
- REG NMS compliance enforcement
- Order type routing (Market, Limit, IOC, FOK)
- Trade execution and settlement
- Event broadcasting to subscribers

**Design Patterns**:
- **Strategy Pattern**: Different order type processors
- **Observer Pattern**: Event callbacks for trades, BBO updates
- **Factory Pattern**: Order book creation per symbol

### 2. OrderBook
**Responsibility**: Maintains price-time priority order book for a single trading pair.

**Key Features**:
- Separate bid/ask price level management
- Sorted price arrays for efficient BBO calculation
- FIFO queues at each price level
- Lock-free read operations where possible

**Data Structure Efficiency**:
```
Bid Prices: [50000, 49990, 49980, ...]  # Descending order
Ask Prices: [50010, 50020, 50030, ...]  # Ascending order

Price Level 50000:
  ├── Order1 (timestamp: 100, qty: 1.0)
  ├── Order2 (timestamp: 200, qty: 0.5)
  └── Order3 (timestamp: 300, qty: 2.0)
```

### 3. PriceLevel
**Responsibility**: Manages FIFO queue of orders at a specific price.

**Implementation**:
- Uses `collections.deque` for O(1) append/popleft operations
- Maintains running total quantity for efficient BBO calculation
- Provides fillable quantity calculation for matching

### 4. Order Management
**Responsibility**: Order lifecycle management and validation.

**Order States**:
```
PENDING → PARTIALLY_FILLED → FILLED
   ↓              ↓
CANCELLED      CANCELLED
   ↓
REJECTED
```

## REG NMS Implementation

### Price-Time Priority
1. **Price Priority**: Orders with better prices execute first
   - Buy orders: Higher price = better priority
   - Sell orders: Lower price = better priority

2. **Time Priority**: At same price level, first-in-first-out (FIFO)
   - Implemented using `deque` data structure
   - Timestamp-based ordering within price levels

### Internal Order Protection
- No trade-throughs: Orders execute at best available internal prices
- Price improvement: Orders can execute at better than limit price
- Complete order book visibility for best execution

### Order Type Compliance

#### Market Orders
```python
def _process_market_order(self, order, order_book):
    # Execute against best available prices
    # No price limit - guarantee execution if liquidity exists
    matches = order_book.get_matching_orders(order)
    # Execute all matches in price-time priority
```

#### Limit Orders
```python
def _process_limit_order(self, order, order_book):
    # Execute marketable portion immediately
    # Rest remaining quantity on book at limit price
    matches = order_book.get_matching_orders(order)
    # Add to book if not fully filled
```

#### IOC (Immediate or Cancel)
```python
def _process_ioc_order(self, order, order_book):
    # Execute immediately available quantity
    # Cancel any remaining unfilled portion
    # Never rests on book
```

#### FOK (Fill or Kill)
```python
def _process_fok_order(self, order, order_book):
    # Check if entire order can be filled
    # If yes: execute completely
    # If no: cancel entire order
```

## Data Flow

### Order Submission Flow
```
1. API Request → Validation → Order Object Creation
2. MatchingEngine.submit_order()
3. Order Type Routing
4. OrderBook.get_matching_orders()
5. Trade Execution Loop
6. Order Book Updates
7. BBO Recalculation
8. Event Broadcasting
9. Response to Client
```

### Trade Execution Flow
```
1. Match Detection (price-time priority)
2. Trade Object Creation
3. Order Quantity Updates
4. Order Status Updates
5. Order Book Cleanup (if filled)
6. Trade Event Broadcasting
7. Audit Logging
```

### Market Data Flow
```
1. Order Book Change Detection
2. BBO Recalculation (O(1) operation)
3. Market Data Snapshot Creation
4. WebSocket Broadcasting
5. Client Updates
```

## Performance Optimizations

### Data Structure Choices
- **Sorted Arrays**: O(log n) price level insertion, O(1) BBO access
- **Deque**: O(1) FIFO operations for time priority
- **Dictionary**: O(1) average case order lookup
- **Decimal**: Precise financial calculations

### Memory Management
- Object pooling for frequently created objects
- Lazy cleanup of empty price levels
- Efficient string operations for IDs

### Concurrency
- **RLock**: Reentrant locks for nested operations
- **Thread-safe collections**: Where applicable
- **Lock granularity**: Per-symbol order books reduce contention

### Algorithm Complexity
```
Operation                Time Complexity    Space Complexity
─────────────────────────────────────────────────────────────
Add Order                O(log n)          O(1)
Remove Order             O(log n)          O(1)
BBO Calculation          O(1)              O(1)
Match Finding            O(k)              O(1)
Trade Execution          O(1)              O(1)

Where:
n = number of price levels
k = number of matching orders
```

## Error Handling & Reliability

### Input Validation
```python
@validator('order_type')
def validate_order_type(cls, v):
    if v not in [ot.value for ot in OrderType]:
        raise ValueError(f"Invalid order type: {v}")
    return v
```

### Exception Handling
- Graceful degradation on errors
- Comprehensive error logging
- Order rejection with clear reasons
- System stability protection

### Audit Trail
- Complete order lifecycle logging
- Trade execution records
- System event logging
- Error tracking and analysis

## API Design

### REST Endpoints
```
POST   /orders           # Submit new order
DELETE /orders/{id}      # Cancel existing order
GET    /market-data/{symbol}  # Get order book snapshot
GET    /bbo/{symbol}     # Get best bid/offer
```

### WebSocket Streams
```
/ws/trades              # Real-time trade stream
/ws/market-data/{symbol} # Order book updates
/ws/bbo/{symbol}        # BBO updates
```

### Message Formats
```json
{
  "timestamp": "2025-06-09T22:37:27.275Z",
  "symbol": "BTC-USDT",
  "trade_id": "uuid",
  "price": "50000.00",
  "quantity": "1.50000000",
  "aggressor_side": "buy",
  "maker_order_id": "uuid",
  "taker_order_id": "uuid"
}
```

## Security Considerations

### Input Sanitization
- Parameter validation using Pydantic
- Type checking and bounds validation
- SQL injection prevention (no database operations)

### Rate Limiting
- Can be added using slowapi middleware
- Per-client order submission limits
- WebSocket connection limits

### Audit & Compliance
- Complete transaction logging
- Order flow reconstruction capability
- Regulatory reporting support

## Testing Strategy

### Unit Tests
- Core logic testing (matching, order types)
- Data structure operations
- Edge case validation
- Error condition handling

### Integration Tests
- API endpoint testing
- WebSocket functionality
- End-to-end order flow
- Performance benchmarking

### Load Testing
- High-frequency order submission
- Concurrent client testing
- Memory usage profiling
- Latency measurement

## Future Enhancements

### Advanced Features
- Advanced order types (Stop-Loss, Iceberg)
- Risk management integration
- Fee calculation models
- Cross-trading prevention

### Performance Scaling
- Lock-free data structures
- SIMD optimizations
- Memory pool allocation
- GPU acceleration for matching

### Enterprise Features
- Database persistence
- High availability clustering
- Advanced monitoring
- Regulatory compliance modules

## Design Trade-offs

### Simplicity vs Performance
- **Chosen**: Clear, maintainable code with good performance
- **Alternative**: Maximum optimization with complex code

### Memory vs Speed
- **Chosen**: Efficient data structures with reasonable memory usage
- **Alternative**: Cache everything in memory for maximum speed

### Consistency vs Availability
- **Chosen**: Strong consistency within single instance
- **Alternative**: Eventual consistency across distributed system

### Language Choice: Python
- **Pros**: Rapid development, extensive libraries, readability
- **Cons**: Not the fastest for high-frequency trading
- **Mitigation**: Efficient algorithms and data structures, potential C extensions

This architecture provides a solid foundation for a production-ready matching engine while maintaining code clarity and extensibility.
