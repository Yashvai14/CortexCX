"""End-to-end answer evaluation: real LLM + real embeddings over the labelled policy document.

Prints each answer with its sources and runs deterministic checks (required facts present, forbidden claims
absent, no extraction artefacts, no raw section numbers, formatting, citation relevance).

    cd backend && .venv\\Scripts\\python -m scripts.eval_answers [question-id ...]
"""
import json
import re
import sys
import time
import uuid

sys.path.insert(0, ".")

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.answer_format import has_artefacts, has_unsupported_promise  # noqa: E402
from app.main import app  # noqa: E402
from scripts.eval_rag import DATA, setup_workspace  # noqa: E402


def check(item: dict, resp: dict) -> list[str]:
    text = resp["content"]
    low = text.lower()
    problems = []
    for f in item.get("facts", []):
        if f.lower() not in low:
            problems.append(f"missing fact: {f!r}")
    for f in item.get("forbidden", []):
        if f.lower() in low:
            problems.append(f"forbidden: {f!r}")
    if has_artefacts(text):
        problems.append("extraction artefacts")
    if has_unsupported_promise(text):
        problems.append("unsupported promise")
    if re.search(r"\[\d+\]", text):
        problems.append("raw citation marker in text")
    if re.search(r"\b\d\.\d\s+[A-Z]", text):
        problems.append("raw section number in text")
    if not item.get("unanswerable") and resp["decision"] != "ANSWER":
        problems.append(f"decision {resp['decision']}")
    if resp["decision"] == "ANSWER" and resp["sources"]:
        wanted = set(item.get("relevant", []))
        if wanted and not any(s.get("section_number") in wanted for s in resp["sources"]):
            problems.append(f"no cited source in {sorted(wanted)}; cited {[s.get('section_number') for s in resp['sources']]}")
        if len(resp["sources"]) > 4:
            problems.append("too many sources")
    return problems


def main() -> None:
    spec = json.loads((DATA / "rag_eval.json").read_text(encoding="utf8"))
    ids = {int(a) for a in sys.argv[1:]}
    client = TestClient(app)
    ws = setup_workspace(client, DATA / spec["document"])
    results = []
    for item in spec["questions"]:
        if ids and item["id"] not in ids:
            continue
        t = time.time()
        r = client.post("/channels/webchat/message", json={
            "workspace_id": str(ws), "session_id": uuid.uuid4().hex[:10], "content": item["q"], "customer_name": "Sam Rao"},
            timeout=600).json()
        dt = time.time() - t
        probs = check(item, r)
        results.append((item, r, dt, probs))
        print(f"\n=== Q{item['id']}: {item['q']}  ({dt:.1f}s)  {'OK' if not probs else 'ISSUES: ' + '; '.join(probs)}")
        print(r["content"])
        for s in r["sources"]:
            print(f"   source: {s['document_title']} · p.{s['page']} · {s.get('section_number') or ''} {s['section']}")
        if r.get("suggestions"):
            print("   follow-ups:", r["suggestions"])
    ok = sum(1 for *_, p in results if not p)
    print(f"\n{ok}/{len(results)} answers passed all checks; median latency {sorted(x[2] for x in results)[len(results)//2]:.1f}s")


if __name__ == "__main__":
    main()
