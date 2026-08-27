from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime

from app.models.database import get_db
from app.models.schemas import User, Robot, RobotInstance, MT5Account
from app.auth import get_current_user

router = APIRouter(prefix="/api/robots", tags=["robots"])


@router.get("")
def list_robots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    robots = db.query(Robot).filter(Robot.is_active == True).all()
    user_instances = db.query(RobotInstance).filter(RobotInstance.user_id == user.id).all()
    instance_map = {ri.robot_id: ri for ri in user_instances}

    return [{
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "strategy": r.strategy,
        "symbols": r.symbols.split(","),
        "min_plan": r.min_plan,
        "icon": r.icon,
        "instance": {
            "id": inst.id,
            "is_running": inst.is_running,
            "profit_total": inst.profit_total,
            "trades_count": inst.trades_count,
            "wins_count": inst.wins_count,
            "losses_count": inst.losses_count,
            "win_rate": inst.win_rate,
            "daily_trades_today": inst.daily_trades_today,
            "daily_pnl": inst.daily_pnl,
            "settings": inst.get_settings_dict(),
        } if r.id in instance_map else None,
    } for r in robots]


class CreateInstanceRequest(BaseModel):
    robot_id: int
    mt5_account_id: int


@router.post("/instance")
def create_instance(req: CreateInstanceRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    robot = db.query(Robot).filter(Robot.id == req.robot_id).first()
    if not robot:
        raise HTTPException(status_code=404, detail="Robô não encontrado")

    account = db.query(MT5Account).filter(
        MT5Account.id == req.mt5_account_id,
        MT5Account.user_id == user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conta MT5 não encontrada")

    existing = db.query(RobotInstance).filter(
        RobotInstance.user_id == user.id,
        RobotInstance.robot_id == req.robot_id,
        RobotInstance.mt5_account_id == req.mt5_account_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Instância já existe para este robô e conta")

    plan_order = {"basic": 0, "pro": 1, "vip": 2}
    if plan_order.get(user.plan, 0) < plan_order.get(robot.min_plan, 0):
        raise HTTPException(status_code=403, detail=f"Plano {robot.min_plan} necessário para este robô")

    # Calculate initial lot based on account balance
    instance = RobotInstance(
        user_id=user.id,
        mt5_account_id=req.mt5_account_id,
        robot_id=req.robot_id,
    )
    # Auto-calculate lot
    initial_lot = instance.calculate_lot(account.balance, robot.symbols.split(",")[0])
    instance.fixed_lot = initial_lot

    db.add(instance)
    db.commit()
    db.refresh(instance)
    return {"ok": True, "instance_id": instance.id}


class ToggleRobotRequest(BaseModel):
    instance_id: int


@router.post("/toggle")
def toggle_robot(req: ToggleRobotRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    instance = db.query(RobotInstance).filter(
        RobotInstance.id == req.instance_id,
        RobotInstance.user_id == user.id,
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instância não encontrada")

    instance.is_running = not instance.is_running
    if instance.is_running:
        instance.started_at = datetime.utcnow()
        instance.daily_trades_today = 0
        instance.daily_pnl = 0.0
    else:
        instance.started_at = None

    db.commit()
    return {"ok": True, "is_running": instance.is_running}


class UpdateSettingsRequest(BaseModel):
    instance_id: int
    risk_per_trade: Optional[float] = None
    max_lot: Optional[float] = None
    min_lot: Optional[float] = None
    max_daily_trades: Optional[int] = None
    max_daily_loss: Optional[float] = None
    stop_loss_pips: Optional[int] = None
    take_profit_pips: Optional[int] = None
    trailing_stop: Optional[bool] = None
    trailing_stop_pips: Optional[int] = None
    lot_multiplier: Optional[float] = None
    use_dynamic_lot: Optional[bool] = None
    fixed_lot: Optional[float] = None


@router.put("/settings")
def update_settings(req: UpdateSettingsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    instance = db.query(RobotInstance).filter(
        RobotInstance.id == req.instance_id,
        RobotInstance.user_id == user.id,
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instância não encontrada")

    # Update only provided fields
    for field in ['risk_per_trade', 'max_lot', 'min_lot', 'max_daily_trades', 'max_daily_loss',
                  'stop_loss_pips', 'take_profit_pips', 'trailing_stop', 'trailing_stop_pips',
                  'lot_multiplier', 'use_dynamic_lot', 'fixed_lot']:
        val = getattr(req, field, None)
        if val is not None:
            setattr(instance, field, val)

    db.commit()
    db.refresh(instance)

    # Return updated settings
    account = db.query(MT5Account).filter(MT5Account.id == instance.mt5_account_id).first()
    robot = db.query(Robot).filter(Robot.id == instance.robot_id).first()

    calculated_lot = instance.calculate_lot(account.balance if account else 0, robot.symbols.split(",")[0] if robot else "XAUUSD")

    return {
        "ok": True,
        "settings": instance.get_settings_dict(),
        "calculated_lot": calculated_lot,
        "account_balance": account.balance if account else 0,
    }


@router.get("/settings/{instance_id}")
def get_settings(instance_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    instance = db.query(RobotInstance).filter(
        RobotInstance.id == instance_id,
        RobotInstance.user_id == user.id,
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instância não encontrada")

    account = db.query(MT5Account).filter(MT5Account.id == instance.mt5_account_id).first()
    robot = db.query(Robot).filter(Robot.id == instance.robot_id).first()

    calculated_lot = instance.calculate_lot(account.balance if account else 0, robot.symbols.split(",")[0] if robot else "XAUUSD")

    return {
        "settings": instance.get_settings_dict(),
        "calculated_lot": calculated_lot,
        "account_balance": account.balance if account else 0,
        "robot_name": robot.name if robot else "",
        "symbol": robot.symbols.split(",")[0] if robot else "XAUUSD",
    }
