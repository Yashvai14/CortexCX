# CortexCX — System Architecture Specification

## 1. Architectural Philosophy

CortexCX is architected around 4 core principles:
1. **Channel Independence**: The cognitive AI pipeline does not know or care whether a message originates from Telegram, WebChat, WhatsApp, or an internal support agent.
2. **Authoritative Truth Hierarchy**:
   `Tool Execution Data > Database Records > Verified Policies > Retrieved Documents > LLM Model Knowledge`.
   The LLM is forbidden from fabricating orders, stock, discounts, or policies.
3. **Strict Multi-Tenancy**: Every database model and service call enforces `workspace_id`.
4. **Safety & Grounding**: When confidence is below threshold (`settings.AI_CONFIDENCE_THRESHOLD`), the system creates an escalation rather than risking hallucination.

---

## 2. Component Diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                    Omnichannel Ingestion                    │
│     Telegram Webhook (/channels/telegram/webhook)           │
│     Website Chat Widget (/channels/webchat/message)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Channel Normalization Layer                 │
│   ChannelIdentity (Maps external users to workspace customer)│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               AI Conversation Orchestrator                  │
│                                                             │
│ 1. Memory Engine: Extract facts & retrieve preferences      │
│ 2. Intent Classifier: 15 classes & entity extraction        │
│ 3. AI Planner: Goal reasoning & tool sequence selection     │
│ 4. Tool Registry: Executes commerce & knowledge tools       │
│ 5. Hybrid RAG: Dense + BM25 Fusion + Reranking + Compression│
│ 6. Multi-Signal Confidence Evaluator                        │
└───────────────────────┬─────────────────────────────┬───────┘
                        │                             │
                 [Score >= 0.75]               [Score < 0.75]
                        │                             │
                        ▼                             ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│     Local LLM (Ollama)        │   │ Human Escalation Queue  │
│  Context Assembly with        │   │ Agent Assist Generation │
│  Prompt Injection Guards      │   │ Claim / Takeover        │
│  AIRunTrace Observability     │   │ Learning Engine Feedback│
└───────────────────────────────┘   └─────────────────────────┘
```

---

## 3. Core Subsystems

### A. Memory Engine (`app/memory/`)
- **Short-Term Memory**: Conversation thread message history.
- **Customer Profile**: Persistent customer attributes (`customers` table).
- **Episodic Memory**: Conversational rule extraction (`CustomerMemoryService.extract_memories_from_text`) capturing dietary preferences, allergies, delivery instructions, and sizing notes. Stored in `customer_memories` table and queried using lexical overlap against incoming queries.

### B. Hybrid RAG Engine (`app/rag/`)
- `DenseRetriever`: Generates query embedding vector and executes cosine similarity over chunk vector arrays.
- `BM25Retriever`: Tokenizes chunks, computes inverse document frequency (IDF) and term frequency with document length penalization.
- `HybridRetriever`: Combines dense and sparse ranked candidates via Reciprocal Rank Fusion (`RRF(d) = sum(1 / (60 + rank))`).
- `Reranker`: Cross-checks query term coverage and full-phrase alignment on top-N candidates.
- `ContextCompressor`: Deduplicates overlapping sentences across chunks to conserve token context.
- `RAGContextAssembler`: Encloses retrieved chunks in `[RETRIEVED UNTRUSTED KNOWLEDGE]` tags, instructing the model to treat content solely as reference data.

### C. Tool Registry (`app/ai/tools/`)
- `ProductSearchTool`: Catalog search with inventory quantities.
- `OrderTrackingTool`: Fulfillment, carrier, and ETA lookup.
- `InventoryTool`: Real-time stock levels.
- `CouponTool`: Promo code validation and discount calculation.
- `RefundPolicyTool`: Official store policies (return, refund, cancellation, warranty).
- `KnowledgeSearchTool`: Hybrid RAG retrieval exposed as an executable tool.

### D. Multi-Signal Confidence Evaluator (`app/ai/confidence/`)
- Evaluates 4 distinct signals:
  1. `intent_confidence` (weight 35%)
  2. `tool_execution` (weight 40%)
  3. `rag_relevance` (weight 25%)
  4. `sentiment_penalty` (caps score at 0.65 if complaint/dissatisfaction is detected)
- Gating: If composite score `< AI_CONFIDENCE_THRESHOLD` (default 0.75), transitions conversation to `escalated` and generates an agent-assist ticket.
