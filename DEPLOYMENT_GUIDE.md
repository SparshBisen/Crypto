# Cryptocurrency Matching Engine - Deployment Guide

## Quick Start

### 1. Installation
```bash
# Install dependencies
pip3 install -r requirements.txt

# Run tests to verify installation
python3 simple_test.py
```

### 2. Start the Server
```bash
python3 main.py
```

The server will start on http://localhost:8000

### 3. Test the API
```bash
# In a new terminal, run the demo client
python3 demo_client.py
```

## API Testing Examples

### Using cURL

#### Submit a Limit Order
```bash
curl -X POST "http://localhost:8000/orders" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "BTC-USDT",
       "order_type": "limit",
       "side": "buy",
       "quantity": "1.0",
       "price": "50000"
     }'
```

#### Get Market Data
```bash
curl "http://localhost:8000/market-data/BTC-USDT?depth=5"
```

#### Get Best Bid/Offer
```bash
curl "http://localhost:8000/bbo/BTC-USDT"
```

### Using Python Requests
```python
import requests
import json

# Submit order
response = requests.post('http://localhost:8000/orders', json={
    "symbol": "BTC-USDT",
    "order_type": "limit", 
    "side": "buy",
    "quantity": "1.0",
    "price": "50000"
})

print(json.dumps(response.json(), indent=2))
```

## WebSocket Testing

### Using Python websockets
```python
import asyncio
import websockets
import json

async def test_trades():
    uri = "ws://localhost:8000/ws/trades"
    async with websockets.connect(uri) as websocket:
        print("Connected to trade stream")
        async for message in websocket:
            trade = json.loads(message)
            print(f"Trade: {trade}")

asyncio.run(test_trades())
```

### Using JavaScript (Browser)
```javascript
// Trade stream
const tradeSocket = new WebSocket('ws://localhost:8000/ws/trades');
tradeSocket.onmessage = function(event) {
    const trade = JSON.parse(event.data);
    console.log('Trade:', trade);
};

// Market data stream
const marketSocket = new WebSocket('ws://localhost:8000/ws/market-data/BTC-USDT');
marketSocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Market Data:', data);
};
```

## Performance Testing

### Simple Load Test
```python
import requests
import time
import concurrent.futures
from decimal import Decimal

def submit_order(i):
    response = requests.post('http://localhost:8000/orders', json={
        "symbol": "PERF-TEST",
        "order_type": "limit",
        "side": "buy" if i % 2 == 0 else "sell",
        "quantity": "1.0",
        "price": str(50000 + (i % 100))
    })
    return response.status_code == 200

# Test 100 concurrent orders
start_time = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(submit_order, i) for i in range(100)]
    results = [f.result() for f in futures]

end_time = time.time()
success_rate = sum(results) / len(results)
print(f"Submitted 100 orders in {end_time - start_time:.2f} seconds")
print(f"Success rate: {success_rate:.1%}")
```

## Production Configuration

### Environment Variables
```bash
export LOG_LEVEL=INFO
export PORT=8000
export HOST=0.0.0.0
```

### Systemd Service (Linux)
```ini
[Unit]
Description=Cryptocurrency Matching Engine
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/matching-engine
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=3
Environment=LOG_LEVEL=INFO
Environment=PORT=8000

[Install]
WantedBy=multi-user.target
```

### Docker Deployment
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "main.py"]
```

```bash
# Build and run
docker build -t matching-engine .
docker run -p 8000:8000 matching-engine
```

## Monitoring & Logging

### Log Files
- `matching_engine.log` - Application logs
- Console output - Real-time operations

### Key Metrics to Monitor
- Orders per second
- Trade execution latency
- WebSocket connection count
- Memory usage
- Order book depth

### Health Check Endpoint
```bash
curl "http://localhost:8000/bbo/HEALTH-CHECK"
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000
# Kill process
kill -9 <PID>
```

#### 2. Dependencies Not Found
```bash
# Reinstall dependencies
pip3 install --force-reinstall -r requirements.txt
```

#### 3. WebSocket Connection Issues
- Check firewall settings
- Verify port 8000 is accessible
- Check browser console for connection errors

#### 4. Performance Issues
- Monitor memory usage with `top` or `htop`
- Check log files for errors
- Reduce order book depth if needed

### Debug Mode
Start server with debug logging:
```bash
LOG_LEVEL=DEBUG python3 main.py
```

## Security Considerations

### Input Validation
- All order parameters are validated
- Price and quantity bounds are enforced
- SQL injection protection (no database in this version)

### Rate Limiting
Consider adding rate limiting for production:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/orders")
@limiter.limit("10/minute")
async def submit_order(request: Request, order_request: OrderRequest):
    # ... existing code
```

### HTTPS Configuration
For production, use HTTPS:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

## Scaling Considerations

### Horizontal Scaling
- Use Redis for shared state
- Implement message queues for order distribution
- Database for persistence

### Vertical Scaling
- Increase server resources
- Optimize data structures
- Use compiled extensions (Cython, Rust)

### High Availability
- Load balancers
- Database replication
- Health checks and failover

## Support

For issues or questions:
1. Check the logs in `matching_engine.log`
2. Run the test suite: `python3 simple_test.py`
3. Review the API documentation at http://localhost:8000/docs
4. Check the WebSocket connections and network configuration
