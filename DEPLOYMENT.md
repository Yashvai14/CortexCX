# CortexCX — Deployment & Production Guide

## 1. Environment Configuration

Copy `.env.example` to `.env` and configure production parameters:

```dotenv
APP_NAME=CortexCX
APP_VERSION=1.0.0
DEBUG=False
HOST=0.0.0.0
PORT=8000

# PostgreSQL Database
DATABASE_URL=postgresql://postgres:YOUR_STRONG_PASSWORD@localhost:5432/cortexcx_db

# JWT & Cryptographic Security
SECRET_KEY=GENERATE_64_CHAR_RANDOM_HEX_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# AI Provider Configuration (ollama | openai | mock)
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Confidence Gating
AI_CONFIDENCE_THRESHOLD=0.75

# Omnichannel Channels
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET=YOUR_SECRET_WEBHOOK_STRING

# Embeddings
EMBEDDING_PROVIDER=mock
EMBEDDING_DIMENSION=128
```

---

## 2. Docker Compose Deployment

```bash
# Pull and start all services (PostgreSQL, Ollama, Backend, Frontend)
docker-compose up -d --build

# Inspect running containers
docker-compose ps

# Tail logs
docker-compose logs -f backend
```

---

## 3. Database Migrations

Apply Alembic migrations to head:
```bash
# Inside container
docker-compose exec backend alembic upgrade head

# Or locally
alembic upgrade head
```

---

## 4. Ollama Setup

When deploying with Ollama:
```bash
# Pull desired inference model
docker exec -it cortexcx-ollama ollama pull llama3.2

# Verify availability
curl http://localhost:11434/api/tags
```

---

## 5. Telegram Webhook Setup

Register your Telegram webhook with Telegram Bot API:
```bash
curl -F "url=https://YOUR_DOMAIN/channels/telegram/webhook?workspace_id=YOUR_WORKSPACE_ID" \
     -F "secret_token=YOUR_SECRET_WEBHOOK_STRING" \
     https://api.telegram.org/botYOUR_TELEGRAM_BOT_TOKEN/setWebhook
```
