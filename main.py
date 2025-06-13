#!/usr/bin/env python3
"""
High-Performance Cryptocurrency Matching Engine
REG NMS-inspired trading system with price-time priority
"""

import time
import uuid
import logging
import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
import heapq
from threading import Lock, RLock
import threading

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
import websockets


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('matching_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents a trading order in the system"""
    order_id: str
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: Decimal
    price: Optional[Decimal] = None
    timestamp: float = field(default_factory=time.time)
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = field(default_factory=lambda: Decimal('0'))
    remaining_quantity: Optional[Decimal] = None
    
    def __post_init__(self):
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity
        
        # Validate order parameters
        if self.order_type in [OrderType.LIMIT, OrderType.IOC, OrderType.FOK] and self.price is None:
            raise ValueError(f"Price required for {self.order_type.value} orders")
        
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.price is not None and self.price <= 0:
            raise ValueError("Price must be positive")
    
    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY
    
    @property
    def is_sell(self) -> bool:
        return self.side == OrderSide.SELL
    
    def partial_fill(self, quantity: Decimal) -> None:
        """Process a partial fill of the order"""
        if self.remaining_quantity is None or quantity > self.remaining_quantity:
            raise ValueError("Fill quantity exceeds remaining quantity")
        
        self.filled_quantity += quantity
        self.remaining_quantity -= quantity
        
        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED


@dataclass
class Trade:
    """Represents a completed trade"""
    trade_id: str
    symbol: str
    price: Decimal
    quantity: Decimal
    timestamp: float
    aggressor_side: OrderSide
    maker_order_id: str
    taker_order_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "symbol": self.symbol,
            "trade_id": self.trade_id,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "aggressor_side": self.aggressor_side.value,
            "maker_order_id": self.maker_order_id,
            "taker_order_id": self.taker_order_id
        }


@dataclass
class BBO:
    """Best Bid and Offer data"""
    symbol: str
    best_bid: Optional[Decimal] = None
    best_offer: Optional[Decimal] = None
    bid_quantity: Optional[Decimal] = None
    offer_quantity: Optional[Decimal] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "symbol": self.symbol,
            "best_bid": str(self.best_bid) if self.best_bid else None,
            "best_offer": str(self.best_offer) if self.best_offer else None,
            "bid_quantity": str(self.bid_quantity) if self.bid_quantity else None,
            "offer_quantity": str(self.offer_quantity) if self.offer_quantity else None
        }


class PriceLevel:
    """Represents a price level in the order book with FIFO queue"""
    
    def __init__(self, price: Decimal):
        self.price = price
        self.orders: deque[Order] = deque()
        self.total_quantity = Decimal('0')
    
    def add_order(self, order: Order) -> None:
        """Add order to this price level (FIFO)"""
        self.orders.append(order)
        self.total_quantity += order.remaining_quantity if order.remaining_quantity is not None else Decimal('0')
    
    def remove_order(self, order: Order) -> bool:
        """Remove specific order from this price level"""
        try:
            self.orders.remove(order)
            if order.remaining_quantity is not None:
                self.total_quantity -= order.remaining_quantity
            return True
        except ValueError:
            return False
    
    def get_fillable_quantity(self, max_quantity: Decimal) -> Tuple[List[Order], Decimal]:
        """Get orders and total quantity that can be filled up to max_quantity"""
        fillable_orders = []
        total_fillable = Decimal('0')
        
        for order in self.orders:
            if total_fillable >= max_quantity:
                break
            
            if order.remaining_quantity is not None:
                available = min(order.remaining_quantity, max_quantity - total_fillable)
                if available > 0:
                    fillable_orders.append(order)
                    total_fillable += available
        
        return fillable_orders, total_fillable
    
    def is_empty(self) -> bool:
        return len(self.orders) == 0


