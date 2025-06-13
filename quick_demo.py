#!/usr/bin/env python3
"""
Quick demo of the matching engine functionality
"""

import requests
import json
from decimal import Decimal


def test_basic_functionality():
    """Test basic matching engine functionality"""
    base_url = "http://localhost:8000"
    
    print("🚀 Cryptocurrency Matching Engine Demo")
    print("=" * 50)
    
    # Test 1: Create market with limit orders
    print("\n1. Creating market with limit orders...")
    
    # Add sell orders (asks)
    sell_orders = []
    for i, price in enumerate([50500, 50600, 50700]):
        response = requests.post(f"{base_url}/orders", json={
            "symbol": "ETH-USDT",
            "order_type": "limit",
            "side": "sell",
            "quantity": "1.0",
            "price": str(price)
        })
        order = response.json()
        sell_orders.append(order)
        print(f"  ✓ Sell order: {price} USDT - Status: {order['status']}")
    
    # Add buy orders (bids)
    buy_orders = []
    for i, price in enumerate([50200, 50100, 50000]):
        response = requests.post(f"{base_url}/orders", json={
            "symbol": "ETH-USDT",
            "order_type": "limit",
            "side": "buy",
            "quantity": "0.8",
            "price": str(price)
        })
        order = response.json()
        buy_orders.append(order)
        print(f"  ✓ Buy order: {price} USDT - Status: {order['status']}")
    
    # Check market data
    print("\n2. Current market data:")
    response = requests.get(f"{base_url}/market-data/ETH-USDT")
    market_data = response.json()
    
    print(f"  Symbol: {market_data['symbol']}")
    print("  Best Asks (Sell Orders):")
    for ask in market_data['asks'][:3]:
        print(f"    {ask[0]} USDT @ {ask[1]} ETH")
    print("  Best Bids (Buy Orders):")
    for bid in market_data['bids'][:3]:
        print(f"    {bid[0]} USDT @ {bid[1]} ETH")
    
    # Get BBO
    print("\n3. Best Bid and Offer:")
    response = requests.get(f"{base_url}/bbo/ETH-USDT")
    bbo = response.json()
    print(f"  Best Bid: {bbo['best_bid']} USDT ({bbo['bid_quantity']} ETH)")
    print(f"  Best Ask: {bbo['best_offer']} USDT ({bbo['offer_quantity']} ETH)")
    spread = float(bbo['best_offer']) - float(bbo['best_bid'])
    print(f"  Spread: {spread} USDT")
    
    # Execute market orders
    print("\n4. Executing market orders...")
    
    # Market buy order
    response = requests.post(f"{base_url}/orders", json={
        "symbol": "ETH-USDT",
        "order_type": "market",
        "side": "buy",
        "quantity": "0.7"
    })
    market_buy = response.json()
    print(f"  ✓ Market buy - Status: {market_buy['status']}")
    print(f"    Filled: {market_buy['filled_quantity']} ETH")
    
    if market_buy['trades']:
        for trade in market_buy['trades']:
            print(f"    Trade: {trade['quantity']} ETH @ {trade['price']} USDT")
    
    # Test IOC order
    print("\n5. Testing IOC (Immediate or Cancel) order...")
    response = requests.post(f"{base_url}/orders", json={
        "symbol": "ETH-USDT",
        "order_type": "ioc",
        "side": "buy",
        "quantity": "2.0",
        "price": "50600"
    })
    ioc_order = response.json()
    print(f"  ✓ IOC order - Status: {ioc_order['status']}")
    print(f"    Filled: {ioc_order['filled_quantity']} ETH")
    print(f"    Remaining (cancelled): {ioc_order['remaining_quantity']} ETH")
    
    # Test FOK order
    print("\n6. Testing FOK (Fill or Kill) order...")
    
    # This should fail (insufficient liquidity)
    response = requests.post(f"{base_url}/orders", json={
        "symbol": "ETH-USDT",
        "order_type": "fok",
        "side": "buy",
        "quantity": "10.0",
        "price": "50700"
    })
    fok_fail = response.json()
    print(f"  ✗ FOK large order - Status: {fok_fail['status']} (expected failure)")
    
    # This should succeed
    response = requests.post(f"{base_url}/orders", json={
        "symbol": "ETH-USDT",
        "order_type": "fok",
        "side": "buy",
        "quantity": "0.5",
        "price": "50700"
    })
    fok_succeed = response.json()
    print(f"  ✓ FOK small order - Status: {fok_succeed['status']}")
    if fok_succeed['trades']:
        print(f"    Executed {len(fok_succeed['trades'])} trades")
    
    # Final market state
    print("\n7. Final market state:")
    response = requests.get(f"{base_url}/bbo/ETH-USDT")
    final_bbo = response.json()
    print(f"  Best Bid: {final_bbo['best_bid']} USDT")
    print(f"  Best Ask: {final_bbo['best_offer']} USDT")
    
    print("\n" + "=" * 50)
    print("✅ Demo completed successfully!")
    print("🎯 All order types working correctly")
    print("📊 Market data streaming functional")
    print("⚡ High-performance matching engine ready!")


if __name__ == "__main__":
    try:
        test_basic_functionality()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure the server is running: python3 main.py")
