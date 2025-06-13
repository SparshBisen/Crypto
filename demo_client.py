#!/usr/bin/env python3
"""
Demo client for the Cryptocurrency Matching Engine
Demonstrates order submission, market data streaming, and trade execution
"""

import asyncio
import json
import time
import requests
import websockets
from decimal import Decimal
import threading
import random


class MatchingEngineClient:
    """Client for interacting with the matching engine"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def submit_order(self, symbol, order_type, side, quantity, price=None):
        """Submit an order to the matching engine"""
        order_data = {
            "symbol": symbol,
            "order_type": order_type,
            "side": side,
            "quantity": str(quantity)
        }
        
        if price is not None:
            order_data["price"] = str(price)
        
        response = self.session.post(f"{self.base_url}/orders", json=order_data)
        response.raise_for_status()
        return response.json()
    
    def cancel_order(self, order_id, symbol):
        """Cancel an existing order"""
        response = self.session.delete(f"{self.base_url}/orders/{order_id}?symbol={symbol}")
        response.raise_for_status()
        return response.json()
    
    def get_market_data(self, symbol, depth=10):
        """Get current order book data"""
        response = self.session.get(f"{self.base_url}/market-data/{symbol}?depth={depth}")
        response.raise_for_status()
        return response.json()
    
    def get_bbo(self, symbol):
        """Get current Best Bid and Offer"""
        response = self.session.get(f"{self.base_url}/bbo/{symbol}")
        response.raise_for_status()
        return response.json()


class WebSocketClient:
    """WebSocket client for real-time data streaming"""
    
    def __init__(self, base_url="ws://localhost:8000"):
        self.base_url = base_url
    
    async def stream_trades(self):
        """Stream trade execution data"""
        uri = f"{self.base_url}/ws/trades"
        async with websockets.connect(uri) as websocket:
            print("Connected to trade stream")
            async for message in websocket:
                trade = json.loads(message)
                print(f"Trade: {trade['symbol']} {trade['quantity']} @ {trade['price']} "
                      f"(aggressor: {trade['aggressor_side']})")
    
    async def stream_market_data(self, symbol):
        """Stream order book market data"""
        uri = f"{self.base_url}/ws/market-data/{symbol}"
        async with websockets.connect(uri) as websocket:
            print(f"Connected to market data stream for {symbol}")
            async for message in websocket:
                data = json.loads(message)
                print(f"\nOrder Book - {symbol}")
                print("Asks (Sell Orders):")
                for ask in data['asks'][:5]:
                    print(f"  {ask[0]} @ {ask[1]}")
                print("Bids (Buy Orders):")
                for bid in data['bids'][:5]:
                    print(f"  {bid[0]} @ {bid[1]}")
                print("-" * 40)
    
    async def stream_bbo(self, symbol):
        """Stream Best Bid and Offer data"""
        uri = f"{self.base_url}/ws/bbo/{symbol}"
        async with websockets.connect(uri) as websocket:
            print(f"Connected to BBO stream for {symbol}")
            async for message in websocket:
                bbo = json.loads(message)
                bid = f"{bbo['best_bid']} ({bbo['bid_quantity']})" if bbo['best_bid'] else "N/A"
                ask = f"{bbo['best_offer']} ({bbo['offer_quantity']})" if bbo['best_offer'] else "N/A"
                print(f"BBO {symbol}: Bid {bid} | Ask {ask}")


def demo_basic_trading():
    """Demonstrate basic trading functionality"""
    print("=== Basic Trading Demo ===")
    client = MatchingEngineClient()
    
    symbol = "BTC-USDT"
    
    try:
        # Submit some limit orders to create a market
        print("\n1. Creating initial market with limit orders...")
        
        # Add sell orders (asks)
        sell_orders = []
        for i, price in enumerate([50100, 50200, 50300, 50400, 50500]):
            order = client.submit_order(symbol, "limit", "sell", Decimal("0.5"), Decimal(price))
            sell_orders.append(order)
            print(f"Sell order: {order['order_id']} - {order['status']}")
        
        # Add buy orders (bids)
        buy_orders = []
        for i, price in enumerate([49900, 49800, 49700, 49600, 49500]):
            order = client.submit_order(symbol, "limit", "buy", Decimal("0.5"), Decimal(price))
            buy_orders.append(order)
            print(f"Buy order: {order['order_id']} - {order['status']}")
        
        # Check market data
        print("\n2. Current market data:")
        market_data = client.get_market_data(symbol)
        print(f"Symbol: {market_data['symbol']}")
        print("Best Asks:")
        for ask in market_data['asks'][:3]:
            print(f"  {ask[0]} @ {ask[1]}")
        print("Best Bids:")
        for bid in market_data['bids'][:3]:
            print(f"  {bid[0]} @ {bid[1]}")
        
        # Get BBO
        print("\n3. Best Bid and Offer:")
        bbo = client.get_bbo(symbol)
        print(f"Best Bid: {bbo['best_bid']} ({bbo['bid_quantity']})")
        print(f"Best Ask: {bbo['best_offer']} ({bbo['offer_quantity']})")
        
        # Execute market orders
        print("\n4. Executing market orders...")
        
        # Market buy order (should match with best ask)
        market_buy = client.submit_order(symbol, "market", "buy", Decimal("0.3"))
        print(f"Market buy result: {market_buy['status']}")
        print(f"Filled quantity: {market_buy['filled_quantity']}")
        if market_buy['trades']:
            for trade in market_buy['trades']:
                print(f"  Trade: {trade['quantity']} @ {trade['price']}")
        
        # Market sell order (should match with best bid)
        market_sell = client.submit_order(symbol, "market", "sell", Decimal("0.2"))
        print(f"Market sell result: {market_sell['status']}")
        print(f"Filled quantity: {market_sell['filled_quantity']}")
        if market_sell['trades']:
            for trade in market_sell['trades']:
                print(f"  Trade: {trade['quantity']} @ {trade['price']}")
        
        # Test IOC order
        print("\n5. Testing IOC (Immediate or Cancel) order...")
        ioc_order = client.submit_order(symbol, "ioc", "buy", Decimal("1.0"), Decimal("50200"))
        print(f"IOC order result: {ioc_order['status']}")
        print(f"Filled: {ioc_order['filled_quantity']}, Remaining: {ioc_order['remaining_quantity']}")
        
        # Test FOK order
        print("\n6. Testing FOK (Fill or Kill) order...")
        # This should fail (insufficient liquidity)
        fok_order = client.submit_order(symbol, "fok", "buy", Decimal("5.0"), Decimal("50300"))
        print(f"FOK order result: {fok_order['status']} (should be cancelled)")
        
        # This should succeed
        fok_order2 = client.submit_order(symbol, "fok", "buy", Decimal("0.2"), Decimal("50300"))
        print(f"FOK order2 result: {fok_order2['status']} (should be filled)")
        
        print("\nBasic trading demo completed successfully!")
        
    except Exception as e:
        print(f"Error in demo: {e}")


def demo_price_time_priority():
    """Demonstrate price-time priority matching"""
    print("\n=== Price-Time Priority Demo ===")
    client = MatchingEngineClient()
    
    symbol = "ETH-USDT"
    
    try:
        # Add multiple orders at same price to test time priority
        print("\n1. Adding multiple sell orders at same price...")
        
        sell_orders = []
        for i in range(3):
            order = client.submit_order(symbol, "limit", "sell", Decimal("1.0"), Decimal("3000"))
            sell_orders.append(order)
            print(f"Sell order {i+1}: {order['order_id']}")
            time.sleep(0.1)  # Small delay to ensure different timestamps
        
        # Market buy should match in FIFO order
        print("\n2. Executing market buy to test FIFO...")
        market_buy = client.submit_order(symbol, "market", "buy", Decimal("2.5"))
        
        print(f"Market buy filled: {market_buy['filled_quantity']}")
        print("Trades executed (should be in FIFO order):")
        for i, trade in enumerate(market_buy['trades']):
            print(f"  Trade {i+1}: {trade['quantity']} @ {trade['price']} "
                  f"(maker: {trade['maker_order_id']})")
        
    except Exception as e:
        print(f"Error in price-time priority demo: {e}")


async def demo_websocket_streaming():
    """Demonstrate WebSocket streaming functionality"""
    print("\n=== WebSocket Streaming Demo ===")
    
    # Create WebSocket clients
    ws_client = WebSocketClient()
    rest_client = MatchingEngineClient()
    
    symbol = "DOGE-USDT"
    
    # Start streaming tasks
    async def trade_stream():
        await ws_client.stream_trades()
    
    async def market_data_stream():
        await ws_client.stream_market_data(symbol)
    
    async def bbo_stream():
        await ws_client.stream_bbo(symbol)
    
    async def generate_orders():
        """Generate random orders to create market activity"""
        await asyncio.sleep(2)  # Wait for streams to connect
        
        print(f"\nGenerating random orders for {symbol}...")
        
        for i in range(10):
            try:
                side = random.choice(["buy", "sell"])
                order_type = random.choice(["limit", "market"])
                quantity = Decimal(str(round(random.uniform(0.1, 2.0), 1)))
                
                if order_type == "limit":
                    base_price = 0.1
                    price_offset = random.uniform(-0.005, 0.005)
                    price = Decimal(str(round(base_price + price_offset, 4)))
                    order = rest_client.submit_order(symbol, order_type, side, quantity, price)
                else:
                    order = rest_client.submit_order(symbol, order_type, side, quantity)
                
                print(f"Order {i+1}: {order_type} {side} {quantity} - {order['status']}")
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error generating order: {e}")
    
    # Run streaming and order generation concurrently
    try:
        await asyncio.gather(
            trade_stream(),
            bbo_stream(),
            generate_orders(),
            return_exceptions=True
        )
    except KeyboardInterrupt:
        print("\nStreaming demo stopped by user")


def demo_performance_test():
    """Simple performance test"""
    print("\n=== Performance Test ===")
    client = MatchingEngineClient()
    
    symbol = "PERF-TEST"
    num_orders = 100
    
    try:
        start_time = time.time()
        
        print(f"Submitting {num_orders} orders...")
        
        for i in range(num_orders):
            side = "buy" if i % 2 == 0 else "sell"
            price = Decimal("100") + Decimal(str(random.randint(-10, 10)))
            quantity = Decimal("1.0")
            
            client.submit_order(symbol, "limit", side, quantity, price)
        
        end_time = time.time()
        duration = end_time - start_time
        orders_per_second = num_orders / duration
        
        print(f"Submitted {num_orders} orders in {duration:.2f} seconds")
        print(f"Performance: {orders_per_second:.2f} orders/second")
        
    except Exception as e:
        print(f"Error in performance test: {e}")


async def main():
    """Main demo function"""
    print("Cryptocurrency Matching Engine Demo")
    print("=" * 50)
    
    # Wait a moment for server to be ready
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    # Run demos
    demo_basic_trading()
    demo_price_time_priority()
    demo_performance_test()
    
    # Ask user if they want to see streaming demo
    print("\nWould you like to see the WebSocket streaming demo? (y/n): ", end="")
    # For demo purposes, we'll skip the input and just show it
    print("y")
    print("Starting WebSocket streaming demo (press Ctrl+C to stop)...")
    await demo_websocket_streaming()


if __name__ == "__main__":
    print("Make sure the matching engine server is running on localhost:8000")
    print("You can start it with: python main.py")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo stopped by user")
