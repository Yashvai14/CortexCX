# 🧠 CortexCX — AI Customer Experience Operating System

> **The Enterprise-Grade AI Operating System for Direct-to-Consumer (D2C) Brands**  
> Built with FastAPI, PostgreSQL, Next.js, Tailwind CSS, Ollama local inference, Hybrid RAG, Customer Memory, Tool Planning, Human Escalations, and Omnichannel Ingestion (Telegram & Storefront WebChat).

---

## 🎯 What is CortexCX?

CortexCX is not a simple chatbot or naive RAG wrapper. It is a full-stack **Customer Experience Operating System** designed for high-growth e-commerce brands to automate customer inquiries safely with high confidence, while seamlessly orchestrating human agent assist when complex exceptions occur.

### Complete Closed-Loop Customer Journey:
```text
                         CORTEXCX
            AI CUSTOMER EXPERIENCE OPERATING SYSTEM

                      Omnichannel Ingestion
                     (Telegram / Website Chat)
                               │
                               ▼
                      Conversation Manager
                               │
                               ▼
                         Memory Engine
                 (Episodic Facts & Preferences)
                               │
                               ▼
                        Intent Detection
                  (15 E-commerce Intent Categories)
                               │
                               ▼
                          AI Planner
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
           Tool Calling                  Hybrid RAG
       (Orders, Catalog, Stock,     (Dense Vector + BM25
        Coupons, Store Policies)      + RRF + Reranker)
                │                             │
                └──────────────┬──────────────┘
                               ▼
                           Local LLM
                       (Ollama / Llama 3)
                               │
                               ▼
                     Confidence Evaluation
                          │          │
                        HIGH         LOW / Request
                          │          │
                          ▼          ▼
                     AI Response  Human Escalation
                                       │
                                       ▼
                                  Agent Assist
                               (Drafts, Memories, Summary)
                                       │
                                       ▼
                                 Learning Engine
                              (Verified Q&A Feedback)
                                       │
                                       ▼
                               Analytics & Tracing
```

---

## 🚀 Key Implemented Modules

1. **Admin Portal**: Executive dashboard, Conversations, Human Escalation inbox, Analytics & latency metrics, Commerce catalog & policies, Knowledge Base manager, and Storefront Chat simulator.
2. **Cognitive Pipeline**:
   - **Intent Classifier**: Structured 15-class intent detection with entity extraction (`order_number`, `policy_type`, `coupon_code`).
   - **AI Task Planner**: Automatic goal decomposition, step sequencing, tool execution, and escalation trigger assessment.
   - **Tool Registry**: Direct integration with D2C commerce services (`product_search`, `order_tracking`, `inventory_lookup`, `coupon_tool`, `policy_lookup`, `knowledge_search`).
   - **Multi-Signal Confidence Evaluator**: Composite scoring across intent confidence, tool execution status, RAG relevance, and sentiment penalty.
3. **Advanced Hybrid RAG**:
   - **Dense Retrieval**: Embedding vector cosine similarity search.
   - **Sparse Retrieval**: BM25 keyword matching with term frequency & length normalization.
   - **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse lists cleanly.
   - **Reranker & Context Compressor**: Deduplicates sentences and optimizes token space.
   - **Prompt Injection Defense**: Untrusted knowledge boundary delimiters.
   - **Document Parsers**: PDF, DOCX, TXT, and live web page/URL scraping.
4. **Customer Memory Engine**:
   - Short-term conversation context.
   - Episodic memory extraction (detects dietary preferences, allergies, sizing, delivery instructions).
   - Dynamic memory retrieval relevant to incoming queries.
5. **Omnichannel Messaging**:
   - **Telegram Integration**: Webhook endpoint with duplicate protection, user mapping, conversation tracking, and reply dispatch.
   - **Website Chat**: Public customer chat widget endpoint with guest session identity resolution and conversation persistence.
6. **Human Handoff & Agent Assist**:
   - Auto-escalation queue for low-confidence inquiries.
   - Real-time AI draft generation, conversation summary, and customer memories presented to support agents.
   - Claim, respond, resolve, and return-to-AI lifecycle.
   - Learning feedback capture on human corrections.
7. **Production Containerization**:
   - Multi-stage `Dockerfile` for FastAPI backend.
   - Multi-stage `Dockerfile` for Next.js frontend.
   - Full `docker-compose.yml` orchestrating PostgreSQL, Ollama, Backend, and Frontend.

---

## 🛠️ Quickstart Guide

### Option 1: Docker Compose (One-Click)

```bash
docker-compose up --build
```
- **Backend API**: `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
- **Admin Dashboard**: `http://localhost:3000`
- **Storefront Chat Widget**: `http://localhost:3000/chat`

### Option 2: Local Python & Node Setup

#### 1. Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Automated Testing

Run the full pytest suite (26 passing tests):
```bash
cd backend
pytest -v
```
Tests cover:
- `test_end_to_end_operating_system.py`: Complete e2e customer journeys (WebChat, Telegram, Escalation, Analytics).
- `test_cognitive_engine.py`: Intent detection, tool execution, planning, and confidence gating.
- `test_hybrid_rag_and_memory.py`: Dense + BM25 fusion, reranking, and episodic memory extraction.
- `test_conversations.py`, `test_customers.py`, `test_knowledge_base.py`, `test_rbac.py`, `test_workspace_management.py`.