class OrderBook:
    """Order book maintaining price-time priority"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[Decimal, PriceLevel] = {}  # price -> PriceLevel
        self.asks: Dict[Decimal, PriceLevel] = {}  # price -> PriceLevel
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.lock = RLock()
        
        # Sorted price levels for efficient BBO calculation
        self._bid_prices: List[Decimal] = []  # Sorted descending (highest first)
        self._ask_prices: List[Decimal] = []  # Sorted ascending (lowest first)
    
    def add_order(self, order: Order) -> None:
        """Add order to the book"""
        with self.lock:
            if order.order_id in self.orders:
                raise ValueError(f"Order {order.order_id} already exists")
            
            self.orders[order.order_id] = order
            
            if order.is_buy:
                self._add_bid_order(order)
            else:
                self._add_ask_order(order)
    
    def _add_bid_order(self, order: Order) -> None:
        """Add buy order to bid side"""
        price = order.price
        if price is None:
            raise ValueError("Order price cannot be None for bid orders")
        if price not in self.bids:
            self.bids[price] = PriceLevel(price)
            self._insert_bid_price(price)
        
        self.bids[price].add_order(order)
    
    def _add_ask_order(self, order: Order) -> None:
        """Add sell order to ask side"""
        price = order.price
        if price is None:
            raise ValueError("Order price cannot be None for ask orders")
        if price not in self.asks:
            self.asks[price] = PriceLevel(price)
            self._insert_ask_price(price)
        
        self.asks[price].add_order(order)
    
    def _insert_bid_price(self, price: Decimal) -> None:
        """Insert bid price maintaining descending order"""
        import bisect
        # For bids, we want descending order (highest first)
        # So we negate prices for bisect operations
        neg_prices = [-p for p in self._bid_prices]
        insert_pos = bisect.bisect_left(neg_prices, -price)
        self._bid_prices.insert(insert_pos, price)
    
    def _insert_ask_price(self, price: Decimal) -> None:
        """Insert ask price maintaining ascending order"""
        import bisect
        insert_pos = bisect.bisect_left(self._ask_prices, price)
        self._ask_prices.insert(insert_pos, price)
    
    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove order from the book"""
        with self.lock:
            if order_id not in self.orders:
                return None
            
            order = self.orders.pop(order_id)
            
            if order.is_buy:
                self._remove_bid_order(order)
            else:
                self._remove_ask_order(order)
            
            return order
    
    def _remove_bid_order(self, order: Order) -> None:
        """Remove buy order from bid side"""
        price = order.price
        if price is None:
            raise ValueError("Order price cannot be None for bid orders")
        if price in self.bids:
            price_level = self.bids[price]
            price_level.remove_order(order)
            
            if price_level.is_empty():
                del self.bids[price]
                self._bid_prices.remove(price)
    
    def _remove_ask_order(self, order: Order) -> None:
        """Remove sell order from ask side"""
        price = order.price
        if price is None:
            raise ValueError("Order price cannot be None for ask orders")
        if price in self.asks:
            price_level = self.asks[price]
            price_level.remove_order(order)
            
            if price_level.is_empty():
                del self.asks[price]
                self._ask_prices.remove(price)
    
    def get_bbo(self) -> BBO:
        """Get Best Bid and Offer"""
        with self.lock:
            bbo = BBO(symbol=self.symbol)
            
            # Best bid (highest price)
            if self._bid_prices:
                best_bid_price = self._bid_prices[0]
                bid_level = self.bids[best_bid_price]
                bbo.best_bid = best_bid_price
                bbo.bid_quantity = bid_level.total_quantity
            
            # Best offer (lowest price)
            if self._ask_prices:
                best_ask_price = self._ask_prices[0]
                ask_level = self.asks[best_ask_price]
                bbo.best_offer = best_ask_price
                bbo.offer_quantity = ask_level.total_quantity
            
            return bbo
    
    def get_market_data(self, depth: int = 10) -> Dict[str, Any]:
        """Get order book market data"""
        with self.lock:
            bids = []
            asks = []
            
            # Top bids (highest prices first)
            for i, price in enumerate(self._bid_prices[:depth]):
                if price in self.bids:
                    level = self.bids[price]
                    bids.append([str(price), str(level.total_quantity)])
            
            # Top asks (lowest prices first)
            for i, price in enumerate(self._ask_prices[:depth]):
                if price in self.asks:
                    level = self.asks[price]
                    asks.append([str(price), str(level.total_quantity)])
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": self.symbol,
                "bids": bids,
                "asks": asks
            }
    
    def get_matching_orders(self, incoming_order: Order) -> List[Tuple[Order, Decimal]]:
        """Get orders that can match with incoming order, respecting price-time priority"""
        with self.lock:
            matches = []
            remaining_qty = incoming_order.remaining_quantity
            if remaining_qty is None:
                remaining_qty = Decimal('0')
            
            if incoming_order.is_buy:
                # Buy order matches against asks (sells)
                # We want lowest ask prices first
                for ask_price in self._ask_prices:
                    if remaining_qty <= 0:
                        break
                    
                    # For buy orders, check if willing to pay ask price
                    if incoming_order.order_type == OrderType.MARKET or \
                       (incoming_order.price is not None and incoming_order.price >= ask_price):
                        
                        ask_level = self.asks[ask_price]
                        fillable_orders, fillable_qty = ask_level.get_fillable_quantity(remaining_qty)
                        
                        for order in fillable_orders:
                            fill_qty = min(order.remaining_quantity if order.remaining_quantity is not None else Decimal('0'), remaining_qty)
                            matches.append((order, fill_qty))
                            remaining_qty -= fill_qty
                            
                            if remaining_qty <= 0:
                                break
            else:
                # Sell order matches against bids (buys)
                # We want highest bid prices first
                for bid_price in self._bid_prices:
                    if remaining_qty <= 0:
                        break
                    
                    # For sell orders, check if willing to accept bid price
                    if incoming_order.order_type == OrderType.MARKET or \
                       (incoming_order.price is not None and incoming_order.price <= bid_price):
                        
                        bid_level = self.bids[bid_price]
                        fillable_orders, fillable_qty = bid_level.get_fillable_quantity(remaining_qty)
                        
                        for order in fillable_orders:
                            fill_qty = min(order.remaining_quantity if order.remaining_quantity is not None else Decimal('0'), remaining_qty)
                            matches.append((order, fill_qty))
                            remaining_qty -= fill_qty
                            
                            if remaining_qty <= 0:
                                break
            
            return matches


