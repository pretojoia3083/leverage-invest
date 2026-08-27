# 🚀 LEVERAGE INVEST - Guia de Deploy

## Passo 1: Criar conta no Neon (Banco PostgreSQL Grátis)

1. Acesse https://neon.tech
2. Crie uma conta com GitHub ou email
3. Clique em **"Create Project"**
4. Escolha:
   - **Project name:** `leverage-invest`
   - **Region:** `AWS US East (Ohio)` ou mais próxima
5. Clique em **"Create Project"**
6. **Copie a Connection String** que aparece (algo como):
   ```
   postgresql://neondb_owner:xxxx@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

## Passo 2: Criar conta no Render

1. Acesse https://render.com
2. Crie uma conta com GitHub
3. Clique em **"New +"** → **"Web Service"**
4. Conecte seu repositório GitHub
5. Configure:
   - **Name:** `leverage-invest`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`

## Passo 3: Configurar Variáveis de Ambiente no Render

No painel do Render, vá em **Environment** e adicione:

| Chave | Valor |
|-------|-------|
| `DATABASE_URL` | (cole a URL do Neon) |
| `SECRET_KEY` | (gere uma chave aleatória) |
| `FRONTEND_URL` | `https://seu-app.onrender.com` |
| `PYTHON_VERSION` | `3.11.0` |

## Passo 4: Deploy Automático (opcional)

Se quiser deploy automático via GitHub:

1. Suba o código para um repositório GitHub
2. No Render, clique em **"New +"** → **"Blueprint"**
3. Conecte o repositório
4. O Render detecta o `render.yaml` automaticamente

## Passo 5: Deploy do Frontend (Estático)

O frontend é HTML puro. Duas opções:

### Opção A: Deploy no Render (já incluso)
O frontend já está configurado para servir arquivos estáticos.

### Opção B: Deploy no Vercel (mais rápido)
1. Acesse https://vercel.com
2. Conecte o repositório
3. Configure:
   - **Framework:** `Other`
   - **Build Command:** (deixe vazio)
   - **Output Directory:** `frontend`

## Passo 6: Configurar Neon

Apois criar o projeto no Neon:

1. Vá em **Dashboard** → **Connection Details**
2. Copie a URL de conexão
3. Cole no Render como `DATABASE_URL`

## Passo 7: Testar

1. Acesse `https://leverageinvest.onrender.com/api/health`
2. Deve retornar: `{"status": "ok", "app": "LEVERAGE INVEST"}`
3. Acesse o frontend e crie uma conta

---

## 📋 Resumo dos Serviços

| Serviço | URL | Uso |
|---------|-----|-----|
| **Neon** | https://neon.tech | Banco PostgreSQL (grátis) |
| **Render** | https://render.com | Backend API (grátis) |
| **Vercel** | https://vercel.com | Frontend (opcional, grátis) |

## 🔑 Custo Total: $0/mês (plano grátis)

---

## ⚠️ Importante

- O **Neon** tem 512MB de armazenamento grátis (suficiente)
- O **Render** tem 750 horas/mês grátis (suficiente)
- O **Stripe** precisa de conta de desenvolvedor para testes
- Os **robôs MT5** precisam ser compilados no MetaEditor
