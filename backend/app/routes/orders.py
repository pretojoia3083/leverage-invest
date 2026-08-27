from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import User, Order, MT5Account
from app.auth import get_current_user

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 50):
    orders = db.query(Order).filter(
        Order.user_id == user.id
    ).order_by(Order.opened_at.desc()).limit(limit).all()

    return [{
        "id": o.id,
        "ticket": o.ticket,
        "symbol": o.symbol,
        "type": o.order_type,
        "volume": o.volume,
        "open_price": o.open_price,
        "close_price": o.close_price,
        "profit": o.profit,
        "status": o.status,
        "opened_at": o.opened_at.isoformat() if o.opened_at else None,
        "closed_at": o.closed_at.isoformat() if o.closed_at else None,
    } for o in orders]


@router.get("/open")
def list_open_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(
        Order.user_id == user.id,
        Order.status == "open"
    ).order_by(Order.opened_at.desc()).all()

    return [{
        "id": o.id,
        "ticket": o.ticket,
        "symbol": o.symbol,
        "type": o.order_type,
        "volume": o.volume,
        "open_price": o.open_price,
        "profit": o.profit,
        "status": o.status,
        "opened_at": o.opened_at.isoformat() if o.opened_at else None,
    } for o in orders]
