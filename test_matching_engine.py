#!/usr/bin/env python3
"""
Unit tests for the Cryptocurrency Matching Engine
"""

import pytest
import time
from decimal import Decimal
from main import (
    Order, OrderType, OrderSide, OrderStatus, Trade, BBO, 
    OrderBook, MatchingEngine, PriceLevel
)


class TestOrder:
    """Test Order class functionality"""
    
    def test_order_creation(self):
        """Test basic order creation"""
        order = Order(
            order_id="test1",
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("1.5"),
            price=Decimal("50000")
        )
        
        assert order.order_id == "test1"
        assert order.symbol == "BTC-USDT"
        assert order.is_buy is True
        assert order.is_sell is False
        assert order.remaining_quantity == Decimal("1.5")
        assert order.filled_quantity == Decimal("0")
        assert order.status == OrderStatus.PENDING
    
    def test_order_validation(self):
        """Test order validation"""
        # Test missing price for limit order
        with pytest.raises(ValueError):
            Order(
                order_id="test2",
                symbol="BTC-USDT",
                order_type=OrderType.LIMIT,
                side=OrderSide.BUY,
                quantity=Decimal("1.5")
            )
        
        # Test negative quantity
        with pytest.raises(ValueError):
            Order(
                order_id="test3",
                symbol="BTC-USDT",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=Decimal("-1.5")
            )
    
    def test_partial_fill(self):
        """Test partial order filling"""
        order = Order(
            order_id="test4",
            symbol="BTC-USDT",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=Decimal("2.0"),
            price=Decimal("50000")
        )
        
        # Partial fill
        order.partial_fill(Decimal("0.5"))
        assert order.filled_quantity == Decimal("0.5")
        assert order.remaining_quantity == Decimal("1.5")
        assert order.status == OrderStatus.PARTIALLY_FILLED
        
        # Complete fill
        order.partial_fill(Decimal("1.5"))
        assert order.filled_quantity == Decimal("2.0")
        assert order.remaining_quantity == Decimal("0")
        assert order.status == OrderStatus.FILLED


