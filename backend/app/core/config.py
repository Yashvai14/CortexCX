from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    HOST: str
    PORT: int
    
    DATABASE_URL: str
    SECRET_KEY: str = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    AI_PROVIDER: str = "mock"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_WEBHOOK_SECRET: str | None = None
    TELEGRAM_BOT_USERNAME: str | None = None
    # Workspace that Telegram conversations belong to (UUID). Required for the polling runner.
    TELEGRAM_WORKSPACE_ID: str | None = None

    AI_CONFIDENCE_THRESHOLD: float = 0.75
    # Ask the LLM to classify intent (extra ~10s per message on CPU). The keyword classifier already handles
    # order/stock/coupon/policy intents, and every informational question is answered from retrieved documents
    # regardless of intent, so this is off by default.
    AI_LLM_INTENT_CLASSIFICATION: bool = False
    # --- hybrid router / conversation memory / cache -------------------------------------------------
    ROUTER_USE_LLM: bool = True            # one JSON classification call, only for messages the rules are unsure about
    ROUTER_MIN_CONFIDENCE: float = 0.7     # rule confidence below this may be refined by the LLM
    CONV_WINDOW_MESSAGES: int = 8          # recent messages sent to the model (sliding window)
    CONV_SUMMARY_MAX_CHARS: int = 500      # extractive summary of everything older than the window
    DIRECT_MAX_CHARS: int = 320            # conversational replies stay short
    RAG_CACHE_ENABLED: bool = True         # reuse answers to repeated, context-free knowledge questions
    RAG_CACHE_TTL_SECONDS: int = 600
    RAG_CACHE_MAX_ENTRIES: int = 256
    # First name the support persona uses with customers (set SUPPORT_AGENT_NAME in .env to change it).
    SUPPORT_AGENT_NAME: str = "Priya"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSION: int = 768

    # RAG tuning (see app/rag/retrieval.py)
    RAG_DENSE_FLOOR: float = 0.48         # cosine similarity at/below which a dense hit counts as unrelated
    RAG_DENSE_CEIL: float = 0.74          # cosine similarity at/above which a dense hit counts as a full match
    RAG_MIN_RELEVANCE: float = 0.30       # chunks scoring below this are never shown to the LLM
    RAG_CHUNK_TARGET_CHARS: int = 1800    # target chunk size (never splits mid-sentence)
    RAG_CHUNK_MAX_CHARS: int = 2800
    RAG_CHUNK_OVERLAP_SENTENCES: int = 1
    RAG_CANDIDATES: int = 20               # stage 1: candidates from hybrid search
    RAG_CONTEXT_MAX_SPECIFIC: int = 5      # stage 2: passages passed to the LLM for a specific question
    RAG_CONTEXT_MAX_BROAD: int = 7         # ...and for a broad "what is your X policy" question

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Setting()
    