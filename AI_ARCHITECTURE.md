# CortexCX — AI & Cognitive Engine Architecture

## 1. Cognitive Architecture Overview

The cognitive engine in CortexCX transforms customer messages into grounded, audited, and explainable actions.

```text
Incoming Message
       │
       ▼
1. Memory Extraction ──► Updates CustomerMemory
       │
2. Intent Classification ──► IntentResult (intent, confidence, entities)
       │
3. Task Planning ──► PlanResult (steps, requires_rag, escalate)
       │
4. Tool Execution ──► ToolResult[] via ToolRegistry
       │
5. Hybrid RAG ──► Dense + BM25 Fusion ──► Reranking ──► Compression
       │
6. Multi-Signal Confidence Evaluator
       │
   ┌───┴────────────────────────┐
   │                            │
   ▼ [>= 0.75]                  ▼ [< 0.75]
7A. Local LLM Generation     7B. Escalation Engine
   - Prompt Injection Defense    - Drafts Summary & Reply
   - Truth Hierarchy Enforcement - Creates HumanEscalation
   - AIRunTrace Persisted        - Flags Conversation
```

---

## 2. Intent Detection Taxonomy

15 standardized D2C commerce intent categories:
1. `PRODUCT_SEARCH`: Inquiries seeking product discovery, browsing, or recommendations.
2. `PRODUCT_INFORMATION`: Deep product specifications, sizing, materials, or ingredients.
3. `ORDER_STATUS`: Order delivery status, tracking number, carrier status, ETA.
4. `ORDER_CANCELLATION`: Order cancellation requests.
5. `REFUND`: Inquiries requesting money back or refund eligibility.
6. `RETURN`: Product return procedures or exchange requests.
7. `COUPON`: Discount codes, vouchers, or promotions.
8. `DISCOUNT`: Inquiries regarding sales, volume pricing, or deals.
9. `INVENTORY`: Item stock availability, restock timing, out-of-stock notices.
10. `DELIVERY`: Shipping rates, shipping speeds, carrier options, regional restrictions.
11. `POLICY`: Official warranty, privacy, return, or terms of service inquiries.
12. `GENERAL_FAQ`: Store hours, contact details, brand philosophy.
13. `HUMAN_AGENT`: Explicit customer request to speak with a human agent.
14. `COMPLAINT`: Customer frustration, damaged package, or bad service.
15. `OTHER`: Ambiguous or unclassified inquiries.

---

## 3. Local LLM Provider (Ollama)

- **Provider**: `OllamaProvider` (`app/ai/providers/ollama_provider.py`)
- **Default Base URL**: `http://localhost:11434`
- **Default Model**: `llama3.2`
- **Protocol**: HTTP REST (`/api/chat`) with strict timeouts (60s) and clean connection error handling.
- **Pluggability**: Factory `get_llm_provider()` can switch between `ollama`, `openai`, and `mock` via `AI_PROVIDER` in `.env`.

---

## 4. Observability & AIRunTrace

Every conversation turn records an `AIRunTrace` in PostgreSQL containing:
- `conversation_id`, `message_id`
- `intent`, `intent_confidence`
- `decision` (`ANSWER` or `ESCALATE`)
- `confidence_score`
- `tools_executed` (JSON list with tool name, arguments, and execution success)
- `retrieved_sources` (JSON list with document ID, title, and relevance score)
- `model_name` (e.g. `llama3.2` or `mock-support-agent-v1`)
- `duration_ms` (total pipeline execution latency in milliseconds)