class TestPriceLevel:
    """Test PriceLevel functionality"""
    
    def test_price_level_operations(self):
        """Test price level order management"""
        price_level = PriceLevel(Decimal("50000"))
        
        order1 = Order("o1", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        order2 = Order("o2", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("0.5"), Decimal("50000"))
        
        # Add orders
        price_level.add_order(order1)
        price_level.add_order(order2)
        
        assert price_level.total_quantity == Decimal("1.5")
        assert len(price_level.orders) == 2
        
        # Test FIFO order
        fillable_orders, total_fillable = price_level.get_fillable_quantity(Decimal("1.2"))
        assert total_fillable == Decimal("1.2")
        assert len(fillable_orders) == 2
        assert fillable_orders[0] == order1  # First in, first out
        
        # Remove order
        price_level.remove_order(order1)
        assert price_level.total_quantity == Decimal("0.5")
        assert len(price_level.orders) == 1


class TestOrderBook:
    """Test OrderBook functionality"""
    
    def test_order_book_creation(self):
        """Test order book creation and basic operations"""
        book = OrderBook("BTC-USDT")
        assert book.symbol == "BTC-USDT"
        assert len(book.bids) == 0
        assert len(book.asks) == 0
    
    def test_add_orders(self):
        """Test adding orders to the book"""
        book = OrderBook("BTC-USDT")
        
        # Add buy orders
        buy1 = Order("b1", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("49000"))
        buy2 = Order("b2", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("0.5"), Decimal("50000"))
        
        book.add_order(buy1)
        book.add_order(buy2)
        
        # Add sell orders
        sell1 = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("0.8"), Decimal("51000"))
        sell2 = Order("s2", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.2"), Decimal("52000"))
        
        book.add_order(sell1)
        book.add_order(sell2)
        
        assert len(book.bids) == 2
        assert len(book.asks) == 2
        assert len(book.orders) == 4
    
    def test_bbo_calculation(self):
        """Test Best Bid and Offer calculation"""
        book = OrderBook("BTC-USDT")
        
        # Empty book
        bbo = book.get_bbo()
        assert bbo.best_bid is None
        assert bbo.best_offer is None
        
        # Add orders
        buy1 = Order("b1", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("49000"))
        buy2 = Order("b2", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("0.5"), Decimal("50000"))
        sell1 = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("0.8"), Decimal("51000"))
        sell2 = Order("s2", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.2"), Decimal("52000"))
        
        book.add_order(buy1)
        book.add_order(buy2)
        book.add_order(sell1)
        book.add_order(sell2)
        
        bbo = book.get_bbo()
        assert bbo.best_bid == Decimal("50000")  # Highest bid
        assert bbo.best_offer == Decimal("51000")  # Lowest ask
        assert bbo.bid_quantity == Decimal("0.5")
        assert bbo.offer_quantity == Decimal("0.8")
    
    def test_price_time_priority(self):
        """Test price-time priority in order matching"""
        book = OrderBook("BTC-USDT")
        
        # Add sell orders at same price (time priority)
        sell1 = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), Decimal("50000"))
        time.sleep(0.001)  # Ensure different timestamps
        sell2 = Order("s2", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, Decimal("1.0"), Decimal("50000"))
        
        book.add_order(sell1)
        book.add_order(sell2)
        
        # Create buy order to match
        buy = Order("b1", "BTC-USDT", OrderType.MARKET, OrderSide.BUY, Decimal("1.5"))
        matches = book.get_matching_orders(buy)
        
        # Should match sell1 first (time priority)
        assert len(matches) >= 1
        assert matches[0][0] == sell1
    
    def test_remove_orders(self):
        """Test order removal"""
        book = OrderBook("BTC-USDT")
        
        buy = Order("b1", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY, Decimal("1.0"), Decimal("50000"))
        book.add_order(buy)
        
        assert len(book.orders) == 1
        
        removed = book.remove_order("b1")
        assert removed == buy
        assert len(book.orders) == 0
        assert len(book.bids) == 0


