from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import stripe

from app.models.database import get_db
from app.models.schemas import User, Subscription
from app.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/subscription", tags=["subscription"])

stripe.api_key = settings.STRIPE_SECRET_KEY

PLANS = {
    "basic": {"name": "Básico", "price": 97, "robots": 1, "stripe_price_id": "price_basic_monthly"},
    "pro": {"name": "Pro", "price": 197, "robots": 3, "stripe_price_id": "price_pro_monthly"},
    "vip": {"name": "VIP", "price": 397, "robots": 99, "stripe_price_id": "price_vip_monthly"},
}


@router.get("/plans")
def get_plans():
    return PLANS


@router.get("/current")
def get_current_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active"
    ).order_by(Subscription.started_at.desc()).first()

    if sub:
        return {
            "plan": sub.plan,
            "status": sub.status,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "plan_info": PLANS.get(sub.plan, {}),
        }
    return {
        "plan": "free",
        "status": "inactive",
        "plan_info": PLANS["basic"],
    }


class CreateCheckoutRequest(BaseModel):
    plan: str


@router.post("/checkout")
def create_checkout(req: CreateCheckoutRequest, user: User = Depends(get_current_user)):
    if req.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    plan_info = PLANS[req.plan]

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card", "boleto"],
            line_items=[{
                "price_data": {
                    "currency": "brl",
                    "product_data": {"name": f"LEVERAGE INVEST - Plano {plan_info['name']}"},
                    "unit_amount": plan_info["price"] * 100,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{settings.FRONTEND_URL}/dashboard?payment=success",
            cancel_url=f"{settings.FRONTEND_URL}/pricing?payment=cancelled",
            customer_email=user.email,
            metadata={"user_id": str(user.id), "plan": req.plan},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar checkout: {str(e)}")


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook inválido")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        plan = session.get("metadata", {}).get("plan")

        if user_id and plan:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.plan = plan
                sub = Subscription(
                    user_id=user.id,
                    plan=plan,
                    stripe_subscription_id=session.get("subscription"),
                    stripe_customer_id=session.get("customer"),
                    status="active",
                    expires_at=datetime.utcnow() + timedelta(days=30),
                )
                db.add(sub)
                db.commit()

    return {"ok": True}
