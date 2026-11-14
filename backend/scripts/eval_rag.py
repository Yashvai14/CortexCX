"""Retrieval evaluation against a labelled document (default: the THREAD & TREND refund/return policy PDF).

Measures retrieval on its own (not LLM answer quality): Recall@5, Recall@10, Precision@5, MRR, context precision,
duplication and latency. Uses the REAL embedding model configured in .env, in a throwaway workspace.

    cd backend && .venv\\Scripts\\python -m scripts.eval_rag
"""
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, ".")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.database.database import SessionLocal  # noqa: E402
from app.rag.retrieval import RAGRetriever  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"


def setup_workspace(client: TestClient, pdf: Path) -> uuid.UUID:
    tag = uuid.uuid4().hex[:8]
    reg = client.post("/auth/register", json={"company_name": f"Eval {tag}", "company_slug": f"eval-{tag}", "full_name": "Eval",
                                              "email": f"eval_{tag}@example.com", "password": "SecurePassword123!"})
    assert reg.status_code == 201, reg.text
    tok = client.post("/auth/login", data={"username": f"eval_{tag}@example.com", "password": "SecurePassword123!"}).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    src = client.post("/knowledge/sources", headers=H, json={"name": "Policies", "source_type": "pdf"}).json()
    up = client.post("/knowledge/upload", headers=H, data={"knowledge_source_id": src["id"]},
                     files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")}, timeout=300)
    assert up.status_code == 201, up.text
    for _ in range(600):
        d = client.get(f"/knowledge/documents/{up.json()['id']}", headers=H).json()
        if d["status"] not in ("processing", "pending"):
            break
        time.sleep(0.5)
    assert d["status"] == "completed", d
    return uuid.UUID(reg.json()["workspace"]["id"])


def section_no(chunk) -> str | None:
    return (chunk.metadata_json or {}).get("section_number")


def evaluate(workspace_id: uuid.UUID, spec: dict) -> dict:
    db = SessionLocal()
    rows, lat = [], []
    try:
        for item in spec["questions"]:
            if item.get("unanswerable"):
                continue
            r = RAGRetriever()
            t = time.perf_counter()
            ctx, plan = r.retrieve_with_plan(db, workspace_id, item["q"], top_k=5)
            lat.append(time.perf_counter() - t)
            ranked = [section_no(c) for c, _, _ in r.last_ranked]
            ctx_secs = [section_no(c) for c, _ in ctx]
            rel = set(item["relevant"])
            first = next((i for i, s in enumerate(ranked, 1) if s in rel), None)
            rows.append({
                "id": item["id"], "q": item["q"], "broad": plan.broad,
                "hit@5": first is not None and first <= 5, "hit@10": first is not None and first <= 10,
                "p@5": sum(1 for s in ranked[:5] if s in rel) / max(len(ranked[:5]), 1),
                "mrr": 1 / first if first else 0.0,
                "ctx_precision": (sum(1 for s in ctx_secs if s in rel) / len(ctx_secs)) if ctx_secs else 0.0,
                "ctx_hit": any(s in rel for s in ctx_secs),
                "ctx_size": len(ctx_secs), "ctx": ctx_secs, "ranked": ranked[:6],
                "ctx_ranks": [round((c.retrieval or {}).get("rank", 0), 2) for c, _ in ctx],
                "dupes": len(ctx_secs) - len(set((c.id for c, _ in ctx))),
            })
        # multi-turn
        conv_rows = []
        for conv in spec.get("conversations", []):
            hist: list[str] = []
            for turn in conv["turns"]:
                r = RAGRetriever()
                ctx, plan = r.retrieve_with_plan(db, workspace_id, turn["q"], top_k=5, history=list(hist))
                ranked = [section_no(c) for c, _, _ in r.last_ranked]
                rel = set(turn["relevant"])
                conv_rows.append({"conv": conv["id"], "q": turn["q"], "hit@5": any(s in rel for s in ranked[:5]),
                                  "ctx": [section_no(c) for c, _ in ctx], "ranked": ranked[:5]})
                hist.append(turn["q"])
    finally:
        db.close()

    n = len(rows)
    summary = {
        "questions": n,
        "recall@5": sum(r["hit@5"] for r in rows) / n,
        "recall@10": sum(r["hit@10"] for r in rows) / n,
        "precision@5": statistics.mean(r["p@5"] for r in rows),
        "mrr": statistics.mean(r["mrr"] for r in rows),
        "context_hit": sum(r["ctx_hit"] for r in rows) / n,
        "context_precision": statistics.mean(r["ctx_precision"] for r in rows),
        "avg_context_chunks": statistics.mean(r["ctx_size"] for r in rows),
        "duplicate_chunks": sum(r["dupes"] for r in rows),
        "multi_turn_recall@5": (sum(c["hit@5"] for c in conv_rows) / len(conv_rows)) if conv_rows else None,
        "latency_p50_s": statistics.median(lat),
        "latency_p95_s": sorted(lat)[max(int(len(lat) * 0.95) - 1, 0)],
    }
    return {"summary": summary, "rows": rows, "conversations": conv_rows}


def main() -> None:
    spec = json.loads((DATA / "rag_eval.json").read_text(encoding="utf8"))
    pdf = DATA / spec["document"]
    print(f"Embedding provider: {settings.EMBEDDING_PROVIDER} ({settings.EMBEDDING_MODEL})")
    client = TestClient(app)
    ws = setup_workspace(client, pdf)
    res = evaluate(ws, spec)
    for r in res["rows"]:
        flag = "OK " if r["hit@5"] else "MISS"
        print(f"{flag} Q{r['id']:<2} {r['q'][:58]:58} broad={str(r['broad'])[0]} ctx={r['ctx']} {r['ctx_ranks']}")
    print()
    for c in res["conversations"]:
        print(f"{'OK ' if c['hit@5'] else 'MISS'} conv {c['conv']}: {c['q'][:48]:48} ctx={c['ctx']} ranked={c['ranked'][:3]}")
    print("\n== SUMMARY ==")
    for k, v in res["summary"].items():
        print(f"{k:22} {v:.3f}" if isinstance(v, float) else f"{k:22} {v}")
    out = DATA / "rag_eval_last_run.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf8")
    print(f"\nFull results written to {out}")


if __name__ == "__main__":
    main()
