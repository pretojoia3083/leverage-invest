# LEVERAGE INVEST

Dashboard de trading com robôs MT5 para XAUUSD e BTCUSD.

## Fluxo do Cliente

1. **Cadastre-se** → Crie sua conta grátis
2. **Conecte MT5** → Adicione número da conta e servidor
3. **Configure o Lote** → Defina risco por trade (% da banca)
4. **Copie o Robô** → Clique em "Copiar & Operar"
5. **Acompanhe** → Lucros, ordens e performance no dashboard

## Robôs Disponíveis

| Robô | Estratégia | Ativos | Plano |
|------|-----------|--------|-------|
| GOLD SNIPER | Scalping + EMA 200 + RSI | XAUUSD | Básico |
| BTC TREND | Breakout + Volume + ATR | BTCUSD | Básico |
| GRID MASTER | Grid Trading | XAUUSD, BTCUSD | Pro |
| NEWS TRADER | News Impact | XAUUSD | Pro |
| COPY TRADE | Copy Trading | Todos | VIP |
| SCALPER PRO | Multi-TF Scalping | XAUUSD, BTCUSD | VIP |

## Configuração de Lote

Cada cliente configura individualmente:
- **% Risco por Trade** (0.5% - 10% da banca)
- **Stop Loss / Take Profit** (em pips)
- **Multiplicador de Lote**
- **Lote Máximo**
- **Trailing Stop**
- **Max Trades/Dia**
- **Max Perda/Dia**

O sistema calcula automaticamente o lote baseado no saldo da conta.

## Planos

- **Básico** (R$97/mês) → 1 robô
- **Pro** (R$197/mês) → 3 robôs
- **VIP** (R$397/mês) → Todos os robôs

## Stack

- Backend: Python FastAPI
- Frontend: HTML/CSS/JS
- Banco: PostgreSQL (Neon)
- Deploy: Render
- MT5: Expert Advisors em MQL5

## Deploy

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (estático)
# Copiar contents de frontend/ para pasta estática do Render
```

## Contato

- WhatsApp: (11) 99999-9999
- Email: contato@leverageinvest.com
- Telegram: @leverageinvest
