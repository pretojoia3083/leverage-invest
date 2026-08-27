from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.models.database import get_db
from app.models.schemas import User, ContactMessage
from app.auth import get_current_user

router = APIRouter(prefix="/api/contact", tags=["contact"])


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: Optional[str] = None
    message: str


@router.post("")
def send_message(req: ContactRequest, db: Session = Depends(get_db)):
    msg = ContactMessage(
        name=req.name,
        email=req.email,
        subject=req.subject,
        message=req.message,
    )
    db.add(msg)
    db.commit()
    return {"ok": True, "message": "Mensagem enviada com sucesso!"}


@router.get("/info")
def get_contact_info():
    return {
        "whatsapp": "+5511999999999",
        "email": "contato@leverageinvest.com",
        "telegram": "@leverageinvest",
        "instagram": "@leverageinvest",
    }
