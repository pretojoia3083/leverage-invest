import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models.database import engine, Base
from app.routes import auth, dashboard, robots, orders, contact, subscription
from app.config import settings

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

app = FastAPI(title="LEVERAGE INVEST", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(robots.router)
app.include_router(orders.router)
app.include_router(contact.router)
app.include_router(subscription.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _seed_robots()


def _seed_robots():
    from app.models.database import SessionLocal
    from app.models.schemas import Robot

    db = SessionLocal()
    try:
        if db.query(Robot).count() == 0:
            robots = [
                Robot(
                    name="GOLD SNIPER",
                    description="Scalping preciso no ouro com filtro de tendência EMA 200 + RSI. Entradas cirúrgicas nos melhores pontos de reversão.",
                    strategy="Scalping + EMA 200 + RSI Filter",
                    symbols="XAUUSD",
                    min_plan="basic",
                    icon="🎯",
                ),
                Robot(
                    name="BTC TREND",
                    description="Breakout de volume + ATR para capturar grandes movimentos do Bitcoin. Ideial para tendências fortes.",
                    strategy="Breakout + Volume + ATR",
                    symbols="BTCUSD",
                    min_plan="basic",
                    icon="📈",
                ),
                Robot(
                    name="GRID MASTER",
                    description="Grid trading inteligente com gerenciamento de risco dinâmico. Opera em ranging markets com alta frequência.",
                    strategy="Grid + Risk Management",
                    symbols="XAUUSD,BTCUSD",
                    min_plan="pro",
                    icon="🔲",
                ),
                Robot(
                    name="NEWS TRADER",
                    description="Captura volatilidade após notícias de alto impacto. Entrada rápida com stop bem definido.",
                    strategy="News Impact + Volatility",
                    symbols="XAUUSD",
                    min_plan="pro",
                    icon="⚡",
                ),
                Robot(
                    name="COPY TRADE",
                    description="Sinais do servidor central executados automaticamente na sua conta. Operações de traders profissionais.",
                    strategy="Copy Trading",
                    symbols="XAUUSD,BTCUSD",
                    min_plan="vip",
                    icon="🔄",
                ),
                Robot(
                    name="SCALPER PRO",
                    description="Scalping de alta frequência com M5/M15. Múltiplas operações por dia com alvos pequenos e consistentes.",
                    strategy="Multi-Timeframe Scalping",
                    symbols="XAUUSD,BTCUSD",
                    min_plan="vip",
                    icon="⚡",
                ),
            ]
            db.add_all(robots)
            db.commit()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "LEVERAGE INVEST"}


@app.get("/")
def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "Frontend not found", "path": str(FRONTEND_DIR)}
