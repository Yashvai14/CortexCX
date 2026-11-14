"""Bootstrap script executed automatically on Docker container startup.

1. Ensures required Ollama models (LLM + Embedding) are available in the Ollama service.
2. Seeds the initial demo workspace, owner account, catalog, orders, policies, and knowledge base if the DB is empty.
"""

import sys
import httpx

sys.path.insert(0, ".")

import app.database.models  # noqa: F401
from app.core.config import settings
from app.database.database import SessionLocal
from app.workspace.model import Workspace


def ensure_ollama_models() -> None:
    base_url = (settings.OLLAMA_BASE_URL or "").rstrip("/")
    if not base_url:
        return

    needed_models: list[str] = []
    if (settings.AI_PROVIDER or "").lower().strip() == "ollama" and settings.OLLAMA_MODEL:
        needed_models.append(settings.OLLAMA_MODEL.strip())
    if (settings.EMBEDDING_PROVIDER or "").lower().strip() == "ollama" and settings.EMBEDDING_MODEL:
        needed_models.append(settings.EMBEDDING_MODEL.strip())

    if not needed_models:
        return

    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=10.0)
        resp.raise_for_status()
        installed = {m.get("name", "") for m in resp.json().get("models", [])}
        installed_short = {name.split(":")[0] for name in installed}
    except Exception as exc:
        print(f"[bootstrap] Ollama not reachable yet at {base_url}: {exc}")
        return

    for model in needed_models:
        if model in installed or model in installed_short:
            print(f"[bootstrap] Ollama model '{model}' already present.")
            continue
        print(f"[bootstrap] Pulling missing Ollama model '{model}' from {base_url} ...")
        try:
            with httpx.stream(
                "POST",
                f"{base_url}/api/pull",
                json={"name": model, "stream": True},
                timeout=600.0,
            ) as pull_resp:
                pull_resp.raise_for_status()
            print(f"[bootstrap] Successfully pulled '{model}'.")
        except Exception as exc:
            print(f"[bootstrap] Warning: could not pull '{model}': {exc}")


def ensure_initial_workspace() -> None:
    db = SessionLocal()
    try:
        count = db.query(Workspace).count()
        if count > 0:
            print(f"[bootstrap] Database already has {count} workspace(s); skipping initial seed.")
            return
    finally:
        db.close()

    print("[bootstrap] No workspace found in database. Creating demo user and seeding store data...")
    try:
        import scripts.create_demo_user  # noqa: F401
        from scripts.seed_demo import main as seed_demo_main

        seed_demo_main("demo")
        print("[bootstrap] Demo workspace ('demo') initialized successfully.")
    except Exception as exc:
        print(f"[bootstrap] Warning during initial workspace seed: {exc}")


if __name__ == "__main__":
    ensure_ollama_models()
    ensure_initial_workspace()

