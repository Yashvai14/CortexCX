import app.database.models
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.auth.user_router import router as user_router
from app.conversation.router import router as conversation_router
from app.core.config import settings
from app.customer.router import router as customer_router
from app.database.database import engine
from app.knowledge.router import router as knowledge_router
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

@app.get("/")
def root():
    return{
        "message": "Welcome to CortexCX",
        "version": settings.APP_VERSION
    }

@app.get("/health")
def health():
    return{
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }

@app.get("/db-health")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return{
            "database": "connected"
        }

    except Exception as e:
        return{
            "database": "failed",
            "error": str(e)
        }