class TestMatchingEngine:
    """Test MatchingEngine functionality"""
    
    def test_engine_creation(self):
        """Test matching engine creation"""
        engine = MatchingEngine()
        assert len(engine.order_books) == 0
        assert len(engine.trades) == 0
    
    def test_limit_order_matching(self):
        """Test limit order matching"""
        engine = MatchingEngine()
        
        # Add sell order first
        sell_order = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL, 
                          Decimal("1.0"), Decimal("50000"))
        processed_sell, trades = engine.submit_order(sell_order)
        
        assert processed_sell.status == OrderStatus.PENDING
        assert len(trades) == 0
        
        # Add matching buy order
        buy_order = Order("b1", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY,
                         Decimal("0.5"), Decimal("50000"))
        processed_buy, trades = engine.submit_order(buy_order)
        
        assert processed_buy.status == OrderStatus.FILLED
        assert len(trades) == 1
        assert trades[0].quantity == Decimal("0.5")
        assert trades[0].price == Decimal("50000")
        assert processed_sell.filled_quantity == Decimal("0.5")
    
    def test_market_order_execution(self):
        """Test market order execution"""
        engine = MatchingEngine()
        
        # Add sell orders
        sell1 = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                     Decimal("0.5"), Decimal("50000"))
        sell2 = Order("s2", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                     Decimal("0.5"), Decimal("51000"))
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        
        # Execute market buy order
        market_buy = Order("b1", "BTC-USDT", OrderType.MARKET, OrderSide.BUY,
                          Decimal("0.8"))
        processed, trades = engine.submit_order(market_buy)
        
        assert len(trades) == 2  # Should match both sells
        assert trades[0].price == Decimal("50000")  # Best price first
        assert trades[1].price == Decimal("51000")
        assert processed.status == OrderStatus.FILLED
    
    def test_ioc_order(self):
        """Test Immediate or Cancel order"""
        engine = MatchingEngine()
        
        # Add sell order
        sell = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                    Decimal("0.5"), Decimal("50000"))
        engine.submit_order(sell)
        
        # IOC buy order for more than available
        ioc_buy = Order("b1", "BTC-USDT", OrderType.IOC, OrderSide.BUY,
                       Decimal("1.0"), Decimal("50000"))
        processed, trades = engine.submit_order(ioc_buy)
        
        assert len(trades) == 1
        assert trades[0].quantity == Decimal("0.5")  # Only available amount
        assert processed.status == OrderStatus.CANCELLED  # Remainder cancelled
        assert processed.filled_quantity == Decimal("0.5")
    
    def test_fok_order(self):
        """Test Fill or Kill order"""
        engine = MatchingEngine()
        
        # Add insufficient liquidity
        sell = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                    Decimal("0.5"), Decimal("50000"))
        engine.submit_order(sell)
        
        # FOK order that can't be fully filled
        fok_buy = Order("b1", "BTC-USDT", OrderType.FOK, OrderSide.BUY,
                       Decimal("1.0"), Decimal("50000"))
        processed, trades = engine.submit_order(fok_buy)
        
        assert len(trades) == 0  # No trades executed
        assert processed.status == OrderStatus.CANCELLED
        assert processed.filled_quantity == Decimal("0")
        
        # Add more liquidity
        sell2 = Order("s2", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                     Decimal("0.5"), Decimal("50000"))
        engine.submit_order(sell2)
        
        # FOK order that can be fully filled
        fok_buy2 = Order("b2", "BTC-USDT", OrderType.FOK, OrderSide.BUY,
                        Decimal("1.0"), Decimal("50000"))
        processed2, trades2 = engine.submit_order(fok_buy2)
        
        assert len(trades2) == 2  # Both sells matched
        assert processed2.status == OrderStatus.FILLED
        assert processed2.filled_quantity == Decimal("1.0")
    
    def test_price_improvement(self):
        """Test that orders get price improvement when possible"""
        engine = MatchingEngine()
        
        # Add sell orders at different prices
        sell1 = Order("s1", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                     Decimal("0.5"), Decimal("49000"))  # Better price
        sell2 = Order("s2", "BTC-USDT", OrderType.LIMIT, OrderSide.SELL,
                     Decimal("0.5"), Decimal("50000"))
        
        engine.submit_order(sell1)
        engine.submit_order(sell2)
        
        # Market buy should get best price first
        market_buy = Order("b1", "BTC-USDT", OrderType.MARKET, OrderSide.BUY,
                          Decimal("0.3"))
        processed, trades = engine.submit_order(market_buy)
        
        assert len(trades) == 1
        assert trades[0].price == Decimal("49000")  # Should get better price
    
    def test_order_cancellation(self):
        """Test order cancellation"""
        engine = MatchingEngine()
        
        # Add limit order
        order = Order("test", "BTC-USDT", OrderType.LIMIT, OrderSide.BUY,
                     Decimal("1.0"), Decimal("50000"))
        engine.submit_order(order)
        
        # Cancel order
        success = engine.cancel_order("test", "BTC-USDT")
        assert success is True
        
        # Try to cancel non-existent order
        success = engine.cancel_order("nonexistent", "BTC-USDT")
        assert success is False


@pytest.mark.asyncio
class TestAPI:
    """Test API functionality (requires running server)"""
    
    def test_order_validation(self):
        """Test order request validation"""
        from main import OrderRequest
        
        # Valid order
        valid_request = OrderRequest(
            symbol="BTC-USDT",
            order_type="limit",
            side="buy",
            quantity="1.0",
            price="50000"
        )
        assert valid_request.symbol == "BTC-USDT"
        
        # Invalid order type
        with pytest.raises(ValueError):
            OrderRequest(
                symbol="BTC-USDT",
                order_type="invalid",
                side="buy",
                quantity="1.0"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
