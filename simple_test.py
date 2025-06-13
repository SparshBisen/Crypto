#!/usr/bin/env python3
"""
Simple test to verify the matching engine functionality without external dependencies
"""

from decimal import Decimal
from main import (
    Order, OrderType, OrderSide, OrderStatus, Trade, BBO, 
    OrderBook, MatchingEngine, PriceLevel
)


def test_basic_functionality():
    """Test basic matching engine functionality"""
    print("Testing basic functionality...")
    
    # Create matching engine
    engine = MatchingEngine()
    
    # Test 1: Create limit orders
    print("Test 1: Creating limit orders")
    sell_order = Order(
        order_id="sell1",
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.SELL,
        quantity=Decimal("1.0"),
        price=Decimal("50000")
    )
    
    buy_order = Order(
        order_id="buy1",
        symbol="BTC-USDT",
        order_type=OrderType.LIMIT,
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000")
    )
    
    # Submit sell order first (should rest on book)
    processed_sell, trades_sell = engine.submit_order(sell_order)
    assert processed_sell.status == OrderStatus.PENDING
    assert len(trades_sell) == 0
    print("✓ Sell order resting on book")
    
    # Submit matching buy order (should execute)
    processed_buy, trades_buy = engine.submit_order(buy_order)
    assert processed_buy.status == OrderStatus.FILLED
    assert len(trades_buy) == 1
    assert trades_buy[0].quantity == Decimal("0.5")
    assert trades_buy[0].price == Decimal("50000")
    print("✓ Buy order matched and executed")
    
    # Test 2: Market order
    print("\nTest 2: Market order execution")
    market_order = Order(
        order_id="market1",
        symbol="BTC-USDT",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=Decimal("0.3")
    )
    
    processed_market, trades_market = engine.submit_order(market_order)
    assert len(trades_market) == 1
    assert trades_market[0].quantity == Decimal("0.3")
    print("✓ Market order executed")
    
    # Test 3: IOC order
    print("\nTest 3: IOC order")
    ioc_order = Order(
        order_id="ioc1",
        symbol="BTC-USDT",
        order_type=OrderType.IOC,
        side=OrderSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("50000")
    )
    
    processed_ioc, trades_ioc = engine.submit_order(ioc_order)
    assert processed_ioc.status == OrderStatus.CANCELLED  # Remaining cancelled
    print("✓ IOC order partial fill and cancel")
    
    # Test 4: Order book and BBO
    print("\nTest 4: Order book and BBO")
    order_book = engine.get_or_create_order_book("ETH-USDT")
    
    # Add some orders
    eth_sell = Order("eth_sell", "ETH-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("2.0"), Decimal("3000"))
    eth_buy = Order("eth_buy", "ETH-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("2900"))
    
    engine.submit_order(eth_sell)
    engine.submit_order(eth_buy)
    
    bbo = engine.get_bbo("ETH-USDT")
    assert bbo is not None, "BBO should not be None"
    assert bbo.best_bid == Decimal("2900")
    assert bbo.best_offer == Decimal("3000")
    print("✓ BBO calculation correct")
    
    # Test 5: Price-time priority
    print("\nTest 5: Price-time priority")
    # Add multiple orders at same price
    order1 = Order("pt1", "TEST-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), Decimal("100"))
    order2 = Order("pt2", "TEST-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), Decimal("100"))
    
    engine.submit_order(order1)
    engine.submit_order(order2)
    
    # Market buy should match first order first
    market_buy = Order("mb1", "TEST-USDT", OrderType.MARKET, OrderSide.BUY, Decimal("0.5"))
    processed_mb, trades_mb = engine.submit_order(market_buy)
    
    assert trades_mb[0].maker_order_id == "pt1"  # First order should match first
    print("✓ Price-time priority working")
    
    print("\nAll tests passed! ✓")


def test_order_validation():
    """Test order validation"""
    print("\nTesting order validation...")
    
    # Test missing price for limit order
    try:
        Order("test", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"))
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✓ Limit order validation working")
    
    # Test negative quantity
    try:
        Order("test", "BTC-USDT", OrderType.MARKET, OrderSide.BUY, Decimal("-1.0"))
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✓ Quantity validation working")
    
    print("Order validation tests passed! ✓")


def test_order_types():
    """Test all order types"""
    print("\nTesting all order types...")
    
    engine = MatchingEngine()
    
    # Setup liquidity
    for i, price in enumerate([50000, 50100, 50200]):
        order = Order(f"setup_sell_{i}", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, 
                     Decimal("1.0"), Decimal(str(price)))
        engine.submit_order(order)
    
    # Test FOK that should fail
    fok_fail = Order("fok_fail", "BTC-USDT", OrderType.FOK, OrderSide.BUY, 
                    Decimal("5.0"), Decimal("50200"))
    processed_fok_fail, trades_fok_fail = engine.submit_order(fok_fail)
    assert processed_fok_fail.status == OrderStatus.CANCELLED
    assert len(trades_fok_fail) == 0
    print("✓ FOK order correctly cancelled when insufficient liquidity")
    
    # Test FOK that should succeed
    fok_succeed = Order("fok_succeed", "BTC-USDT", OrderType.FOK, OrderSide.BUY, 
                       Decimal("1.5"), Decimal("50200"))
    processed_fok_succeed, trades_fok_succeed = engine.submit_order(fok_succeed)
    assert processed_fok_succeed.status == OrderStatus.FILLED
    assert len(trades_fok_succeed) >= 1
    print("✓ FOK order correctly filled when sufficient liquidity")
    
    print("Order type tests passed! ✓")


if __name__ == "__main__":
    print("Running Cryptocurrency Matching Engine Tests")
    print("=" * 50)
    
    test_basic_functionality()
    test_order_validation() 
    test_order_types()
    
    print("\n" + "=" * 50)
    print("All tests completed successfully! 🎉")
    print("\nThe matching engine is working correctly and ready for use.")
