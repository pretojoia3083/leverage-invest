from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.models.database import get_db
from app.models.schemas import MT5Account, CopyTradeConfig, Order
from app.auth import get_current_user

router = APIRouter(prefix="/api/copy-trade", tags=["Copy Trade"])


class ConnectMasterRequest(BaseModel):
    account_number: str
    server: str
    lot: float = 0.10


class ConnectFollowerRequest(BaseModel):
    master_account_id: int
    follower_account_id: int


@router.post("/connect-master")
def connect_master(
    req: ConnectMasterRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    account = db.query(MT5Account).filter(
        MT5Account.user_id == current_user.id,
        MT5Account.account_number == req.account_number
    ).first()

    if not account:
        account = MT5Account(
            user_id=current_user.id,
            account_number=req.account_number,
            server=req.server,
            balance=0,
            equity=0,
            is_connected=True
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    return {
        "message": "Conta master conectada!",
        "account": {
            "id": account.id,
            "account_number": account.account_number,
            "server": account.server,
            "type": "master",
            "lot": req.lot
        }
    }


@router.post("/connect-follower")
def connect_follower(
    req: ConnectFollowerRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    master_account = db.query(MT5Account).filter(
        MT5Account.id == req.master_account_id,
        MT5Account.user_id == current_user.id
    ).first()

    if not master_account:
        raise HTTPException(status_code=404, detail="Conta master não encontrada")

    existing_config = db.query(CopyTradeConfig).filter(
        CopyTradeConfig.user_id == current_user.id,
        CopyTradeConfig.master_account_id == master_account.id
    ).first()

    if existing_config:
        return {"message": "Configuração de copy trade já existe!", "config_id": existing_config.id}

    follower_account = db.query(MT5Account).filter(
        MT5Account.id == req.follower_account_id,
        MT5Account.user_id == current_user.id
    ).first()

    if not follower_account:
        raise HTTPException(status_code=404, detail="Conta follower não encontrada")

    config = CopyTradeConfig(
        user_id=current_user.id,
        master_account_id=master_account.id,
        follower_account_id=follower_account.id,
        lot_multiplier=1.0,
        copy_sl=True,
        copy_tp=True,
        max_lots=1.0,
        min_lots=0.01,
        is_active=True
    )
    db.add(config)
    db.commit()

    return {
        "message": "Conta follower conectada!",
        "follower": {
            "id": follower_account.id,
            "account_number": follower_account.account_number,
            "server": follower_account.server,
            "type": "follower"
        }
    }


@router.get("/config")
def get_config(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    configs = db.query(CopyTradeConfig).filter(
        CopyTradeConfig.user_id == current_user.id
    ).all()

    result = []
    for c in configs:
        master = db.query(MT5Account).filter(MT5Account.id == c.master_account_id).first()
        follower = db.query(MT5Account).filter(MT5Account.id == c.follower_account_id).first()
        result.append({
            "id": c.id,
            "master": {
                "account_number": master.account_number if master else "?",
                "server": master.server if master else "?"
            },
            "follower": {
                "account_number": follower.account_number if follower else "?",
                "server": follower.server if follower else "?"
            },
            "lot_multiplier": c.lot_multiplier,
            "is_active": c.is_active
        })

    return {"configs": result}


@router.post("/sync")
def sync_trades(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    configs = db.query(CopyTradeConfig).filter(
        CopyTradeConfig.user_id == current_user.id,
        CopyTradeConfig.is_active == True
    ).all()

    synced = 0
    for config in configs:
        master_orders = db.query(Order).filter(
            Order.mt5_account_id == config.master_account_id,
            Order.status == "open"
        ).all()

        for order in master_orders:
            existing = db.query(Order).filter(
                Order.mt5_account_id == config.follower_account_id,
                Order.ticket == f"COPY_{order.ticket}"
            ).first()

            if not existing:
                follower_lot = order.volume * config.lot_multiplier
                follower_lot = max(config.min_lots, min(follower_lot, config.max_lots))

                new_order = Order(
                    user_id=current_user.id,
                    mt5_account_id=config.follower_account_id,
                    robot_instance_id=order.robot_instance_id,
                    ticket=f"COPY_{order.ticket}",
                    symbol=order.symbol,
                    order_type=order.order_type,
                    volume=follower_lot,
                    open_price=order.open_price,
                    stop_loss=order.stop_loss if config.copy_sl else None,
                    take_profit=order.take_profit if config.copy_tp else None,
                    status="open"
                )
                db.add(new_order)
                synced += 1

    db.commit()

    return {"message": f"{synced} trades sincronizados!"}
