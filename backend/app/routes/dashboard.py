from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.database import get_db
from app.models.schemas import User, MT5Account, RobotInstance, Order, Robot
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    all_accounts = db.query(MT5Account).filter(MT5Account.user_id == user.id).all()
    robots = db.query(RobotInstance).filter(RobotInstance.user_id == user.id).all()
    running = [r for r in robots if r.is_running]

    real_accounts = [a for a in all_accounts if 'demo' not in (a.server or '').lower()]
    demo_accounts = [a for a in all_accounts if 'demo' in (a.server or '').lower()]

    total_balance = sum(a.balance for a in real_accounts)
    total_equity = sum(a.equity for a in real_accounts)
    total_profit_today = sum(a.profit_today for a in real_accounts)
    total_profit_week = sum(a.profit_week for a in real_accounts)
    total_profit_month = sum(a.profit_month for a in real_accounts)
    profit_pct = (total_profit_today / total_balance * 100) if total_balance > 0 else 0

    recent_orders = db.query(Order).filter(
        Order.user_id == user.id
    ).order_by(Order.opened_at.desc()).limit(10).all()

    account_map = {a.id: a for a in all_accounts}

    return {
        "accounts": [{
            "id": a.id,
            "account_number": a.account_number,
            "server": a.server,
            "balance": a.balance,
            "equity": a.equity,
            "profit_today": a.profit_today,
            "profit_week": a.profit_week,
            "profit_month": a.profit_month,
            "profit_pct": a.profit_pct,
            "is_connected": a.is_connected,
        } for a in real_accounts],
        "demo_accounts": [{
            "id": a.id,
            "account_number": a.account_number,
            "server": a.server,
            "balance": a.balance,
            "equity": a.equity,
            "profit_today": a.profit_today,
            "is_connected": a.is_connected,
        } for a in demo_accounts],
        "summary": {
            "total_balance": total_balance,
            "total_equity": total_equity,
            "profit_today": total_profit_today,
            "profit_week": total_profit_week,
            "profit_month": total_profit_month,
            "profit_pct": round(profit_pct, 2),
            "active_robots": len(running),
            "total_robots": len(robots),
        },
        "recent_orders": [{
            "id": o.id,
            "ticket": o.ticket,
            "symbol": o.symbol,
            "type": o.order_type,
            "volume": o.volume,
            "open_price": o.open_price,
            "close_price": o.close_price,
            "profit": o.profit,
            "status": o.status,
            "account_number": account_map.get(o.mt5_account_id, None).account_number if account_map.get(o.mt5_account_id) else None,
            "is_demo": 'demo' in (account_map.get(o.mt5_account_id, None).server or '').lower() if account_map.get(o.mt5_account_id) else False,
            "opened_at": o.opened_at.isoformat() if o.opened_at else None,
        } for o in recent_orders],
    }


@router.get("/stats")
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())

    today_orders = db.query(Order).filter(
        Order.user_id == user.id,
        Order.opened_at >= today_start
    ).all()
    week_orders = db.query(Order).filter(
        Order.user_id == user.id,
        Order.opened_at >= week_start
    ).all()

    today_profit = sum(o.profit for o in today_orders)
    week_profit = sum(o.profit for o in week_orders)
    today_trades = len(today_orders)
    week_trades = len(week_orders)
    today_wins = len([o for o in today_orders if o.profit > 0])
    week_wins = len([o for o in week_orders if o.profit > 0])

    return {
        "today": {
            "profit": today_profit,
            "trades": today_trades,
            "wins": today_wins,
            "win_rate": round(today_wins / today_trades * 100, 1) if today_trades > 0 else 0,
        },
        "week": {
            "profit": week_profit,
            "trades": week_trades,
            "wins": week_wins,
            "win_rate": round(week_wins / week_trades * 100, 1) if week_trades > 0 else 0,
        },
    }
