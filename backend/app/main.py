import app.database.models
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.ai.router import router as ai_router
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.auth.user_router import router as user_router
from app.channels.router import router as channels_router
from app.commerce.router import router as commerce_router
from app.conversation.router import router as conversation_router
from app.core.config import settings
from app.customer.router import router as customer_router
from app.database.database import engine
from app.escalation.router import router as escalation_router
from app.knowledge.router import router as knowledge_router
from app.ticket.router import router as ticket_router
from app.workspace.router import router as workspace_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

# ---------------------------------------------------------------
# CORS — allow frontend dev servers to call the API
# ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(user_router)
app.include_router(customer_router)
app.include_router(conversation_router)
app.include_router(ai_router)
app.include_router(knowledge_router)
app.include_router(channels_router)
app.include_router(escalation_router)
app.include_router(commerce_router)
app.include_router(analytics_router)
app.include_router(ticket_router)

@app.on_event("startup")
def _warm_llm():
    if (settings.AI_PROVIDER or "").lower().strip() == "ollama":
        from app.ai.providers.ollama_provider import warm_up_ollama

        warm_up_ollama()


@app.get("/")
def root():
    return{
        "message": "Welcome to CortexCX",
        "version": settings.APP_VERSION
    }

@app.get("/health")
def health():
    services = {}
    overall_healthy = True

    # 1. Database Check
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        services["database"] = {"status": "healthy"}
    except Exception as e:
        services["database"] = {"status": "unhealthy", "error": "Database connection failed"}
        overall_healthy = False

    # 2. Ollama Diagnostic Check
    import httpx
    try:
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        resp = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            services["ollama"] = {
                "status": "healthy",
                "model": settings.OLLAMA_MODEL,
            }
        else:
            services["ollama"] = {
                "status": "degraded",
                "error": f"Ollama returned HTTP {resp.status_code}",
            }
    except Exception:
        services["ollama"] = {
            "status": "offline",
            "error": f"Ollama not reachable at {settings.OLLAMA_BASE_URL}",
        }

    # 3. Vector Store / Embeddings Check
    try:
        from app.embeddings.factory import get_embedding_provider
        provider = get_embedding_provider()
        services["vector_store"] = {
            "status": "healthy",
            "provider": provider.__class__.__name__,
        }
    except Exception as e:
        services["vector_store"] = {
            "status": "degraded",
            "error": "Vector provider initialization failed",
        }

    # 4. Telegram Channel Configuration
    telegram_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    if telegram_token and telegram_token.strip():
        services["telegram"] = {"status": "configured"}
    else:
        services["telegram"] = {"status": "not_configured"}

    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "services": services,
    }


@app.get("/db-health")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception as e:
        return {"database": "failed", "error": str(e)}
