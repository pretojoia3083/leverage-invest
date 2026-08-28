from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.models.database import get_db
from app.models.schemas import MT5Account, Order, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/mt5", tags=["MT5 Bridge"])


class TradeReport(BaseModel):
    ticket: str
    symbol: str
    order_type: str
    volume: float
    open_price: float
    close_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    profit: float = 0.0
    status: str = "open"
    opened_at: Optional[str] = None


class MT5ReportRequest(BaseModel):
    account_number: str
    server: str
    balance: float = 0.0
    equity: float = 0.0
    profit_today: float = 0.0
    profit_week: float = 0.0
    trades: List[TradeReport] = []


@router.post("/report")
def report_trades(req: MT5ReportRequest, db: Session = Depends(get_db)):
    account = db.query(MT5Account).filter(
        MT5Account.account_number == req.account_number,
        MT5Account.server == req.server,
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada. Conecte a conta no painel primeiro.")

    account.balance = req.balance
    account.equity = req.equity
    account.profit_today = req.profit_today
    account.profit_week = req.profit_week
    account.is_connected = True
    account.last_update = datetime.utcnow()
    db.commit()

    synced = 0
    for trade in req.trades:
        existing = db.query(Order).filter(
            Order.mt5_account_id == account.id,
            Order.ticket == trade.ticket,
        ).first()

        if existing:
            existing.close_price = trade.close_price
            existing.profit = trade.profit
            existing.status = trade.status
            if trade.status == "closed" and not existing.closed_at:
                existing.closed_at = datetime.utcnow()
            synced += 1
        else:
            opened_at = None
            if trade.opened_at:
                try:
                    opened_at = datetime.fromisoformat(trade.opened_at.replace('Z', '+00:00'))
                except:
                    opened_at = datetime.utcnow()

            new_order = Order(
                user_id=account.user_id,
                mt5_account_id=account.id,
                ticket=trade.ticket,
                symbol=trade.symbol,
                order_type=trade.order_type,
                volume=trade.volume,
                open_price=trade.open_price,
                close_price=trade.close_price,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
                profit=trade.profit,
                status=trade.status,
                opened_at=opened_at or datetime.utcnow(),
            )
            db.add(new_order)
            synced += 1

    db.commit()

    return {
        "ok": True,
        "account_id": account.id,
        "balance": account.balance,
        "equity": account.equity,
        "trades_synced": synced,
    }


@router.get("/status/{account_number}")
def get_mt5_status(account_number: str, db: Session = Depends(get_db)):
    account = db.query(MT5Account).filter(
        MT5Account.account_number == account_number
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    orders = db.query(Order).filter(
        Order.mt5_account_id == account.id,
        Order.status == "open"
    ).all()

    return {
        "account_number": account.account_number,
        "server": account.server,
        "balance": account.balance,
        "equity": account.equity,
        "profit_today": account.profit_today,
        "is_connected": account.is_connected,
        "last_update": account.last_update.isoformat() if account.last_update else None,
        "open_trades": len(orders),
        "trades": [{
            "ticket": o.ticket,
            "symbol": o.symbol,
            "type": o.order_type,
            "volume": o.volume,
            "open_price": o.open_price,
            "profit": o.profit,
        } for o in orders],
    }