class MatchingEngine:
    """Core matching engine implementing REG NMS principles"""
    
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}
        self.trades: List[Trade] = []
        self.lock = RLock()
        
        # Event callbacks
        self.trade_callbacks: List[Callable[[Trade], None]] = []
        self.bbo_callbacks: List[Callable[[BBO], None]] = []
        self.order_book_callbacks: List[Callable[[str, Dict], None]] = []
        
        logger.info("MatchingEngine initialized")
    
    def get_or_create_order_book(self, symbol: str) -> OrderBook:
        """Get existing order book or create new one"""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
            logger.info(f"Created new order book for {symbol}")
        return self.order_books[symbol]
    
    def submit_order(self, order: Order) -> Tuple[Order, List[Trade]]:
        """Submit order to matching engine with REG NMS compliance"""
        with self.lock:
            logger.info(f"Processing order: {order.order_id} {order.side.value} {order.quantity} {order.symbol} @ {order.price}")
            
            order_book = self.get_or_create_order_book(order.symbol)
            trades = []
            
            try:
                # Handle different order types
                if order.order_type == OrderType.MARKET:
                    trades = self._process_market_order(order, order_book)
                elif order.order_type == OrderType.LIMIT:
                    trades = self._process_limit_order(order, order_book)
                elif order.order_type == OrderType.IOC:
                    trades = self._process_ioc_order(order, order_book)
                elif order.order_type == OrderType.FOK:
                    trades = self._process_fok_order(order, order_book)
                
                # Update BBO and notify subscribers
                self._update_market_data(order.symbol)
                
                logger.info(f"Order {order.order_id} processed. Status: {order.status.value}, Trades: {len(trades)}")
                return order, trades
                
            except Exception as e:
                logger.error(f"Error processing order {order.order_id}: {str(e)}")
                order.status = OrderStatus.REJECTED
                return order, []
    
    def _process_market_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Process market order - executes at best available prices"""
        matches = order_book.get_matching_orders(order)
        trades = []
        
        for maker_order, fill_qty in matches:
            trade = self._execute_trade(
                maker_order=maker_order,
                taker_order=order,
                quantity=fill_qty,
                price=maker_order.price if maker_order.price is not None else (
                    order.price if order.price is not None else Decimal('0')
                )
            )
            trades.append(trade)
            
            # Update order quantities
            maker_order.partial_fill(fill_qty)
            order.partial_fill(fill_qty)
            
            # Remove filled orders from book
            if maker_order.remaining_quantity == 0:
                order_book.remove_order(maker_order.order_id)
        
        # Market orders that can't be filled are cancelled
        if order.remaining_quantity is not None and order.remaining_quantity > 0:
            order.status = OrderStatus.CANCELLED
            logger.warning(f"Market order {order.order_id} partially cancelled - insufficient liquidity")
        
        return trades
    
    def _process_limit_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Process limit order - match what's possible, rest on book"""
        matches = order_book.get_matching_orders(order)
        trades = []
        
        # Execute matches
        for maker_order, fill_qty in matches:
            trade = self._execute_trade(
                maker_order=maker_order,
                taker_order=order,
                quantity=fill_qty,
                price=maker_order.price if maker_order.price is not None else (order.price if order.price is not None else Decimal('0'))
            )
            trades.append(trade)
            
            maker_order.partial_fill(fill_qty)
            order.partial_fill(fill_qty)
            
            if maker_order.remaining_quantity == 0:
                order_book.remove_order(maker_order.order_id)
        
        # Add remaining quantity to book if not fully filled
        if order.remaining_quantity is not None and order.remaining_quantity > 0:
            order_book.add_order(order)
        
        return trades
    
    def _process_ioc_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Process IOC order - execute immediately, cancel remainder"""
        matches = order_book.get_matching_orders(order)
        trades = []
        
        for maker_order, fill_qty in matches:
            trade = self._execute_trade(
                maker_order=maker_order,
                taker_order=order,
                quantity=fill_qty,
                price=maker_order.price if maker_order.price is not None else (order.price if order.price is not None else Decimal('0'))
            )
            trades.append(trade)
            
            maker_order.partial_fill(fill_qty)
            order.partial_fill(fill_qty)
            
            if maker_order.remaining_quantity == 0:
                order_book.remove_order(maker_order.order_id)
        
        # Cancel any remaining quantity
        if order.remaining_quantity is not None and order.remaining_quantity > 0:
            order.status = OrderStatus.CANCELLED
        
        return trades
    
    def _process_fok_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Process FOK order - execute fully or cancel entirely"""
        matches = order_book.get_matching_orders(order)
        
        # Calculate total fillable quantity
        total_fillable = sum(fill_qty for _, fill_qty in matches)
        
        # If can't fill completely, cancel the order
        remaining_qty = order.remaining_quantity if order.remaining_quantity is not None else Decimal('0')
        if total_fillable < remaining_qty:
            order.status = OrderStatus.CANCELLED
            logger.info(f"FOK order {order.order_id} cancelled - insufficient liquidity")
            return []
        
        # Execute all matches
        trades = []
        for maker_order, fill_qty in matches:
            trade = self._execute_trade(
                maker_order=maker_order,
                taker_order=order,
                quantity=fill_qty,
                price=maker_order.price if maker_order.price is not None else (order.price if order.price is not None else Decimal('0'))
            )
            trades.append(trade)
            
            maker_order.partial_fill(fill_qty)
            order.partial_fill(fill_qty)
            
            if maker_order.remaining_quantity == 0:
                order_book.remove_order(maker_order.order_id)
        
        return trades
    
    def _execute_trade(self, maker_order: Order, taker_order: Order, 
                      quantity: Decimal, price: Decimal) -> Trade:
        """Execute a trade between two orders"""
        trade = Trade(
            trade_id=str(uuid.uuid4()),
            symbol=maker_order.symbol,
            price=price,
            quantity=quantity,
            timestamp=time.time(),
            aggressor_side=taker_order.side,
            maker_order_id=maker_order.order_id,
            taker_order_id=taker_order.order_id
        )
        
        self.trades.append(trade)
        
        # Notify trade callbacks
        for callback in self.trade_callbacks:
            try:
                callback(trade)
            except Exception as e:
                logger.error(f"Trade callback error: {str(e)}")
        
        logger.info(f"Trade executed: {trade.trade_id} {quantity} @ {price}")
        return trade
    
    def _update_market_data(self, symbol: str) -> None:
        """Update and broadcast market data"""
        if symbol in self.order_books:
            order_book = self.order_books[symbol]
            
            # Update BBO
            bbo = order_book.get_bbo()
            for callback in self.bbo_callbacks:
                try:
                    callback(bbo)
                except Exception as e:
                    logger.error(f"BBO callback error: {str(e)}")
            
            # Update order book data
            market_data = order_book.get_market_data()
            for callback in self.order_book_callbacks:
                try:
                    callback(symbol, market_data)
                except Exception as e:
                    logger.error(f"Order book callback error: {str(e)}")
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order"""
        with self.lock:
            if symbol not in self.order_books:
                return False
            
            order_book = self.order_books[symbol]
            order = order_book.remove_order(order_id)
            
            if order:
                order.status = OrderStatus.CANCELLED
                self._update_market_data(symbol)
                logger.info(f"Order cancelled: {order_id}")
                return True
            
            return False
    
    def get_bbo(self, symbol: str) -> Optional[BBO]:
        """Get current BBO for symbol"""
        if symbol in self.order_books:
            return self.order_books[symbol].get_bbo()
        return None
    
    def get_order_book_data(self, symbol: str, depth: int = 10) -> Optional[Dict]:
        """Get order book data for symbol"""
        if symbol in self.order_books:
            return self.order_books[symbol].get_market_data(depth)
        return None


# API Models
class OrderRequest(BaseModel):
    symbol: str
    order_type: str
    side: str
    quantity: str
    price: Optional[str] = None
    
    @validator('order_type')
    def validate_order_type(cls, v):
        if v not in [ot.value for ot in OrderType]:
            raise ValueError(f"Invalid order type: {v}")
        return v
    
    @validator('side')
    def validate_side(cls, v):
        if v not in [s.value for s in OrderSide]:
            raise ValueError(f"Invalid side: {v}")
        return v


class OrderResponse(BaseModel):
    order_id: str
    status: str
    filled_quantity: str
    remaining_quantity: str
    trades: List[Dict[str, Any]]


# FastAPI Application
app = FastAPI(title="Cryptocurrency Matching Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global matching engine instance
matching_engine = MatchingEngine()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.trade_connections: List[WebSocket] = []
        self.market_data_connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self.bbo_connections: Dict[str, List[WebSocket]] = defaultdict(list)
    
    async def connect_trades(self, websocket: WebSocket):
        await websocket.accept()
        self.trade_connections.append(websocket)
    
    async def connect_market_data(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        self.market_data_connections[symbol].append(websocket)
    
    async def connect_bbo(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        self.bbo_connections[symbol].append(websocket)
    
    def disconnect_trades(self, websocket: WebSocket):
        if websocket in self.trade_connections:
            self.trade_connections.remove(websocket)
    
    def disconnect_market_data(self, websocket: WebSocket, symbol: str):
        if websocket in self.market_data_connections[symbol]:
            self.market_data_connections[symbol].remove(websocket)
    
    def disconnect_bbo(self, websocket: WebSocket, symbol: str):
        if websocket in self.bbo_connections[symbol]:
            self.bbo_connections[symbol].remove(websocket)
    
    async def broadcast_trade(self, trade: Trade):
        if self.trade_connections:
            message = json.dumps(trade.to_dict())
            for connection in self.trade_connections[:]:
                try:
                    await connection.send_text(message)
                except:
                    self.trade_connections.remove(connection)
    
    async def broadcast_market_data(self, symbol: str, data: Dict):
        if symbol in self.market_data_connections:
            message = json.dumps(data)
            for connection in self.market_data_connections[symbol][:]:
                try:
                    await connection.send_text(message)
                except:
                    self.market_data_connections[symbol].remove(connection)
    
    async def broadcast_bbo(self, bbo: BBO):
        if bbo.symbol in self.bbo_connections:
            message = json.dumps(bbo.to_dict())
            for connection in self.bbo_connections[bbo.symbol][:]:
                try:
                    await connection.send_text(message)
                except:
                    self.bbo_connections[bbo.symbol].remove(connection)

manager = ConnectionManager()

# Register callbacks
def trade_callback(trade):
    asyncio.create_task(manager.broadcast_trade(trade))

def bbo_callback(bbo):
    asyncio.create_task(manager.broadcast_bbo(bbo))

def order_book_callback(symbol, data):
    asyncio.create_task(manager.broadcast_market_data(symbol, data))

matching_engine.trade_callbacks.append(trade_callback)
matching_engine.bbo_callbacks.append(bbo_callback)
matching_engine.order_book_callbacks.append(order_book_callback)


# REST API Endpoints
@app.post("/orders", response_model=OrderResponse)
async def submit_order(order_request: OrderRequest):
    """Submit a new order"""
    try:
        # Create order object
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=order_request.symbol,
            order_type=OrderType(order_request.order_type),
            side=OrderSide(order_request.side),
            quantity=Decimal(order_request.quantity),
            price=Decimal(order_request.price) if order_request.price else None
        )
        
        # Submit to matching engine
        processed_order, trades = matching_engine.submit_order(order)
        
        # Format response
        return OrderResponse(
            order_id=processed_order.order_id,
            status=processed_order.status.value,
            filled_quantity=str(processed_order.filled_quantity),
            remaining_quantity=str(processed_order.remaining_quantity),
            trades=[trade.to_dict() for trade in trades]
        )
        
    except Exception as e:
        logger.error(f"Error submitting order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str, symbol: str):
    """Cancel an existing order"""
    success = matching_engine.cancel_order(order_id, symbol)
    if success:
        return {"message": "Order cancelled successfully"}
    else:
        raise HTTPException(status_code=404, detail="Order not found")


@app.get("/market-data/{symbol}")
async def get_market_data(symbol: str, depth: int = 10):
    """Get current order book market data"""
    data = matching_engine.get_order_book_data(symbol, depth)
    if data:
        return data
    else:
        raise HTTPException(status_code=404, detail="Symbol not found")


@app.get("/bbo/{symbol}")
async def get_bbo(symbol: str):
    """Get current Best Bid and Offer"""
    bbo = matching_engine.get_bbo(symbol)
    if bbo:
        return bbo.to_dict()
    else:
        raise HTTPException(status_code=404, detail="Symbol not found")


# WebSocket Endpoints
@app.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    """WebSocket endpoint for trade data stream"""
    await manager.connect_trades(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect_trades(websocket)


@app.websocket("/ws/market-data/{symbol}")
async def websocket_market_data(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for order book data stream"""
    await manager.connect_market_data(websocket, symbol)
    try:
        # Send initial data
        initial_data = matching_engine.get_order_book_data(symbol)
        if initial_data:
            await websocket.send_text(json.dumps(initial_data))
        
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect_market_data(websocket, symbol)


@app.websocket("/ws/bbo/{symbol}")
async def websocket_bbo(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for BBO data stream"""
    await manager.connect_bbo(websocket, symbol)
    try:
        # Send initial BBO
        initial_bbo = matching_engine.get_bbo(symbol)
        if initial_bbo:
            await websocket.send_text(json.dumps(initial_bbo.to_dict()))
        
        while True:
            await websocket.receive_text()
    except:
        manager.disconnect_bbo(websocket, symbol)


if __name__ == "__main__":
    print("Starting Cryptocurrency Matching Engine...")
    print("API Documentation: http://localhost:8000/docs")
    print("WebSocket Endpoints:")
    print("  - Trade Stream: ws://localhost:8000/ws/trades")
    print("  - Market Data: ws://localhost:8000/ws/market-data/{symbol}")
    print("  - BBO Stream: ws://localhost:8000/ws/bbo/{symbol}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
