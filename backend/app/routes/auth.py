from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.models.database import get_db
from app.models.schemas import User, Subscription
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    whatsapp: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    whatsapp: Optional[str]
    plan: str
    is_active: bool

    class Config:
        from_attributes = True


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    user = User(
        name=req.name,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        phone=req.phone,
        whatsapp=req.whatsapp,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return {"token": token, "user": UserResponse.model_validate(user)}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Conta desativada")

    token = create_access_token(data={"sub": str(user.id)})
    return {"token": token, "user": UserResponse.model_validate(user)}


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.put("/me")
def update_profile(req: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.name:
        user.name = req.name
    if req.phone is not None:
        user.phone = req.phone
    if req.whatsapp is not None:
        user.whatsapp = req.whatsapp
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    user.hashed_password = get_password_hash(req.new_password)
    db.commit()
    return {"ok": True, "message": "Senha alterada com sucesso"}
