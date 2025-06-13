# Cryptocurrency Matching Engine

A high-performance cryptocurrency matching engine implementing REG NMS-inspired principles with price-time priority and comprehensive order management.

## Features

### Core Functionality
- **REG NMS-Inspired Matching**: Price-time priority with internal order protection
- **Order Types**: Market, Limit, IOC (Immediate or Cancel), FOK (Fill or Kill)
- **Real-time BBO**: Best Bid and Offer calculation and dissemination
- **Trade Execution**: Complete trade lifecycle with execution reports
- **Order Book Management**: Efficient price-level based order book

### APIs
- **REST API**: Order submission, cancellation, and market data retrieval
- **WebSocket APIs**: Real-time streaming for trades, market data, and BBO updates
- **Comprehensive Logging**: Full audit trail for all operations

### Performance
- **High Throughput**: Optimized data structures for fast order processing
- **Concurrent Processing**: Thread-safe operations with proper locking
- **Efficient Matching**: O(log n) order book operations

## Architecture

### Core Components

```
MatchingEngine
├── OrderBook (per symbol)
│   ├── PriceLevel (FIFO queues)
│   ├── BBO Calculation
│   └── Price-Time Priority
├── Order Management
├── Trade Execution
└── Market Data Broadcasting
```

### Data Structures
- **Order**: Complete order representation with lifecycle management
- **OrderBook**: Price-level based book with sorted price arrays
- **PriceLevel**: FIFO queues for time priority at each price
- **Trade**: Complete trade execution records

### APIs
- **REST Endpoints**: `/orders`, `/market-data/{symbol}`, `/bbo/{symbol}`
- **WebSocket Streams**: `/ws/trades`, `/ws/market-data/{symbol}`, `/ws/bbo/{symbol}`

## Installation

### Requirements
- Python 3.8+
- FastAPI
- Uvicorn
- WebSockets
- Other dependencies in `requirements.txt`

### Setup
```bash
# Clone or download the project
cd cryptocurrency-matching-engine

# Install dependencies
pip install -r requirements.txt

# Run the matching engine
python main.py
```

The server will start on `http://localhost:8000`

### API Documentation
Visit `http://localhost:8000/docs` for interactive API documentation.

## Usage

### Starting the Server
```bash
python main.py
```

### Running Tests
```bash
python -m pytest test_matching_engine.py -v
```

### Demo Client
```bash
python demo_client.py
```

## API Reference

### REST Endpoints

#### Submit Order
```http
POST /orders
Content-Type: application/json

{
  "symbol": "BTC-USDT",
  "order_type": "limit",
  "side": "buy",
  "quantity": "1.5",
  "price": "50000"
}
```

#### Cancel Order
```http
DELETE /orders/{order_id}?symbol=BTC-USDT
```

#### Get Market Data
```http
GET /market-data/BTC-USDT?depth=10
```

#### Get BBO
```http
GET /bbo/BTC-USDT
```

### WebSocket Endpoints

#### Trade Stream
```javascript
ws://localhost:8000/ws/trades
```

#### Market Data Stream
```javascript
ws://localhost:8000/ws/market-data/BTC-USDT
```

#### BBO Stream
```javascript
ws://localhost:8000/ws/bbo/BTC-USDT
```

## Order Types

### Market Orders
- Execute immediately at best available price(s)
- Guaranteed execution (if liquidity exists)
- No price limit

### Limit Orders
- Execute at specified price or better
- Rest on book if not immediately marketable
- Price protection

### IOC (Immediate or Cancel)
- Execute immediately at best available price(s)
- Cancel any unfilled portion
- No resting on book

### FOK (Fill or Kill)
- Execute entire order immediately or cancel
- All-or-nothing execution
- Liquidity requirement check

## REG NMS Compliance

### Price-Time Priority
1. **Price Priority**: Better prices always execute first
2. **Time Priority**: At same price level, orders execute FIFO
3. **No Trade-Through**: Internal orders protected from worse prices

### Best Execution
- Orders always match at best available prices
- Price improvement when possible
- Transparent order book with real-time BBO

### Internal Order Protection
- Incoming orders match against internal book first
- No external routing (self-contained matching)
- Complete price-time priority enforcement

## Performance Characteristics

### Data Structure Efficiency
- **Order Book**: O(log n) insertion/deletion
- **BBO Calculation**: O(1) access to best prices
- **Matching**: O(k) where k is number of matches

### Benchmarking Results
- **Throughput**: >1000 orders/second (depends on hardware)
- **Latency**: Sub-millisecond matching for most orders
- **Memory**: Efficient price-level aggregation

## Example Usage

### Python Client
```python
import requests
from decimal import Decimal

# Submit a limit order
response = requests.post('http://localhost:8000/orders', json={
    "symbol": "BTC-USDT",
    "order_type": "limit",
    "side": "buy",
    "quantity": "1.0",
    "price": "50000"
})

order = response.json()
print(f"Order ID: {order['order_id']}")
print(f"Status: {order['status']}")
```

### WebSocket Client
```python
import asyncio
import websockets
import json

async def stream_trades():
    uri = "ws://localhost:8000/ws/trades"
    async with websockets.connect(uri) as websocket:
        async for message in websocket:
            trade = json.loads(message)
            print(f"Trade: {trade['quantity']} @ {trade['price']}")

asyncio.run(stream_trades())
```

## Testing

### Unit Tests
Comprehensive test suite covering:
- Order validation and lifecycle
- OrderBook operations and matching
- Price-time priority compliance
- All order types (Market, Limit, IOC, FOK)
- Edge cases and error conditions

### Integration Tests
- API endpoint testing
- WebSocket functionality
- End-to-end order processing

### Performance Tests
- Order throughput benchmarking
- Latency measurement
- Memory usage profiling

## Logging and Monitoring

### Audit Trail
- All orders logged with timestamps
- Complete trade execution records
- Order book state changes
- Error conditions and rejections

### Log Levels
- **INFO**: Normal operations, trades, order updates
- **WARNING**: Partial fills, cancellations
- **ERROR**: Validation failures, system errors

### Monitoring
- Order processing rates
- Trade volumes
- System performance metrics
- Error rates and types

## Configuration

### Environment Variables
- `LOG_LEVEL`: Logging level (default: INFO)
- `PORT`: Server port (default: 8000)
- `HOST`: Server host (default: 0.0.0.0)

### Customization
- Precision settings for price/quantity
- Order book depth limits
- Rate limiting configuration
- Fee calculation models

## Security Considerations

### Input Validation
- Strict order parameter validation
- Price and quantity bounds checking
- Symbol validation
- Order type verification

### Error Handling
- Graceful degradation on errors
- Comprehensive error logging
- Client error responses
- System stability protection

### Audit Trail
- Complete transaction logging
- Order lifecycle tracking
- Trade execution records
- System event logging
