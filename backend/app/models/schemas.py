from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import json

from app.models.database import Base


class PlanType(str, enum.Enum):
    BASIC = "basic"
    PRO = "pro"
    VIP = "vip"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=True)
    whatsapp = Column(String(20), nullable=True)
    plan = Column(String(20), default=PlanType.BASIC)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    mt5_accounts = relationship("MT5Account", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    orders = relationship("Order", back_populates="user")


class MT5Account(Base):
    __tablename__ = "mt5_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_number = Column(String(50), nullable=False)
    server = Column(String(100), nullable=False)
    balance = Column(Float, default=0.0)
    equity = Column(Float, default=0.0)
    profit_today = Column(Float, default=0.0)
    profit_week = Column(Float, default=0.0)
    profit_month = Column(Float, default=0.0)
    profit_pct = Column(Float, default=0.0)
    is_connected = Column(Boolean, default=False)
    last_update = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="mt5_accounts")
    robots = relationship("RobotInstance", back_populates="mt5_account")


class Robot(Base):
    __tablename__ = "robots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    strategy = Column(String(100), nullable=False)
    symbols = Column(String(200), nullable=False)
    min_plan = Column(String(20), default=PlanType.BASIC)
    icon = Column(String(50), default="🤖")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    instances = relationship("RobotInstance", back_populates="robot")


class RobotInstance(Base):
    __tablename__ = "robot_instances"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mt5_account_id = Column(Integer, ForeignKey("mt5_accounts.id"), nullable=False)
    robot_id = Column(Integer, ForeignKey("robots.id"), nullable=False)
    is_running = Column(Boolean, default=False)

    # Risk Management / Lot Configuration
    risk_per_trade = Column(Float, default=2.0)       # % da banca por trade
    max_lot = Column(Float, default=1.0)              # lote máximo
    min_lot = Column(Float, default=0.01)             # lote mínimo
    max_daily_trades = Column(Integer, default=10)    # máx trades/dia
    max_daily_loss = Column(Float, default=5.0)       # % máximo de perda/dia
    stop_loss_pips = Column(Integer, default=50)      # SL em pips
    take_profit_pips = Column(Integer, default=100)   # TP em pips
    trailing_stop = Column(Boolean, default=False)     # trailing stop
    trailing_stop_pips = Column(Integer, default=30)  # pips do trailing
    lot_multiplier = Column(Float, default=1.0)       # multiplicador do lote
    use_dynamic_lot = Column(Boolean, default=True)   # lote dinâmico baseado na banca
    fixed_lot = Column(Float, default=0.01)           # lote fixo (se não usar dinâmico)

    profit_total = Column(Float, default=0.0)
    trades_count = Column(Integer, default=0)
    wins_count = Column(Integer, default=0)
    losses_count = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    daily_trades_today = Column(Integer, default=0)
    daily_pnl = Column(Float, default=0.0)
    last_trade_date = Column(String(10), nullable=True)

    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    mt5_account = relationship("MT5Account", back_populates="robots")
    robot = relationship("Robot", back_populates="instances")

    def get_settings_dict(self):
        return {
            "risk_per_trade": self.risk_per_trade,
            "max_lot": self.max_lot,
            "min_lot": self.min_lot,
            "max_daily_trades": self.max_daily_trades,
            "max_daily_loss": self.max_daily_loss,
            "stop_loss_pips": self.stop_loss_pips,
            "take_profit_pips": self.take_profit_pips,
            "trailing_stop": self.trailing_stop,
            "trailing_stop_pips": self.trailing_stop_pips,
            "lot_multiplier": self.lot_multiplier,
            "use_dynamic_lot": self.use_dynamic_lot,
            "fixed_lot": self.fixed_lot,
        }

    def calculate_lot(self, balance: float, symbol: str = "XAUUSD") -> float:
        """Calcula o lote ideal baseado na banca e risco configurado"""
        if not self.use_dynamic_lot:
            return max(self.min_lot, min(self.fixed_lot, self.max_lot))

        # Risk amount in dollars
        risk_amount = balance * (self.risk_per_trade / 100)

        # Approximate pip value (varies by symbol)
        pip_values = {
            "XAUUSD": 10.0,   # $10 per pip per 0.01 lot (standard)
            "BTCUSD": 1.0,    # $1 per pip per 0.01 lot
        }
        pip_value = pip_values.get(symbol, 10.0)

        # Calculate lot based on risk and stop loss
        if self.stop_loss_pips > 0:
            lot = risk_amount / (self.stop_loss_pips * pip_value)
        else:
            lot = risk_amount / 100  # fallback

        # Apply multiplier
        lot *= self.lot_multiplier

        # Clamp between min and max
        lot = max(self.min_lot, min(round(lot, 2), self.max_lot))

        return lot


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mt5_account_id = Column(Integer, ForeignKey("mt5_accounts.id"), nullable=False)
    robot_instance_id = Column(Integer, ForeignKey("robot_instances.id"), nullable=True)
    ticket = Column(String(50), nullable=True)
    symbol = Column(String(20), nullable=False)
    order_type = Column(String(10), nullable=False)
    volume = Column(Float, nullable=False)
    open_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    profit = Column(Float, default=0.0)
    status = Column(String(20), default="open")
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(String(20), nullable=False)
    stripe_subscription_id = Column(String(200), nullable=True)
    stripe_customer_id = Column(String(200), nullable=True)
    status = Column(String(20), default="active")
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="subscriptions")


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)
    subject = Column(String(200), nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
