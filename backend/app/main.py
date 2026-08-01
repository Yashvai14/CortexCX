import app.database.models
from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.database.database import engine
from app.auth.router import router as auth_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

app.include_router(auth_router)

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